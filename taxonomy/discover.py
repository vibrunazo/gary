"""Build taxonomy discovery (docs/ARCHITECTURE.md §7.3), first pass.

From the build orders extracted by ingest/build_orders.py, for one matchup and one race:

  1. Features: the time each key item first appears (e.g. Spawning Pool, 2nd Hatchery, Lair,
     Spire, first Mutalisk), within a time window. Missing items get a "never" value.
  2. Clusters: HDBSCAN on those timings, so the same plan with slightly different timing or
     order lands in the same cluster. Players that fit no cluster are left as noise.
  3. Cluster cards: size, win rate, how often each item appears and its typical timing, the
     typical order of the first buildings, and example replays. These are what a person (or an
     LLM) reviews and names.
  4. Readable rules: a shallow decision tree that separates the clusters, printed as if/then
     rules. They become the deterministic `opening_class` provider once reviewed.
  5. Opening tree: counts of the most common first-N-building sequences.

Only items with `confirmed` or `ordered` confidence are used (cancelled and not-built are dropped).

Output: data/interim/taxonomy/<matchup>_<race>_<level>.md (cards) and .json (assignments).

Usage:
  python taxonomy/discover.py --matchup TvZ --race Z --level tech
  python taxonomy/discover.py --matchup TvZ --race T --level opening --min-cluster 150
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.cluster import HDBSCAN
from sklearn.tree import DecisionTreeClassifier, export_text

REPO_ROOT = Path(__file__).resolve().parent.parent

# Key items per race: (feature name, item name, which instance). Instance 2 = the second one.
KEY_ITEMS = {
    "Z": [
        ("pool", "Spawning Pool", 1), ("hatch2", "Hatchery", 1), ("hatch3", "Hatchery", 2),
        ("hatch4", "Hatchery", 3), ("gas1", "Extractor", 1), ("gas2", "Extractor", 2),
        ("ling", "Zergling", 1), ("ling_speed", "Metabolic Boost (Zergling Speed)", 1),
        ("lair", "Lair", 1), ("spire", "Spire", 1), ("muta", "Mutalisk", 1),
        ("den", "Hydralisk Den", 1), ("hydra", "Hydralisk", 1), ("lurker_aspect", "Lurker Aspect", 1),
        ("evo", "Evolution Chamber", 1), ("creep1", "Creep Colony", 1), ("queens_nest", "Queens Nest", 1),
        ("hive", "Hive", 1),
    ],
    "T": [
        ("rax1", "Barracks", 1), ("rax2", "Barracks", 2), ("rax3", "Barracks", 3),
        ("depot1", "Supply Depot", 1), ("gas1", "Refinery", 1), ("cc2", "Command Center", 1),
        ("cc3", "Command Center", 2), ("bunker", "Bunker", 1), ("ebay", "Engineering Bay", 1),
        ("turret", "Missile Turret", 1), ("academy", "Academy", 1), ("medic", "Medic", 1),
        ("stim", "Stim Packs", 1), ("range", "U-238 Shells (Marine Range)", 1),
        ("factory", "Factory", 1), ("factory2", "Factory", 2), ("shop", "Machine Shop", 1),
        ("vulture", "Vulture", 1), ("tank", "Siege Tank (Tank Mode)", 1), ("starport", "Starport", 1),
        ("valkyrie", "Valkyrie", 1), ("wraith", "Wraith", 1), ("science", "Science Facility", 1),
    ],
    "P": [
        ("pylon1", "Pylon", 1), ("gate1", "Gateway", 1), ("gate2", "Gateway", 2), ("forge", "Forge", 1),
        ("cannon", "Photon Cannon", 1), ("nexus2", "Nexus", 1), ("gas1", "Assimilator", 1),
        ("core", "Cybernetics Core", 1), ("goon", "Dragoon", 1), ("stargate", "Stargate", 1),
        ("corsair", "Corsair", 1), ("citadel", "Citadel of Adun", 1), ("archives", "Templar Archives", 1),
        ("dt", "Dark Templar", 1), ("robo", "Robotics Facility", 1), ("reaver", "Reaver", 1),
    ],
}
LEVEL_WINDOW_S = {"opening": 4 * 60, "tech": 8 * 60}
STRUCTURE_KINDS = {"build", "building_morph"}


def data_root() -> Path:
    return Path(os.environ.get("GARY_DATA", REPO_ROOT / "data"))


def mmss(s: float) -> str:
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


def first_times(items: list[dict], race: str, window: int) -> dict[str, float]:
    """Time of each key item's n-th occurrence within the window."""
    seen = Counter()
    times: dict[str, float] = {}
    wanted = {(name, n): feat for feat, name, n in KEY_ITEMS[race]}
    for i in items:
        if i["conf"] not in ("confirmed", "ordered") or i["t"] > window:
            continue
        seen[i["name"]] += 1
        feat = wanted.get((i["name"], seen[i["name"]]))
        if feat and feat not in times:
            times[feat] = i["t"]
    return times


def structure_order(items: list[dict], window: int, n: int = 6) -> tuple[str, ...]:
    """First n distinct structure types in order (repeats of the same type collapsed)."""
    seq: list[str] = []
    for i in items:
        if i["kind"] in STRUCTURE_KINDS and i["conf"] in ("confirmed", "ordered") and i["t"] <= window:
            if not seq or seq[-1] != i["name"]:
                seq.append(i["name"])
            if len(seq) == n:
                break
    return tuple(seq)


def load_rows(matchup: str, race: str) -> list[dict]:
    path = data_root() / "interim" / "build_orders.jsonl"
    if not path.exists():
        sys.exit("no build orders yet: run ingest/build_orders.py first")
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["matchup"] == matchup and r["race"] == race and r["duration_s"] >= 4 * 60:
                rows.append(r)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--matchup", default="TvZ")
    ap.add_argument("--race", required=True, choices=sorted(KEY_ITEMS))
    ap.add_argument("--level", default="tech", choices=sorted(LEVEL_WINDOW_S))
    ap.add_argument("--min-cluster", type=int, default=200, help="HDBSCAN min_cluster_size")
    ap.add_argument("--min-samples", type=int, default=20, help="HDBSCAN min_samples (lower = less noise)")
    ap.add_argument("--tree-depth", type=int, default=4)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    window = LEVEL_WINDOW_S[args.level]
    never = window + 60  # "didn't happen in the window" sits just past the window
    feats = [f for f, _, _ in KEY_ITEMS[args.race]]
    rows = load_rows(args.matchup, args.race)
    times = [first_times(r["items"], args.race, window) for r in rows]
    # drop features almost nobody reaches in this window; they only add noise
    present = {f: sum(f in t for t in times) / len(times) for f in feats}
    feats = [f for f in feats if present[f] >= 0.02]
    X = np.array([[t.get(f, never) for f in feats] for t in times], dtype=float) / 60.0
    print(f"{len(rows)} {args.race} player-games in {args.matchup}; features: {', '.join(feats)}")

    labels = HDBSCAN(min_cluster_size=args.min_cluster, min_samples=args.min_samples, copy=True).fit_predict(X)
    clusters = sorted(set(labels) - {-1}, key=lambda c: -(labels == c).sum())
    print(f"{len(clusters)} clusters, {np.mean(labels == -1):.0%} noise")

    out_dir = data_root() / "interim" / "taxonomy"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{args.matchup}_{args.race}_{args.level}"
    md = [f"# {args.matchup} {args.race} {args.level} clusters (window {mmss(window)})", "",
          f"{len(rows)} player-games, {len(clusters)} clusters, {np.mean(labels == -1):.0%} unclustered.", ""]
    assignments = {}
    for rank, c in enumerate(clusters, 1):
        idx = np.where(labels == c)[0]
        members = [rows[i] for i in idx]
        won = [m["won"] for m in members if m["won"] is not None]
        md += [f"## Cluster {rank} ({len(idx)} games, {len(idx) / len(rows):.1%}, "
               f"win rate {np.mean(won):.0%})", ""]
        md += ["| item | present | median time | p10 – p90 |", "|---|---|---|---|"]
        for j, f in enumerate(feats):
            col = X[idx, j] * 60
            hit = col < never
            if hit.mean() < 0.05:
                continue
            md.append(f"| {f} | {hit.mean():.0%} | {mmss(np.median(col[hit]))} | "
                      f"{mmss(np.percentile(col[hit], 10))} – {mmss(np.percentile(col[hit], 90))} |")
        orders = Counter(structure_order(m["items"], window) for m in members)
        md += ["", "Most common building orders:", ""]
        for seq, n in orders.most_common(3):
            md.append(f"- {n / len(idx):.0%}: {' → '.join(seq)}")
        md += ["", "Examples: " + ", ".join(f"`{m['rel_path']}`" for m in members[:3]), ""]
        for m in members:
            assignments[f"{m['rel_path']}|{m['player']}"] = rank

    if clusters:
        mask = labels != -1
        names = {c: rank for rank, c in enumerate(clusters, 1)}
        tree = DecisionTreeClassifier(max_depth=args.tree_depth, min_samples_leaf=50, random_state=0)
        tree.fit(X[mask], [names[c] for c in labels[mask]])
        acc = tree.score(X[mask], [names[c] for c in labels[mask]])
        rules = export_text(tree, feature_names=[f"{f}_min" for f in feats], decimals=1)
        md += ["## Readable rules", "",
               f"Depth-{args.tree_depth} decision tree reproducing the clusters ({acc:.0%} agreement). "
               f"Times in minutes; a value above {never / 60:.0f} means the item wasn't made in the window.",
               "", "```", rules, "```", ""]
        print(f"rule agreement: {acc:.0%}")

    tree_counts = Counter(structure_order(r["items"], window, n=4) for r in rows)
    md += ["## Opening tree (first 4 building types)", ""]
    for seq, n in tree_counts.most_common(15):
        md.append(f"- {n:>5} ({n / len(rows):.1%}): {' → '.join(seq)}")

    (out_dir / f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (out_dir / f"{stem}.json").write_text(json.dumps(
        {"matchup": args.matchup, "race": args.race, "level": args.level, "window_s": window,
         "features": feats, "assignments": assignments}, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out_dir / (stem + '.md')}")


if __name__ == "__main__":
    main()

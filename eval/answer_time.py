"""How soon the Terran answers the Zerg's tech (docs/REFOCUS.md §3.3, Phase 1 step 7a: answers.py off, does the macro
model answer alone?), per the Zerg's plan by the pros' rule (taxonomy/label_all.py zerg_plan), from the replays' build
items (ingest/build_orders.py: when each was ordered), for Gary's rounds and the modern pros on the ladder maps.

Written before step 7a's games (2026-11-24): the Zerg's tech is the Spire ordered (a spire-first plan) or Lurker
Aspect researched (lurker first); the answers, each the first ordered from 4:00 on, in seconds from the tech (negative:
before it):
  against the Spire   the first Missile Turret; the turrets ordered by 150 s after the Spire (its 80 s and a mutalisk's 28 s, and
                      their flight)
  against lurkers     the first detection (a ComSat, a Science Vessel or a Missile Turret); the first ComSat; Siege Mode
Added after step 7a's games (not written before them): the turrets ordered within 10 minutes of the tech (answers.py
vetoes turrets beyond one a base), and against lurkers the first Science Vessel.
Never within 10 minutes of the tech (or before the game's end): "never", apart.

    python -m eval.answer_time --rounds SC291a9 SC291a1 SC291a0 SC291a4 --pros
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
import tempfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))
sys.path.insert(0, str(REPO / "taxonomy"))

from eval import monitor, priority  # noqa: E402

FROM_S = 240                       # s: answers counted from 4:00
WITHIN_S = 600                     # s: after the tech, at most
TURRETS_BY_S = 150                 # s after the Spire
DETECT = ("ComSat", "Comsat Station", "Science Vessel", "Missile Turret")


def first_after(items: list[dict], names, t0: float) -> float | None:
    """Seconds from t0 to the first of names ordered from FROM_S (None: none within WITHIN_S)."""
    ts = [it["t"] for it in items if it["name"] in names and it["t"] >= FROM_S and it["t"] - t0 <= WITHIN_S]
    return min(ts) - t0 if ts else None


def turrets_within(items: list[dict], t0: float, duration_s: float) -> int | None:
    """Missile Turrets ordered from FROM_S to WITHIN_S after t0 (None: the game ended before)."""
    if duration_s < t0 + WITHIN_S:
        return None
    return sum(1 for it in items if it["name"] == "Missile Turret" and FROM_S <= it["t"] <= t0 + WITHIN_S)


def measure(t_items: list[dict], z_items: list[dict], duration_s: float) -> dict | None:
    """One game: the Zerg's plan and the answers' delays."""
    from label_all import zerg_plan
    plan = zerg_plan({"items": z_items, "duration_s": duration_s}, "TvZ")
    tech = plan.split(",")[-1].strip() if plan and "," in plan else plan
    if tech == "spire first":
        t0 = next((it["t"] for it in z_items if it["name"] == "Spire"), None)
        if t0 is None:
            return None
        return {"plan": plan, "tech": tech, "t0": t0, "left_s": duration_s - t0,
                "turret": first_after(t_items, ("Missile Turret",), t0),
                "turrets_by": sum(1 for it in t_items if it["name"] == "Missile Turret" and FROM_S <= it["t"] <= t0 + TURRETS_BY_S),
                "turrets_10m": turrets_within(t_items, t0, duration_s)}
    if tech == "lurker first":
        t0 = next((it["t"] for it in z_items if it["name"] == "Lurker Aspect"), None)
        if t0 is None:
            return None
        return {"plan": plan, "tech": tech, "t0": t0, "left_s": duration_s - t0,
                "detect": first_after(t_items, DETECT, t0), "comsat": first_after(t_items, ("ComSat", "Comsat Station"), t0),
                "siege": first_after(t_items, ("Tank Siege Mode",), t0),
                "vessel": first_after(t_items, ("Science Vessel",), t0), "turrets_10m": turrets_within(t_items, t0, duration_s)}
    return {"plan": plan, "tech": tech}


def gary_game(rep: str):
    from build_orders import extract_player
    from cmdcache import P, load_game
    from inventory import find_screp
    game = load_game(find_screp(None), Path(rep), hashlib.sha1(rep.encode()).hexdigest(),
                     Path(tempfile.gettempdir()) / "gary_answer_cmds")
    ps = {p["race"]: p for p in game["players"] if not p["observer"]}
    if "T" not in ps or "Z" not in ps:
        return None
    items = {r: extract_player([c for c in game["cmds"] if c[P] == ps[r]["id"]], r)[0] for r in "TZ"}
    dur = max((it["t"] for r in "TZ" for it in items[r]), default=0)
    return measure(items["T"], items["Z"], dur)


def pro_games() -> list[dict]:
    from inventory import data_root
    from eval.league import ladder_maps
    import re
    base = {re.sub(r"[^a-z]", "", m.lower().split(" ")[0]) for m in ladder_maps()}
    by = defaultdict(dict)
    for line in open(data_root() / "interim" / "build_orders.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("matchup") != "TvZ" or r.get("source") != "cwal":
            continue
        if not any(b in re.sub(r"[^a-z]", "", str(r.get("map", "")).lower()) for b in base):
            continue
        by[r["rel_path"]][r["race"]] = r
    out = []
    for rows in by.values():
        if "T" in rows and "Z" in rows:
            m = measure(rows["T"]["items"], rows["Z"]["items"], rows["T"]["duration_s"])
            if m is not None:
                out.append(m)
    return out


def report(name: str, games: list[dict]) -> None:
    def cell(vals, n_running):
        got = [v for v in vals if v is not None]
        return (f"median {np.median(got):+.0f} s (n {len(got)}), never {sum(v is None for v in vals)} of {n_running}"
                if got else f"never {len(vals)} of {n_running}")
    def tens(gs):
        v = [g["turrets_10m"] for g in gs if g.get("turrets_10m") is not None]
        return (f"turrets within {WITHIN_S // 60} min of the tech median {np.median(v):.0f} (n {len(v)}, "
                f"{', '.join(str(x) for x in sorted(v)) if len(v) <= 12 else 'quartiles ' + ' '.join(f'{q:.0f}' for q in np.percentile(v, [25, 75]))})"
                if v else "turrets within the window: no game ran long enough")
    sp = [g for g in games if g.get("tech") == "spire first" and g.get("left_s", 0) >= TURRETS_BY_S]
    lu = [g for g in games if g.get("tech") == "lurker first" and g.get("left_s", 0) >= 60]
    print(f"{name}: {len(games)} games ({len(sp)} spire first, {len(lu)} lurker first running past their tech)")
    if sp:
        print(f"  against the Spire: first turret {cell([g['turret'] for g in sp], len(sp))}; turrets by "
              f"{TURRETS_BY_S} s after it, median {np.median([g['turrets_by'] for g in sp]):.0f} "
              f"(none {np.mean([g['turrets_by'] == 0 for g in sp]):.0%}); {tens(sp)}")
        for plan in sorted({g["plan"] for g in sp}):
            q = [g for g in sp if g["plan"] == plan]
            print(f"    {plan} ({len(q)}): first turret {cell([g['turret'] for g in q], len(q))}, turrets by "
                  f"{np.median([g['turrets_by'] for g in q]):.0f}")
    if lu:
        print(f"  against lurkers: first detection {cell([g['detect'] for g in lu], len(lu))}; first ComSat "
              f"{cell([g['comsat'] for g in lu], len(lu))}; Siege Mode {cell([g['siege'] for g in lu], len(lu))}; Science Vessel "
              f"{cell([g['vessel'] for g in lu], len(lu))}; {tens(lu)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", nargs="*", default=[])
    ap.add_argument("--label", help="the rounds' name in the report")
    ap.add_argument("--pros", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    if args.rounds:
        reps = [p for r in args.rounds for p in sorted(glob.glob(str(REPO / "runs" / "league" / r / "*" / "*.rep")))]
        with ProcessPoolExecutor(args.workers) as pool:
            games = [g for g in monitor.track(pool.map(gary_game, reps), len(reps), "games") if g is not None]
        report(args.label or " ".join(args.rounds), games)
    if args.pros:
        report("the modern TvZ pros on the ladder maps", pro_games())


if __name__ == "__main__":
    main()

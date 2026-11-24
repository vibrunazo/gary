"""Does Gary time its attacks to Stim Packs and +1 Infantry Weapons as the pros do? (docs/REFOCUS.md §3.4 and §5.1, an
offline audit at 0 games, before any upgrade-timing criterion; the commit model gets no research state,
gary/policy/army.py.) TvZ, the Terran.

Attacks are eval/attacks.py's (ATTACK_N fighters near a Zerg building after a quiet spell). An upgrade is done at its
order (the replay's commands, ingest/build_orders.py) plus its research time (DONE_AFTER, game seconds at fastest). Per
game: when each was done, the first attack after 5:00, and every attack's start against the upgrade: before it, within
WINDOW after it, or later.

    python -m eval.upgrade_timing --gary RD285a HS284a --pros 150
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

from eval import monitor, priority  # noqa: E402

DONE_AFTER = {"Stim Packs": 1200 / 24, "Terran Infantry Weapons": 4000 / 24}   # s: the research's time
WINDOW = 60                     # s: an attack this soon after the upgrade is "on it"
FROM = 5 * 60                   # s: attacks from here (earlier ones are rushes and defenses at the natural)


def _done(items: list[dict]) -> dict[str, float | None]:
    out = {}
    for name, after in DONE_AFTER.items():
        t = next((i["t"] for i in items if i["name"] == name and i["conf"] in ("confirmed", "ordered")), None)
        out[name] = t + after if t is not None else None
    return out


def _game(job: tuple):
    from eval.attacks import attacks
    path, items = job
    if items is None:
        from build_orders import extract_player
        from cmdcache import P, load_game
        from inventory import find_screp
        game = load_game(find_screp(None), Path(path), hashlib.sha1(path.encode()).hexdigest(),
                         Path(tempfile.gettempdir()) / "gary_upgrade_cmds")
        t = next((p for p in game["players"] if not p["observer"] and p["race"] == "T"), None)
        if t is None:
            return None
        items = extract_player([c for c in game["cmds"] if c[P] == t["id"]], "T")[0]
    a = attacks(path)
    if a is None:
        return None
    return {"done": _done(items), "attacks": [x["minute"] * 60 for x in a]}


def summary(name: str, games: list[dict]) -> dict:
    res = {"games": len(games)}
    print(f"\n{name}: {len(games)} games")
    for up in DONE_AFTER:
        done = [g["done"][up] for g in games if g["done"][up] is not None]
        rel = [a - g["done"][up] for g in games if g["done"][up] is not None for a in g["attacks"] if a >= FROM]
        nod = sum(1 for g in games if g["done"][up] is None)
        first = [min([a for a in g["attacks"] if a >= FROM] or [np.nan]) - g["done"][up]
                 for g in games if g["done"][up] is not None]
        first = [x for x in first if not np.isnan(x)]
        rel = np.array(rel)
        on = float(np.mean((rel >= 0) & (rel <= WINDOW))) if len(rel) else float("nan")
        before = float(np.mean(rel < 0)) if len(rel) else float("nan")
        print(f"  {up}: done in {len(done)} of {len(games)} (median {np.median(done) / 60 if done else float('nan'):.2f} min); "
              f"attacks from 5:00: {len(rel)}, before it {before:.0%}, within {WINDOW} s after {on:.0%}; first attack from "
              f"5:00 minus done: median {np.median(first) if first else float('nan'):+.0f} s (quartiles "
              f"{np.percentile(first, 25) if first else float('nan'):+.0f} to {np.percentile(first, 75) if first else float('nan'):+.0f})")
        res[up] = {"done_in": len(done), "never": nod, "done_min": float(np.median(done) / 60) if done else None,
                   "attacks": int(len(rel)), "before": before, "within": on,
                   "first_minus_done_s": float(np.median(first)) if first else None}
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gary", nargs="*", default=[], help="league rounds (the Terran's side)")
    ap.add_argument("--pros", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out")
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    sets = []
    for r in args.gary:
        sets.append((r, [(str(p), None) for p in sorted((REPO / "runs" / "league" / r).rglob("*.rep"))]))
    if args.pros:
        from inventory import data_root
        from eval.humanlike import clean_replays
        clean = clean_replays()
        recs = [json.loads(l) for l in open(data_root() / "interim" / "build_orders.jsonl", encoding="utf-8")]
        recs = [r for r in recs if r.get("matchup") == "TvZ" and r.get("race") == "T" and r.get("source") == "cwal"
                and r["rel_path"] in clean and r.get("duration_s", 0) >= 600]
        random.Random(0).shuffle(recs)
        sets.append(("pros", [(str(data_root() / "raw" / r["rel_path"]), r["items"]) for r in recs[:args.pros]]))
    out = {}
    with ProcessPoolExecutor(args.workers) as pool:
        for name, jobs in sets:
            games = [g for g in monitor.track(pool.map(_game, jobs), len(jobs), name) if g is not None]
            out[name] = summary(name, games)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

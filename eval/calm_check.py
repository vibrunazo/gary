"""The calm layer's measures (gary/agent/calm.py; docs/PROGRESS.md 2026-11-18), a league round's side against the pros'
games of its matchup, re-simulated, over a time window (5-10 minutes by default):
  standing        the share of fighter samples (every 2 s, Medics left out) standing (Guard, PlayerGuard)
  long            the share of standing time in stretches of 30 s or more
  short/min       new point orders (move, attack-move) a calm fighter a minute given while it stood, under the army
                  data's reach (gary/policy/calm.py MOVED cells): what the calm layer owns (the pros 2.0, gt1dev 0.5)
  far/min         the same beyond it (the commit model's)
  first rest      a new fighter's first stand (at its rally) before its next order: median seconds, share over 30 s
Calm: no enemy fighter within CALM_SIGHT. Sampled every 8 frames for the orders (a new order: its order or target
changed), every 48 for the rest.

    python -m eval.calm_check --round runs/league/NF279a --race T --pros 40
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

STANDING = {2, 3}
MOVING = {6, 14}


def _job(job: tuple) -> dict | None:
    path, race, t0, t1 = job
    from eval.humanlike import FIGHTERS_ANY, NEUTRAL, RACES
    from gary.env import Game
    from gary.policy.calm import CALM_SIGHT, MOVED, army_cell
    R = RACES[race]
    try:
        g = Game.scenario(path)
    except Exception:
        return None
    out = {"samples": 0, "standing": 0, "calm8": 0, "short": 0, "far": 0, "runs": [], "rests": []}
    prev, slot, run, first, rested = {}, None, {}, {}, set()
    try:
        while g.frame + 8 <= t1:
            g.step(8)
            o = g.observe()
            units = o["units"]
            if slot is None:
                owners = sorted({u["owner"] for u in units if u["type"] in R["halls"]})
                slot = owners[0] if owners else None
            if slot is None or g.frame < t0:
                continue
            mw, mh = o["map"]["w"], o["map"]["h"]
            foes = np.array([(u["x"], u["y"]) for u in units if u["owner"] not in (slot, NEUTRAL)
                             and u["type"] in FIGHTERS_ANY] or [(1e9, 1e9)], np.float64)
            mine = [u for u in units if u["owner"] == slot and u["completed"] and u["type"] in R["fighters"]
                    and R["fighters"][u["type"]] != "medic"]
            sample = g.frame % 48 < 8
            for u in mine:
                t = u["tag"]
                calm = np.sqrt(((foes - (u["x"], u["y"])) ** 2).sum(1)).min() > CALM_SIGHT
                key = (u["order"], u["tx"], u["ty"])
                was = prev.get(t)
                if calm:
                    out["calm8"] += 1
                    if was is not None and was[0] in STANDING and u["order"] in MOVING and key != was:
                        a, b = army_cell(u["tx"], u["ty"], mw, mh), army_cell(u["x"], u["y"], mw, mh)
                        out["short" if max(abs(a[0] - b[0]), abs(a[1] - b[1])) < MOVED else "far"] += 1
                prev[t] = key
                if sample:
                    first.setdefault(t, g.frame)
                    idle = u["order"] in STANDING
                    out["samples"] += 1
                    out["standing"] += idle
                    if idle:
                        run[t] = run.get(t, 0) + 2
                    elif t in run:
                        out["runs"].append(run.pop(t))
                    if first[t] > t0 + 48 and t not in rested:          # (new in the window: its first rest)
                        if idle:
                            rested.add(t)
                            out.setdefault("resting", {})[t] = g.frame
                    if t in out.get("resting", {}) and not idle:
                        out["rests"].append((g.frame - out["resting"].pop(t)) / 24)
    except Exception:
        pass
    out["runs"] += list(run.values())
    out["rests"] += [(g.frame - f) / 24 for f in out.pop("resting", {}).values()]
    return out


def summary(name: str, res: list[dict]) -> None:
    n = sum(r["samples"] for r in res)
    c8 = sum(r["calm8"] for r in res)
    runs = np.array([x for r in res for x in r["runs"]] or [0])
    rests = np.array([x for r in res for x in r["rests"]] or [np.nan])
    per = lambda k: sum(r[k] for r in res) / max(1, c8) * (1440 / 8)
    print(f"{name} ({len(res)} games): standing {sum(r['standing'] for r in res) / max(1, n):.2f}; long "
          f"{runs[runs >= 30].sum() / max(1, runs.sum()):.2f}; short/min {per('short'):.2f}, far/min {per('far'):.2f}; "
          f"first rest median {np.nanmedian(rests):.0f} s, over 30 s {np.nanmean(rests >= 30):.2f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--round", nargs="+", required=True, help="league round folders (their side A's replays)")
    ap.add_argument("--race", default="T")
    ap.add_argument("--matchup", default="TvZ")
    ap.add_argument("--pros", type=int, default=40, help="the pros' games (0: none)")
    ap.add_argument("--start", type=float, default=5)
    ap.add_argument("--end", type=float, default=10)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    from eval import priority
    priority.apply("low")
    t0, t1 = int(args.start * 1440), int(args.end * 1440)
    with ProcessPoolExecutor(args.workers) as pool:
        for rnd in args.round:
            reps = sorted(str(p) for p in Path(rnd).rglob("*.rep"))
            summary(Path(rnd).name, [r for r in pool.map(_job, [(p, args.race, t0, t1) for p in reps]) if r])
        if args.pros:
            from inventory import data_root
            tag = "" if args.matchup == "TvZ" else f"_{args.matchup}"
            cache = data_root() / "interim" / "humanlike" / f"pro_{args.race}{tag}_modern_30min.jsonl"
            have = [json.loads(line)["rel_path"].split("#")[0] for line in open(cache, encoding="utf-8")]
            random.Random(0).shuffle(have)
            jobs = [(str(data_root() / "raw" / p), args.race, t0, t1) for p in have[:args.pros]]
            summary("pros", [r for r in pool.map(_job, jobs) if r])


if __name__ == "__main__":
    main()

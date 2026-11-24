"""Strict drills graded against their card (docs/REFOCUS.md Phase 1 gate 2, G3: ">= 18/20 unharassed strict drills
within a timing tolerance written before the drills"; step 8).

The tolerance, written 2026-11-24 before any drill was played: a milestone (the card's item and count) is met when
Gary's own order of it (the replay's commands, gary/agent/strategy.py replay_items: its one-offs, the whole game) lands within
max(its tol, TOL_FLOOR) of its time t, both on the replay's clock; tol is the card's own, the style's pros' 90th
percentile of distance from t (a pro misses one in ten). A drill passes when every milestone of its card is met. The
card is the round's told style's (manifest option told<N>), or a StrategySpec's (--spec).

    python -m eval.drills --rounds DR295a1 DR295a2 DR295a3
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

TOL_FLOOR = 15.0           # s: the hands' grain (a builder sent, the camera there)


def grade(items: list[dict], card: list[dict]) -> list[dict]:
    have = {(i["item"], i["n"]): i["t"] for i in items}
    out = []
    for m in card:
        t = have.get((m["item"], m["n"]))
        tol = max(m["tol"], TOL_FLOOR)
        out.append({"item": m["item"], "n": m["n"], "card_t": m["t"], "tol": tol, "t": t,
                    "delta": None if t is None else round(t - m["t"], 1),
                    "met": t is not None and abs(t - m["t"]) <= tol})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", nargs="+", required=True)
    ap.add_argument("--spec", help="a StrategySpec's JSON (its card), for every game, over the told style's")
    args = ap.parse_args()
    from gary.agent.strategy import StrategySpec, from_style, replay_items
    spec = StrategySpec.load(args.spec) if args.spec else None
    drills, by_item = [], {}
    for rnd in args.rounds:
        meta = json.loads((REPO / "runs" / "league" / rnd / "round.json").read_text(encoding="utf-8"))
        told = re.search(r"\+told(\d+)", meta["terran"])
        card = list(spec.card) if spec else (list(from_style("TvZ", "T", int(told.group(1))).card) if told else [])
        for rep in sorted(glob.glob(str(REPO / "runs" / "league" / rnd / "*" / "*.rep"))):
            _, _, items = replay_items(rep, None, "T", by_s=None)
            g = grade(items, card)
            ok = all(m["met"] for m in g)
            drills.append(ok)
            miss = [f"{m['item']} #{m['n']} {'never' if m['t'] is None else f'{m['delta']:+.0f}s'} (tol {m['tol']:.0f})"
                    for m in g if not m["met"]]
            print(f"  {rnd} {Path(rep).parent.name[:16]:16s} {'PASS' if ok else 'fail'} {sum(m['met'] for m in g)}/{len(g)}"
                  + (f": {'; '.join(miss)}" if miss else ""))
            for m in g:
                k = f"{m['item']} #{m['n']}"
                by_item.setdefault(k, []).append(m)
    print(f"drills passed: {sum(drills)}/{len(drills)} (gate 2: at least 18 of 20)")
    for k, ms in by_item.items():
        d = sorted(m["delta"] for m in ms if m["delta"] is not None)
        print(f"  {k:32s} met {sum(m['met'] for m in ms)}/{len(ms)}, delta median "
              f"{d[len(d) // 2] if d else None} s, never {sum(m['t'] is None for m in ms)}")


if __name__ == "__main__":
    main()

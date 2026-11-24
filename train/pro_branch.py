"""The pros' conditional choice frequencies for the strategic trunk's branches (docs/REFOCUS.md §3.2, Phase 1 step 7b):
P_pro(branch | belief, context), what pros do, kept apart from how their games ended (printed, never decided on).

One branch so far, PREP_VS_LURKER (TvZ, the Terran): at a moment where the pro has not started Siege Mode, does the
pro start it within WINDOW_S? Written before the table was read (2026-11-24):
  the belief     the plan belief's cross-fitted odds of a lurker-first tech (train/plan_belief.py --oof: a fold that never
                 saw the game, never the retrospective label), in BUCKETS
  looked         Gate 1's split (train/plan_belief.py is_looked, the sighting states of ingest/sighting_dataset.py)
  own state      STAGES: no Factory, a Factory and no Machine Shop, a Machine Shop (Siege Mode needs one; a pro without
                 one is not about to research it, whatever they believe)
  the minute     MINUTES' bounds
A cell needs MIN_N modern games; with fewer, the BACKOFF's next parent (the minute dropped, then the looked state, then
the own state), each level's n printed. The trunk activates the branch where P_pro >= THRESHOLD (gary/agent/trunk.py)
and, revised after the table was read and before the rule was run over any of Gary's games (2026-11-24), where the
cell's interval is clear of its CONTRAST's (the same cell with the belief under 0.2, at the same backoff level): a pro
with a Machine Shop researches Siege Mode by 8-10 minutes whatever the Zerg went (0.58 of 795 games with P(lurker)
under 0.2), so P_pro alone would start PREP_VS_LURKER against mutalisks; the contrast keeps the part of the choice the
belief makes.
The pros' moments are every 30 s from 2:30 to 10:00 (the belief's samples), a game counted once per cell for n.

    python -m train.pro_branch --oof runs/plan_belief/TvZ_T_oof_20261124/oof.npz
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

WINDOW_S = 120
BUCKETS = (0.2, 0.5, 0.8)                 # P(lurker first): <0.2, 0.2-0.5, 0.5-0.8, >=0.8
MINUTES = (360, 480)                      # s: before 6:00, 6:00-8:00, 8:00-10:00
MIN_N = 25
THRESHOLD = 0.5
CONTRAST = {"belief": 0}                  # the cell the branch's P_pro must clear (its interval above this one's)
BACKOFF = (("belief", "looked", "stage", "minute"), ("belief", "looked", "stage"), ("belief", "stage"), ("belief",))
STAGES = ("no Factory", "Factory", "Machine Shop")
BRANCH = "PREP_VS_LURKER"
TECH = "lurker first"
CHAIN = {"Factory": "Factory", "Machine Shop": "Machine Shop", "siege": "Tank Siege Mode"}


def bucket(p: float) -> int:
    return int(np.searchsorted(BUCKETS, p, side="right"))


def minute_of(t: float) -> int:
    return int(np.searchsorted(MINUTES, t, side="right"))


def stage_of(have: dict, t: float) -> int:
    if have.get("Machine Shop", 1e9) <= t:
        return 2
    return 1 if have.get("Factory", 1e9) <= t else 0


def key_of(fields: dict, level: tuple) -> str:
    return "|".join(f"{k}={fields[k]}" for k in level)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--oof", required=True, help="train/plan_belief.py --oof's oof.npz")
    ap.add_argument("--matchup", default="TvZ")
    ap.add_argument("--race", default="T")
    ap.add_argument("--out")
    args = ap.parse_args()
    from inventory import data_root
    from gary.policy.plan_belief import is_looked
    from train.plan_belief import parts
    d = np.load(args.oof, allow_pickle=True)
    names = [str(n) for n in d["names"]]
    lurk = np.array([parts(n)[2] == TECH for n in names])
    p_lurk = d["odds"][:, lurk].sum(1)
    sd = np.load(data_root() / "interim" / "sightings" / f"{args.matchup}_{args.race}.npz")
    looked = {(str(r), int(s), int(t)): is_looked(f) for r, s, t, f in zip(sd["rel_path"], sd["slot"], sd["t"], sd["features"])}
    games = {}
    for line in open(data_root() / "interim" / "build_orders.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("matchup") != args.matchup or r.get("race") != args.race or r.get("source") != "cwal":
            continue
        have = {}
        for it in r["items"]:
            for k, name in CHAIN.items():
                if it["name"] == name and k not in have:
                    have[k] = it["t"]
        games[r["rel_path"]] = (have, bool(r.get("won")))
    cells = defaultdict(lambda: {"rows": 0, "yes": 0, "games": set(), "won_yes": [0, 0], "won_no": [0, 0]})
    used, skipped = 0, defaultdict(int)
    for rel, slot, t, p in zip(d["rel_path"], d["slot"], d["t"], p_lurk):
        rel, slot, t = str(rel), int(slot), int(t)
        if rel not in games:
            skipped["no build order"] += 1
            continue
        if (rel, slot, t) not in looked:
            skipped["no sighting state"] += 1
            continue
        have, won = games[rel]
        if have.get("siege", 1e9) <= t:
            continue                                   # (Siege Mode started already: no branch left to take)
        yes = t < have.get("siege", 1e9) <= t + WINDOW_S
        fields = {"belief": bucket(float(p)), "looked": int(looked[(rel, slot, t)]), "stage": stage_of(have, t),
                  "minute": minute_of(t)}
        used += 1
        for level in BACKOFF:
            c = cells[key_of(fields, level)]
            c["rows"] += 1
            c["yes"] += int(yes)
            c["games"].add(rel)
            w = c["won_yes"] if yes else c["won_no"]
            w[0] += int(won)
            w[1] += 1
    table = {}
    for k, c in cells.items():
        n = len(c["games"])
        p = c["yes"] / c["rows"]
        z = 1.96                                        # (Wilson, on games: rows of one game aren't independent)
        den = 1 + z * z / n
        mid = (p + z * z / (2 * n)) / den
        half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
        table[k] = {"p": round(p, 3), "lo": round(max(0.0, mid - half), 3), "hi": round(min(1.0, mid + half), 3),
                    "games": n, "rows": c["rows"],
                    "pro_won_if_taken": round(c["won_yes"][0] / c["won_yes"][1], 3) if c["won_yes"][1] else None,
                    "pro_won_if_not": round(c["won_no"][0] / c["won_no"][1], 3) if c["won_no"][1] else None}
    out = Path(args.out) if args.out else REPO / "runs" / "selector" / f"{args.matchup}_{args.race}_{BRANCH}_{time.strftime('%Y%m%d')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {"branch": BRANCH, "matchup": args.matchup, "race": args.race, "tech": TECH, "window_s": WINDOW_S,
            "buckets": BUCKETS, "minutes": MINUTES, "stages": STAGES, "min_n": MIN_N, "threshold": THRESHOLD,
            "contrast": CONTRAST,
            "backoff": BACKOFF, "oof": Path(args.oof).parent.name, "moments": used,
            "games": len({str(r) for r in d["rel_path"]} & set(games)), "skipped": dict(skipped)}
    out.write_text(json.dumps({"meta": meta, "cells": table}, indent=1), encoding="utf-8")
    print(f"{used} moments of {meta['games']} modern games (skipped {dict(skipped)}) -> {out}")
    blab = ["<0.2", "0.2-0.5", "0.5-0.8", ">=0.8"]
    mlab = ["<6:00", "6-8", "8-10"]
    for b in range(4):
        for st in range(3):
            for lk in (1, 0):
                row = []
                for mi in range(3):
                    c = table.get(key_of({"belief": b, "looked": lk, "stage": st, "minute": mi}, BACKOFF[0]))
                    row.append(f"{mlab[mi]} {c['p']:.2f} n{c['games']}" if c else f"{mlab[mi]} -")
                par = table.get(key_of({"belief": b, "looked": lk, "stage": st}, BACKOFF[1]))
                print(f"  P(lurker) {blab[b]:7s} {STAGES[st]:12s} {'looked' if lk else 'unlooked':8s}: " + "; ".join(row)
                      + (f" | all minutes {par['p']:.2f} n{par['games']} (pros won {par['pro_won_if_taken']} if taken, "
                         f"{par['pro_won_if_not']} if not)" if par else ""))


if __name__ == "__main__":
    main()

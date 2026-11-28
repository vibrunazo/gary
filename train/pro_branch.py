"""The pros' conditional choice frequencies for the strategic trunk's branches (docs/REFOCUS.md §3.2, Phase 1 step 7b):
P_pro(branch | belief, context), what pros do, kept apart from how their games ended (printed, never decided on).

One branch so far, PREP_VS_LURKER (TvZ, the Terran). Its event, revised 2026-11-24 after step 7b (the user's decision,
"matched, chain A only"): at a moment, does the pro start the next missing item of the first chain not yet had within
WINDOW_S? The chains, CHAINS: Factory -> Machine Shop -> Siege Mode, then Starport -> Science Facility -> Science Vessel
(counted only once Siege Mode is had). A moment with both chains had is no moment. (The event "either chain's next
item" was read first, 0 games: the vessel chain's next item comes at 0.90+ whatever the pro believes, so with the
matched contrast it took the branch in 1 of 4 lurker games of step 7a.) Until then the event was Siege Mode alone, so a pro without a Machine Shop never took the
branch whatever they believed, and Gary's own Factory gated the trunk's start (step 7b: Fighting Spirit looked at 6:03
with the belief at 0.65-0.73 and started at 8:36). The fields, written before the table was read:
  the belief     the plan belief's cross-fitted odds of a lurker-first tech (train/plan_belief.py --oof: a fold that never
                 saw the game, never the retrospective label), in BUCKETS
  looked         Gate 1's split (gary/policy/plan_belief.py is_looked, the sighting states of ingest/sighting_dataset.py)
  own state      a and b, how far along each chain the pro is (0 to 3 items had, in order: ordered, by the frame)
  the minute     MINUTES' bounds
A cell needs MIN_N modern games; with fewer, the BACKOFF's next parent (the minute dropped, then the looked state, then
chain b, then chain a), each level's n printed. The trunk activates the branch where P_pro >= THRESHOLD
(gary/agent/trunk.py) and where the cell's interval is clear of its CONTRAST's (the same cell with the belief under 0.2,
at the same backoff level; step 7b's revision: the base rate of a chain's next item is high late whatever the Zerg went,
and the contrast keeps the part of the choice the belief makes). Revised again before this table met any of Gary's games
(2026-11-24, CONTRAST_LEVEL "finest"): the contrast is the most specific low-belief cell with MIN_N games, walked down
the backoff on its own, not the one at the high-belief cell's level. High beliefs come late, so a pooled low-belief cell
is mostly the early minutes: looked, without a Factory or Starport at 6-8 minutes, the pooled low-belief cell is 0.45
and the matched one 0.90 (a Factory then is the base rate, not an answer to lurkers).
The pros' moments are every 30 s from 2:30 to 10:00 (the belief's samples, at frame 24 t), a game counted once per cell
for n. Items by their frames: the buildings and Siege Mode from the build orders, the Science Vessel from the raw Train
commands (the build orders keep units only to 8:00).

    python -m train.pro_branch --oof runs/plan_belief/TvZ_T_oof_20261124/oof.npz
    python -m train.pro_branch --oof runs/plan_belief/TvZ_T_oof_20261124/oof.npz --branch PREP_VS_MUTA --turret-caps

PREP_VS_MUTA (2026-11-28, docs/DIRECTIVES.md §7): the same fields and backoff, its belief the odds of the spire-first
plans, its own state the ring (BRANCHES, ring_position), its minutes by the minute to 6:30. --turret-caps adds the pros'
turrets by the minute under a lurker belief (PREP_VS_LURKER's turret cut) to the table's meta.
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
CONTRAST_LEVEL = "finest"                 # the contrast cell: the most specific with MIN_N games (else "same": its level)
BACKOFF = (("belief", "looked", "a", "b", "minute"), ("belief", "looked", "a", "b"), ("belief", "a", "b"),
           ("belief", "a"), ("belief",))
BRANCH = "PREP_VS_LURKER"
TECH = "lurker first"
CHAINS = (("Factory", "Machine Shop", "Siege Mode"), ("Starport", "Science Facility", "Science Vessel"))   # Gary's names
REPLAY_NAMES = {"Siege Mode": "Tank Siege Mode"}
# PREP_VS_MUTA (TvZ, the Terran; docs/DIRECTIVES.md §5, 2026-11-28): an Engineering Bay, then the mineral-line ring
# counted as the play side counts it, by turrets against the bases standing (no map geometry): one turret a base, then
# two. The ring's position at a moment: 0 no Engineering Bay, 1 fewer turrets than bases, 2 fewer than twice the bases,
# 3 the ring had; its event: the Engineering Bay (position 0) or a Missile Turret (1-2) ordered within WINDOW_S. The
# bases: the starting one and every Command Center ordered since (as eval/answer_time.py, from the build orders).
BRANCHES = {"PREP_VS_LURKER": {"tech": "lurker first", "kind": "chains"},
            "PREP_VS_MUTA": {"tech": "spire first", "kind": "ring",
                             # (by the minute to 6:00: the pros' Engineering Bay comes at a median 4:41, and a pooled "before
                             # 6:00" cell took the branch at the first sample, 2:30, in every game)
                             "minutes": (210, 270, 330, 390, 480)}}
RING = ("Engineering Bay", "Missile Turret x1 a base", "Missile Turret x2 a base")
TURRET_CAP_Q = 0.9                        # the pros' turrets by the minute under a lurker belief: this quantile
TURRET_CAP_BELIEF = 0.5                   # ...at P(lurker first) this high or more


def bucket(p: float) -> int:
    return int(np.searchsorted(BUCKETS, p, side="right"))


def minute_of(t: float) -> int:
    return int(np.searchsorted(MINUTES, t, side="right"))


def position(chain: tuple, have: dict, f: int) -> int:
    """Items of the chain had by frame f, in order (the index of its next missing item)."""
    k = 0
    while k < len(chain) and have.get(chain[k], 1e12) <= f:
        k += 1
    return k


def ring_position(g: dict, f: int) -> int:
    """PREP_VS_MUTA's position at frame f: 0 no Engineering Bay, 1 turrets under the bases, 2 under twice, 3 had."""
    if g.get("Engineering Bay", 1e12) > f:
        return 0
    bases = 1 + sum(1 for x in g["cc"] if x <= f)
    turrets = sum(1 for x in g["turrets"] if x <= f)
    return 1 if turrets < bases else 2 if turrets < 2 * bases else 3


def turret_caps(d, p_lurk, games: dict) -> dict:
    """The pros' Missile Turrets ordered by each minute at moments with P(lurker first) >= TURRET_CAP_BELIEF: the
    TURRET_CAP_Q quantile, the median and n games, by minute (PREP_VS_LURKER's turret cut, docs/DIRECTIVES.md §5.2)."""
    by = defaultdict(dict)                         # minute -> game -> turrets by then (a game counted once a minute)
    for rel, t, p in zip(d["rel_path"], d["t"], p_lurk):
        rel, t = str(rel), int(t)
        if rel in games and p >= TURRET_CAP_BELIEF:
            by[t // 60][rel] = sum(1 for x in games[rel]["turrets"] if x <= 24 * t)
    return {m: {"q": float(np.quantile(list(v.values()), TURRET_CAP_Q)), "median": float(np.median(list(v.values()))),
                "games": len(v)} for m, v in sorted(by.items()) if len(v) >= MIN_N}


def vessels(job):
    """The pro's first Science Vessel order (frame) from the raw commands, None if none or unreadable."""
    rel, sha1, name = job
    from cmdcache import F, N, P, T, load_game
    from inventory import data_root, find_screp
    try:
        game = load_game(find_screp(None), data_root() / "raw" / rel, sha1, data_root() / "interim" / "cmdcache")
    except Exception:  # noqa: BLE001
        return None
    pid = next((p["id"] for p in game["players"] if p["name"] == name and not p["observer"]), None)
    return min((c[F] for c in game["cmds"] if c[P] == pid and c[T] == "Train" and c[N] == "Science Vessel"), default=None)


def key_of(fields: dict, level: tuple) -> str:
    return "|".join(f"{k}={fields[k]}" for k in level)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--oof", required=True, help="train/plan_belief.py --oof's oof.npz")
    ap.add_argument("--matchup", default="TvZ")
    ap.add_argument("--race", default="T")
    ap.add_argument("--out")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--branch", default=BRANCH, choices=sorted(BRANCHES))
    ap.add_argument("--turret-caps", action="store_true", help="also the pros' turrets by the minute under a lurker belief")
    args = ap.parse_args()
    spec = BRANCHES[args.branch]
    tech = spec["tech"]
    minutes = spec.get("minutes", MINUTES)
    from inventory import data_root
    from gary.policy.plan_belief import is_looked
    from train.plan_belief import parts
    d = np.load(args.oof, allow_pickle=True)
    names = [str(n) for n in d["names"]]
    lurk = np.array([parts(n)[2] == "lurker first" for n in names])
    p_lurk = d["odds"][:, lurk].sum(1)
    p_branch = d["odds"][:, np.array([parts(n)[2] == tech for n in names])].sum(1)
    sd = np.load(data_root() / "interim" / "sightings" / f"{args.matchup}_{args.race}.npz")
    looked = {(str(r), int(s), int(t)): is_looked(f) for r, s, t, f in zip(sd["rel_path"], sd["slot"], sd["t"], sd["features"])}
    games, jobs, ring = {}, [], {}
    names = {REPLAY_NAMES.get(n, n): n for ch in CHAINS for n in ch}
    for line in open(data_root() / "interim" / "build_orders.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("matchup") != args.matchup or r.get("race") != args.race or r.get("source") != "cwal":
            continue
        have = {}
        for it in r["items"]:
            n = names.get(it["name"])
            if n is not None and n != "Science Vessel" and n not in have:
                have[n] = it["frame"]
        games[r["rel_path"]] = (have, bool(r.get("won")))
        built = [it for it in r["items"] if it.get("conf") in ("confirmed", "ordered")]
        ring[r["rel_path"]] = {"Engineering Bay": min((it["frame"] for it in built if it["name"] == "Engineering Bay"), default=1e12),
                               "turrets": sorted(it["frame"] for it in built if it["name"] == "Missile Turret"),
                               "cc": sorted(it["frame"] for it in built if it["name"] == "Command Center")}
        jobs.append((r["rel_path"], r["sha1"], r["player"]))
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(args.workers) as pool:
        for (rel, _, _), f in zip(jobs if spec["kind"] == "chains" else [], pool.map(vessels, jobs if spec["kind"] == "chains" else [], chunksize=16)):
            if f is not None:
                games[rel][0]["Science Vessel"] = f
    cells = defaultdict(lambda: {"rows": 0, "yes": 0, "games": set(), "won_yes": [0, 0], "won_no": [0, 0]})
    used, skipped = 0, defaultdict(int)
    for rel, slot, t, p in zip(d["rel_path"], d["slot"], d["t"], p_branch):
        rel, slot, t = str(rel), int(slot), int(t)
        if rel not in games:
            skipped["no build order"] += 1
            continue
        if (rel, slot, t) not in looked:
            skipped["no sighting state"] += 1
            continue
        have, won = games[rel]
        f = 24 * t
        if spec["kind"] == "ring":
            g = ring[rel]
            pos = [ring_position(g, f), 0]
            if pos[0] == len(RING):
                continue                               # (the ring had: no branch left to take)
            yes = f < g["Engineering Bay"] <= f + 24 * WINDOW_S if pos[0] == 0 else                 any(f < x <= f + 24 * WINDOW_S for x in g["turrets"])
        else:
            pos = [position(ch, have, f) for ch in CHAINS]
            if all(k == len(ch) for k, ch in zip(pos, CHAINS)):
                continue                               # (both chains had: no branch left to take)
            j = next(i for i, (k, ch) in enumerate(zip(pos, CHAINS)) if k < len(ch))     # (the first chain not had)
            yes = f < have.get(CHAINS[j][pos[j]], 1e12) <= f + 24 * WINDOW_S
        fields = {"belief": bucket(float(p)), "looked": int(looked[(rel, slot, t)]), "a": pos[0], "b": pos[1],
                  "minute": int(np.searchsorted(minutes, t, side="right"))}
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
    out = Path(args.out) if args.out else REPO / "runs" / "selector" / f"{args.matchup}_{args.race}_{args.branch}_{time.strftime('%Y%m%d')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {"branch": args.branch, "matchup": args.matchup, "race": args.race, "tech": tech, "window_s": WINDOW_S,
            "buckets": BUCKETS, "minutes": minutes, "chains": CHAINS if spec["kind"] == "chains" else (RING,),
            "event": "the next missing item of the first chain not had, started within window_s" if spec["kind"] == "chains"
            else "the Engineering Bay (position 0) or a Missile Turret (1-2) ordered within window_s; the ring counted by turrets "
            "against the bases standing", "min_n": MIN_N, "threshold": THRESHOLD,
            "contrast": CONTRAST, "contrast_level": CONTRAST_LEVEL,
            "backoff": BACKOFF, "oof": Path(args.oof).parent.name, "moments": used,
            "games": len({str(r) for r in d["rel_path"]} & set(games)), "skipped": dict(skipped)}
    if args.turret_caps:
        meta["turret_caps"] = {"belief": TURRET_CAP_BELIEF, "q": TURRET_CAP_Q, "by_minute": turret_caps(d, p_lurk, ring)}
        print("the pros' turrets by the minute at P(lurker first) >= %.1f: " % TURRET_CAP_BELIEF + "; ".join(
            f"{m}:00 q{TURRET_CAP_Q:.0%} {c['q']:.0f} (median {c['median']:.0f}, n {c['games']})" for m, c in meta["turret_caps"]["by_minute"].items()))
    out.write_text(json.dumps({"meta": meta, "cells": table}, indent=1), encoding="utf-8")
    print(f"{used} moments of {meta['games']} modern games (skipped {dict(skipped)}) -> {out}")
    blab = ["<0.2", "0.2-0.5", "0.5-0.8", ">=0.8"]
    edges = [150] + list(minutes) + [600]
    mlab = [f"{a // 60}:{a % 60:02d}-{b // 60}:{b % 60:02d}" for a, b in zip(edges, edges[1:])]
    for b in range(4):
        for a in range(4):
            for v in range(4):
                for lk in (1, 0):
                    row = []
                    for mi in range(len(mlab)):
                        c = table.get(key_of({"belief": b, "looked": lk, "a": a, "b": v, "minute": mi}, BACKOFF[0]))
                        row.append(f"{mlab[mi]} {c['p']:.2f} n{c['games']}" if c else f"{mlab[mi]} -")
                    par = table.get(key_of({"belief": b, "looked": lk, "a": a, "b": v}, BACKOFF[1]))
                    if par is None:
                        continue
                    print(f"  P({tech}) {blab[b]:7s} a{a} b{v} {'looked' if lk else 'unlooked':8s}: " + "; ".join(row)
                          + f" | all minutes {par['p']:.2f} n{par['games']} (pros won {par['pro_won_if_taken']} if taken, "
                            f"{par['pro_won_if_not']} if not)")

if __name__ == "__main__":
    main()

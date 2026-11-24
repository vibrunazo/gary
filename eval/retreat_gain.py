"""How far Gary's retreats get: each unit sent a retreat (the fight layer's draws, decisions.npz draws_<race>: role
"retreat" and sent "RETREAT"), the distance to the nearest enemy fighter when sent and LATER after, from the replay
re-played (gary.env Game.scenario). A unit sent again within LATER is counted once. Per round: the median gain in
tiles, the share 4 tiles or more (a pro's retreat label), the share nearer the enemy after.

    python -m eval.retreat_gain --rounds SU291a9 SU291a1 --race T
"""
from __future__ import annotations

import argparse
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from eval import monitor, priority  # noqa: E402

LATER = 48                    # frames (2 s)


def _game(job):
    from gary.env import Game
    from gary.policy.army import is_building, is_worker, supply_x2
    rep, race = job
    dec = Path(str(rep)[:-4] + ".decisions.npz")
    if not dec.exists():
        return None
    d = np.load(dec, allow_pickle=True)
    k = f"draws_{race.lower()}"
    if f"{k}/frame" not in d.files:
        return None
    fr, tg, role, sent = d[f"{k}/frame"], d[f"{k}/tag"], d[f"{k}/role"], d[f"{k}/sent"]
    events, last = [], {}
    for f, t, r, s in sorted(zip(fr.tolist(), tg.tolist(), role.tolist(), sent.tolist())):
        if r == "retreat" and s == "RETREAT" and f - last.get(t, -10 ** 9) > LATER:
            last[t] = f
            events.append((f, t))
    if not events:
        return []
    want = sorted({f for f, _ in events} | {f + LATER for f, _ in events})
    try:
        g = Game.scenario(str(rep))
    except Exception:
        return None
    seen = {}
    try:
        g.step(1)
        o = g.observe()
        hall = {106: "T", 131: "Z", 154: "P"}
        slot = next(u["owner"] for u in o["units"] if hall.get(u["type"]) == race)
        for f in want:
            if f > g.frame:
                g.step(f - g.frame)
            o = g.observe()
            units = {u["tag"]: u for u in o["units"] if u["owner"] == slot}
            foes = np.array([(u["x"], u["y"]) for u in o["units"] if u["owner"] not in (slot, 11)
                             and supply_x2(u["type"]) > 0 and not is_worker(u["type"]) and not is_building(u["type"])]
                            or [(1e9, 1e9)], np.float64)
            seen[f] = (units, foes)
    finally:
        g.close()
    out = []
    for f, t in events:
        a, b = seen.get(f), seen.get(f + LATER)
        if a is None or b is None or t not in a[0] or t not in b[0]:
            continue
        d0 = float(np.sqrt(((a[1] - (a[0][t]["x"], a[0][t]["y"])) ** 2).sum(1)).min())
        d1 = float(np.sqrt(((b[1] - (b[0][t]["x"], b[0][t]["y"])) ** 2).sum(1)).min())
        if d0 < 20 * 32 and d1 < 1e8:
            out.append((d1 - d0) / 32)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", nargs="+", required=True)
    ap.add_argument("--race", default="T")
    ap.add_argument("--workers", type=int, default=4)
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    jobs = [(p, args.race) for r in args.rounds for p in sorted((REPO / "runs" / "league" / r).rglob("*.rep"))]
    with ProcessPoolExecutor(args.workers) as pool:
        res = [x for x in monitor.track(pool.map(_game, jobs), len(jobs), "games") if x is not None]
    gain = np.array([x for g in res for x in g])
    if not len(gain):
        print("no retreats")
        return
    print(f"{' '.join(args.rounds)}: {len(gain)} retreats sent in {len(res)} games; 2 s later farther from the nearest "
          f"enemy fighter by a median {np.median(gain):.1f} tiles; 4 tiles or more {np.mean(gain >= 4):.0%}; nearer "
          f"{np.mean(gain < 0):.0%}")


if __name__ == "__main__":
    main()

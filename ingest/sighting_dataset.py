"""The sighting states for the enemy-plan belief (gary/policy/sightings.py): each pro game of the matchup re-simulated,
the player's view looked at every LOOK_EVERY frames, its SightingState's features at the plan belief's sample times
(train/plan_belief.py SAMPLE, FIRST, LAST). The re-simulator's snapshots have counts and no positions, so this re-plays
the replay (gary.env Game.scenario) for where the player's units stood.

    python -m ingest.sighting_dataset --race T --matchup TvZ --era modern
Output: data/interim/sightings/<matchup>_<race>.npz (rel_path, t, features) for train/plan_belief.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

from eval import monitor, priority  # noqa: E402

LOOK_EVERY = 48               # frames between looks (2 s)
HALLS = {"Z": {131, 132, 133}, "T": {106}, "P": {154}}


def _job(job: tuple):
    from gary.env import Game
    from gary.mapinfo import MapInfo
    from gary.policy.army import is_building
    from gary.policy.sightings import SightingState
    from ingest.response_dataset import Seen
    from train.plan_belief import FIRST, LAST, SAMPLE
    path, rel, race, enemy, slot = job
    try:
        g = Game.scenario(path)
    except Exception as e:  # noqa: BLE001
        return rel, f"scenario: {type(e).__name__}: {e}"
    try:
        g.step(24)
        obs = g.observe()
        # the player by its slot (the town hall of its race was either player's in a mirror: until 2026-11-23)
        own_hall = next((u for u in obs["units"] if u["owner"] == slot and u["type"] in HALLS[race]), None)
        if own_hall is None:
            return rel, f"no {race} town hall of slot {slot}"
        state = SightingState(MapInfo.from_game(g), slot, (own_hall["x"], own_hall["y"]), HALLS[enemy], is_building)
        seen = Seen(g, slot)
        times, feats = [], []
        t_next = FIRST
        while t_next <= LAST:
            target = t_next * 24
            while g.frame + LOOK_EVERY <= target:
                g.step(LOOK_EVERY)
                state.look(seen.observe()["units"], g.frame)
            if target > g.frame:
                g.step(target - g.frame)
            state.look(seen.observe()["units"], g.frame)
            if not any(u["owner"] == slot for u in g.observe()["units"]):
                break
            times.append(t_next)
            feats.append(state.features(g.frame))
            t_next += SAMPLE
        return rel, np.array(times, np.int16), np.array(feats, np.float32)
    except Exception as e:  # noqa: BLE001 - reported, not dropped silently
        return rel, f"{type(e).__name__}: {e}"
    finally:
        g.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--race", default="T")
    ap.add_argument("--matchup", default="TvZ")
    ap.add_argument("--era", choices=("modern", "all"), default="all",
                    help="all: every era the trainer reads (modern only handed the trees the era through missing values)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out")
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    from inventory import data_root
    from train.plan_belief import jobs_for
    jobs, _ = jobs_for(args.race, args.matchup)
    raw = data_root() / "raw"
    enemy = [r for r in args.matchup.split("v") if r != args.race][0]
    todo = [(str(raw / rel), rel, args.race, enemy, slot) for _, _, rel, _, _, slot in jobs
            if args.era == "all" or rel.startswith("cwal/")]
    if args.limit:
        todo = todo[:args.limit]
    with ProcessPoolExecutor(args.workers) as pool:
        got = list(monitor.track(pool.map(_job, todo, chunksize=2), len(todo), "games"))
    failed = [r for r in got if isinstance(r[1], str)]
    res = [r for r in got if not isinstance(r[1], str)]
    if failed:                                    # (every failure counted and listed, none dropped silently)
        reasons = Counter(r[1].split(":")[0] for r in failed)
        print(f"{len(failed)} of {len(todo)} games failed: {dict(reasons.most_common(6))}")
    rel = np.array([r[0] for r in res for _ in r[1]])
    t = np.concatenate([r[1] for r in res]) if res else np.zeros(0, np.int16)
    f = np.concatenate([r[2] for r in res]) if res else np.zeros((0, 0), np.float32)
    out = Path(args.out) if args.out else data_root() / "interim" / "sightings" / f"{args.matchup}_{args.race}.npz"
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, rel_path=rel, t=t, features=f)
    if failed:
        out.with_suffix(".failed.json").write_text(json.dumps(dict(failed), indent=1), encoding="utf-8")
    print(f"{len(res)} of {len(todo)} games, {len(t)} samples -> {out}")
    if len(f):
        for minute in (4, 6, 8):
            s = f[t == minute * 60]
            print(f"  {minute}:00  main known {s[:, 0].mean():.0%}, main looked at within 60 s {np.mean(s[:, 1] * 600 <= 60):.0%}, "
                  f"natural ever looked at {np.mean(s[:, 3] >= 0):.0%}, other bases looked at (3 min) {s[:, 4].mean() * 4:.1f}")


if __name__ == "__main__":
    main()

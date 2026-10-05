"""Record replays (and Gary's POV logs) of a fight model, to watch what it does: the same validation
home defenses as the pro, the imitation model and the given model; and drills as the given model,
the imitation model and attack-move. Files: <out>/<scenario or drill>_<who>.rep (+ .pov.jsonl).

    python -m eval.record --fight-model runs/fight_cmd_rl/<run>/model.pt --out data/interim/rl_replays/<name>
"""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


def _scenario(args: tuple) -> str:
    from eval import scenarios as S
    sc, who, path, out = args
    name = f"{sc['sha1'][:8]}_{who}"
    if who == "pro":
        r = S.run_one(sc, "pro", 45, "v07free", 1, save=str(Path(out) / f"{name}.rep"))
    else:
        r = S.run_one(sc, "gary", 45, "v07free", 1, save=str(Path(out) / f"{name}.rep"),
                      fight_path=None if who == "imitation" else path, sample_seed=0)
    return f"{name}: net {r.get('net')} {r.get('error', '')}"


def _drill(args: tuple) -> str:
    from gary.drills import make_drill, run_drill
    family, seed, who, path, out = args
    d = make_drill(family, seed)
    name = f"{d.name}_{who}"
    r = run_drill(d, "amove" if who == "amove" else "gary", None if who == "imitation" else path,
                  save=str(Path(out) / f"{name}.rep"))
    return f"{name}: net {r.get('net')} {r.get('error', '')}"


def record(path: str, out: str, n_scenarios: int = 4, n_drills: int = 4, family: str = "home_defense",
           pool=None) -> list[str]:
    """Replays of the model's play, with the pro / imitation / attack-move versions to compare."""
    from train.fight_cmd_rl import real_splits
    Path(out).mkdir(parents=True, exist_ok=True)
    _, val = real_splits()
    jobs_s = [(sc, who, path, out) for sc in val[:n_scenarios] for who in ("pro", "imitation", "model")]
    jobs_d = [(family, s, who, path, out) for s in range(n_drills) for who in ("model", "imitation", "amove")]
    own = pool is None
    pool = pool or ProcessPoolExecutor(max(1, (os.cpu_count() or 6) * 2 // 3))
    try:
        return list(pool.map(_scenario, jobs_s)) + list(pool.map(_drill, jobs_d))
    finally:
        if own:
            pool.shutdown()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fight-model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scenarios", type=int, default=4)
    ap.add_argument("--drills", type=int, default=4)
    ap.add_argument("--family", default="home_defense")
    args = ap.parse_args()
    for line in record(args.fight_model, args.out, args.scenarios, args.drills, args.family):
        print(line)
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

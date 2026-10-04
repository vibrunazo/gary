"""Train Gary's army model (gary/policy/army.py) on the army training set.

Behavior cloning: for each army order a pro gave, predict where the group went (one of 256 cells
of the mirrored 16x16 map grid) and whether it was a move or an attack. Games are split by replay
(the same 10% held out as the macro model), and scored on the held-out games:

  cell top-1 / top-5    the destination cell is the model's first (or among its first five) guesses
  within 1 cell         the first guess is the destination or one of its 8 neighbors
  far orders            the same, only for orders sending the group 3+ cells away (attacks,
                        retreats, defending another base), the decisions that matter most
  kind                  move vs attack accuracy
Baselines: "stay" (the group's own cell) and "most common destination cell".

Usage:
  python -m train.army --race T
Output: runs/army/<matchup>_<race>_<time>/model.pt and report.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "ingest"))
from inventory import data_root  # noqa: E402

from gary.policy.army import CELLS, CHANNELS, GRID, ArmyModel, ArmyNet, ArmySpec, encode_global  # noqa: E402
from train.macro import is_test  # noqa: E402  (same held-out games as the macro model)

MAX_PER_PLAYER = 160          # samples per player-game (keeps memory in check, spreads over games)


def army_dir() -> Path:
    return data_root() / "interim" / "army" / "v1"


def player_games(matchup: str, race: str) -> list[tuple[str, int, bool]]:
    out = []
    with open(army_dir() / "index.jsonl", encoding="utf-8") as f:
        rows = {r["sha1"]: r for r in map(json.loads, f)}
    for r in rows.values():
        if not r.get("ok") or r["matchup"] != matchup:
            continue
        path = str(army_dir() / r["sha1"][:2] / f"{r['sha1']}.npz")
        for i, p in enumerate(r["players"]):
            if p["race"] == race and p["samples"] > 0:
                out.append((path, i, is_test(r["sha1"])))
    return out


def scan(job: tuple) -> tuple[set, set]:
    d = np.load(job[0])
    i = job[1]
    return (set(np.nonzero(d[f"p{i}_units"].max(0))[0].tolist()),
            set(np.nonzero(d[f"p{i}_seen"].max(0))[0].tolist()))


def load_player(args: tuple) -> tuple[np.ndarray, ...]:
    (path, i, held), spec_d = args
    spec = ArmySpec(**spec_d)
    d = np.load(path)
    n = len(d[f"p{i}_target"])
    rng = np.random.default_rng(hash(path) % 2**32 + i)
    idx = np.sort(rng.choice(n, MAX_PER_PLAYER, replace=False)) if n > MAX_PER_PLAYER and not held else np.arange(n)
    grid = d[f"p{i}_grid"][idx]
    glob = encode_global(spec, d[f"p{i}_frame"][idx].astype(np.float32), d[f"p{i}_eco"][idx].astype(np.float32),
                         d[f"p{i}_sup"][idx].astype(np.float32), d[f"p{i}_units"][idx].astype(np.float32),
                         d[f"p{i}_seen"][idx].astype(np.float32))
    group_cell = grid[:, 8].argmax(1).astype(np.int16)
    return grid, glob.astype(np.float16), d[f"p{i}_target"][idx], d[f"p{i}_kind"][idx], group_cell


def load(jobs: list, spec: ArmySpec, workers: int) -> dict:
    parts = {False: [], True: []}
    with ProcessPoolExecutor(workers) as pool:
        for job, res in zip(jobs, pool.map(load_player, [(j, spec.to_dict()) for j in jobs], chunksize=16)):
            parts[job[2]].append(res)
    return {("test" if held else "train"): tuple(np.concatenate([r[k] for r in rs]) for k in range(5))
            for held, rs in parts.items()}


def cell_dist(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Chebyshev distance between cells, in cells."""
    return np.maximum(np.abs(a // GRID - b // GRID), np.abs(a % GRID - b % GRID))


def evaluate(net: ArmyNet, data: tuple, common: int, device: str) -> dict:
    grid, glob, target, kind, group = data
    net.eval()
    top5, kinds = [], []
    with torch.no_grad():
        for s in range(0, len(target), 8192):
            g = torch.from_numpy(grid[s:s + 8192]).to(device).float().view(-1, CHANNELS, GRID, GRID)
            where, k = net(g, torch.from_numpy(glob[s:s + 8192]).to(device).float())
            top5.append(where.topk(5, -1).indices.cpu().numpy())
            kinds.append(k.argmax(-1).cpu().numpy())
    top5, kinds = np.concatenate(top5), np.concatenate(kinds)
    t = target.astype(np.int64)
    first = top5[:, 0]
    far = cell_dist(t, group.astype(np.int64)) >= 3
    r = lambda x: round(float(x), 4)
    return {
        "orders": int(len(t)), "far_share": r(far.mean()),
        "cell_top1": r((first == t).mean()), "cell_top5": r((top5 == t[:, None]).any(1).mean()),
        "within1": r((cell_dist(first, t) <= 1).mean()),
        "far_within1": r((cell_dist(first, t) <= 1)[far].mean()),
        "far_top5": r((top5 == t[:, None]).any(1)[far].mean()),
        "kind_acc": r((kinds == kind).mean()),
        "baseline_stay_within1": r((cell_dist(group.astype(np.int64), t) <= 1).mean()),
        "baseline_stay_far_within1": r((cell_dist(group.astype(np.int64), t) <= 1)[far].mean()),
        "baseline_common_within1": r((cell_dist(np.full_like(t, common), t) <= 1).mean()),
        "baseline_kind_acc": r(max((kind == 0).mean(), (kind == 1).mean())),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--matchup", default="TvZ")
    ap.add_argument("--race", required=True, choices=["T", "Z", "P"])
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--channels", type=int, default=64)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.time()

    jobs = player_games(args.matchup, args.race)
    own, seen = set(), set()
    with ProcessPoolExecutor(args.workers) as pool:
        for o, s in pool.map(scan, [j for j in jobs if not j[2]], chunksize=32):
            own |= o
            seen |= s
    spec = ArmySpec(race=args.race, own_types=sorted(own), seen_types=sorted(seen))
    data = load(jobs, spec, args.workers)
    grid, glob, target, kind, group = data["train"]
    print(f"{len(jobs)} player-games; orders: train {len(target):,}, test {len(data['test'][2]):,} "
          f"({time.time() - t0:.0f} s)", flush=True)
    common = int(np.bincount(target.astype(np.int64), minlength=CELLS).argmax())

    config = {"net": {"ch": args.channels}, "matchup": args.matchup}
    net = ArmyNet(spec.n_global, **config["net"]).to(device)
    opt = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=1e-4)
    steps = args.epochs * (len(target) // args.batch + 1)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=steps)
    gt = torch.from_numpy(grid)                     # uint8 on the CPU; batches move to the GPU
    xt = torch.from_numpy(glob)
    yt = torch.from_numpy(target.astype(np.int64))
    kt = torch.from_numpy(kind.astype(np.int64))
    for epoch in range(args.epochs):
        net.train()
        perm = torch.randperm(len(yt))
        total = 0.0
        for s in range(0, len(perm), args.batch):
            idx = perm[s:s + args.batch]
            g = gt[idx].to(device, non_blocking=True).float().view(-1, CHANNELS, GRID, GRID)
            where, k = net(g, xt[idx].to(device).float())
            loss = F.cross_entropy(where, yt[idx].to(device)) + 0.5 * F.cross_entropy(k, kt[idx].to(device))
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            total += loss.item() * len(idx)
        res = evaluate(net, data["test"], common, device)
        print(f"epoch {epoch + 1}: loss {total / len(yt):.3f}  within1 {res['within1']}  "
              f"far within1 {res['far_within1']}  top5 {res['cell_top5']}  kind {res['kind_acc']}", flush=True)

    out = REPO_ROOT / "runs" / "army" / f"{args.matchup}_{args.race}_{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    ArmyModel(spec, net.cpu(), config).save(out / "model.pt")
    report = {"matchup": args.matchup, "race": args.race, "player_games": len(jobs),
              "train_orders": int(len(target)), "epochs": args.epochs,
              "minutes": round((time.time() - t0) / 60, 1), "test": res}
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"saved {out / 'model.pt'}")


if __name__ == "__main__":
    main()

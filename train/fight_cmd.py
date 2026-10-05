"""Train Gary's fight command model (gary/policy/fight_cmd.py) on the fight training set (#2).

Behavior cloning, one command at a time: for each fight snapshot, the commands the pro gave in
the next half second. They're rebuilt from the fight set's per-unit labels: the player's units
told the same thing in that window (the same action and target unit, or for moves the same
point) were one command, and they were its selection (as far as it's in the snapshot).
Snapshots without a command teach "nothing". Terran's units, the same 10% of games held out as
the other models. Scored on held-out games:

  command      the command type: accuracy, and when the pro commanded, how often the model's
               likeliest real command is the pro's (baseline: "nothing" / the most common command)
  selection    given the type: IoU of the selected units with the pro's (baseline: all own units)
  target       given type and selection, the pro's target unit (baseline: the nearest unit of the
               right side to the selection)
  destination  for moves, the pro's cell or a neighbor (baseline: the selection's own cell)

Usage:
  python -m train.fight_cmd
Output: runs/fight_cmd/<matchup>_<race>_<time>/model.pt and report.json
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

from gary.bots.terran_v04 import latest_fight_model  # noqa: E402
from gary.policy.fight import ACTIONS, MAX_UNITS, OTARGET, SIDE, X, Y, tensors  # noqa: E402
from gary.policy.fight_cmd import GRID, MOVES, POINTER, CommandModel, CommandNet, cell_of  # noqa: E402
from train.fight import KEEP_IDLE, PER_GAME, jobs_for  # noqa: E402

A = {a: i for i, a in enumerate(ACTIONS)}
TARGET_SIDE = {A["attack_unit"]: 0, A["gather"]: 2, A["own_unit"]: 1}


def load_game(job: tuple):
    """Command examples of one player in one game: (units, padding, command, selection, target
    row, destination cell, time, held out)."""
    path, player, held = job
    d = np.load(path)
    starts, units = d["snap_start"], d["units"]
    act, act_t, dx, dy = d["act"], d["act_target"], d["act_dx"], d["act_dy"]
    rng = np.random.default_rng(int(path[-12:-4], 16) + player)
    snaps = list(np.nonzero(d["snap_player"] == player)[0])
    if len(snaps) > PER_GAME and not held:
        snaps = sorted(rng.choice(snaps, PER_GAME, replace=False))
    out = {k: [] for k in ("U", "PAD", "CMD", "SEL", "TGT", "CELL", "T")}

    def add(rows, n, cmd, sel, tgt, cell, t):
        u = np.zeros((MAX_UNITS, 11), np.int16)
        u[:n] = rows
        out["U"].append(u); out["PAD"].append(np.arange(MAX_UNITS) >= n); out["CMD"].append(cmd)
        out["SEL"].append(sel); out["TGT"].append(tgt); out["CELL"].append(cell); out["T"].append(t)

    for k in snaps:
        s, e = starts[k], starts[k + 1]
        rows = units[s:e]
        order = np.argsort(rows[:, X].astype(np.int32) ** 2 + rows[:, Y].astype(np.int32) ** 2)[:MAX_UNITS]
        n = len(order)
        remap = np.full(e - s, -1, np.int16)
        remap[order] = np.arange(n)
        r = rows[order].copy()
        ot = r[:, OTARGET]
        r[:, OTARGET] = np.where(ot >= 0, remap[np.maximum(ot, 0)], -1)
        a, t = act[s:e][order], act_t[s:e][order]
        t = np.where(t >= 0, remap[np.maximum(t, 0)], -1)
        ax = r[:, X].astype(np.int32) + dx[s:e][order]
        ay = r[:, Y].astype(np.int32) + dy[s:e][order]
        time_s = d["snap_frame"][k] * 42 / 1000.0
        groups: dict[tuple, list[int]] = {}
        for i in np.nonzero(a > 0)[0]:
            ai = int(a[i])
            key = (ai, int(t[i])) if ai in POINTER else \
                (ai, int(ax[i]) // 8, int(ay[i]) // 8) if ai in MOVES else (ai,)
            groups.setdefault(key, []).append(int(i))
        if not groups:
            if rng.random() < KEEP_IDLE:
                add(r, n, 0, np.zeros(MAX_UNITS, bool), -1, -1, time_s)
            continue
        for key, members in groups.items():
            sel = np.zeros(MAX_UNITS, bool)
            sel[members] = True
            tgt = key[1] if key[0] in POINTER and key[1] not in members else -1
            cell = int(cell_of(ax[members[0]], ay[members[0]])) if key[0] in MOVES else -1
            add(r, n, key[0], sel, tgt, cell, time_s)
    if not out["U"]:
        return None
    m = len(out["U"])
    return (np.stack(out["U"]), np.stack(out["PAD"]), np.array(out["CMD"], np.int64), np.stack(out["SEL"]),
            np.array(out["TGT"], np.int64), np.array(out["CELL"], np.int64), np.array(out["T"], np.float32),
            np.full(m, held))


def load_all(jobs: list, workers: int) -> dict:
    parts = []
    with ProcessPoolExecutor(workers) as pool:
        for r in pool.map(load_game, jobs, chunksize=16):
            if r is not None:
                parts.append(r)
    allp = [np.concatenate([p[k] for p in parts]) for k in range(8)]
    held = allp[7]
    return {"train": tuple(a[~held] for a in allp[:7]), "test": tuple(a[held] for a in allp[:7])}


def batch(data: tuple, idx: np.ndarray, device: str):
    U, PAD, CMD, SEL, TGT, CELL, T = (a[idx] for a in data)
    inputs = tensors(U, PAD, T, device)
    lab = lambda x: torch.as_tensor(x, device=device)
    return inputs, (lab(CMD), lab(SEL), lab(TGT), lab(CELL))


def forward(net: CommandNet, inputs, labels):
    cmd, sel, tgt, cell = labels
    return net(*inputs, cmd, sel)


def losses(net: CommandNet, inputs, labels, weights: torch.Tensor | None = None) -> torch.Tensor:
    cmd, sel, tgt, cell = labels
    cmd_l, sel_l, tgt_l, dst_l = forward(net, inputs, labels)
    loss = F.cross_entropy(cmd_l, cmd, weight=weights)
    side, pad = inputs[1], inputs[4]
    own = (side == 1) & ~pad & (cmd > 0)[:, None]
    if own.any():
        loss = loss + F.binary_cross_entropy_with_logits(sel_l[own], sel[own].float())
    aimed = tgt >= 0
    if aimed.any():
        loss = loss + F.cross_entropy(tgt_l[aimed], tgt[aimed])
    moving = cell >= 0
    if moving.any():
        loss = loss + F.cross_entropy(dst_l[moving], cell[moving])
    return loss


@torch.no_grad()
def evaluate(net: CommandNet, data: tuple, device: str) -> dict:
    net.eval()
    cmds, preds, preds_real, ious, ious_base, hits, hits_base, near, near_base = ([] for _ in range(9))
    U = data[0]
    common = int(np.bincount(data[2][data[2] > 0], minlength=len(ACTIONS)).argmax())
    for s in range(0, len(U), 2048):
        idx = np.arange(s, min(s + 2048, len(U)))
        inputs, labels = batch(data, idx, device)
        cmd, sel, tgt, cell = labels
        cmd_l, sel_l, tgt_l, dst_l = forward(net, inputs, labels)
        cmds.append(cmd.cpu().numpy())
        preds.append(cmd_l.argmax(-1).cpu().numpy())
        preds_real.append((cmd_l[:, 1:].argmax(-1) + 1).cpu().numpy())
        side, pad = inputs[1], inputs[4]
        own = (side == 1) & ~pad
        acted = cmd > 0
        pick = (sel_l > 0) & own
        iou = (pick & sel).sum(1) / (pick | sel).sum(1).clamp(min=1)
        base = (own & sel).sum(1) / (own | sel).sum(1).clamp(min=1)
        ious.append(iou[acted].cpu().numpy()); ious_base.append(base[acted].cpu().numpy())
        aimed = tgt >= 0
        hits.append((tgt_l.argmax(-1) == tgt)[aimed].cpu().numpy())
        # baseline: the unit of the right side nearest to the selection's center
        u = torch.as_tensor(U[idx].astype(np.float32), device=device)
        xy = u[..., [X, Y]]
        sf = sel.float()
        center = (xy * sf[..., None]).sum(1) / sf.sum(1, keepdim=True).clamp(min=1)
        dist = (xy - center[:, None]).norm(dim=-1)
        want = torch.zeros_like(cmd)
        for a, sd in TARGET_SIDE.items():
            want = torch.where(cmd == a, torch.full_like(cmd, sd), want)
        dist = dist.masked_fill((side != want[:, None]) | pad | sel, 1e9)
        hits_base.append((dist.argmin(-1) == tgt)[aimed].cpu().numpy())
        moving = cell >= 0
        guess = dst_l.argmax(-1)
        own_cell = torch.as_tensor(cell_of(center[:, 0].cpu().numpy(), center[:, 1].cpu().numpy()), device=device)
        close = lambda c: ((c % GRID - cell % GRID).abs() <= 1) & ((c // GRID - cell // GRID).abs() <= 1)
        near.append(close(guess)[moving].cpu().numpy()); near_base.append(close(own_cell)[moving].cpu().numpy())
    cmds, preds, preds_real = np.concatenate(cmds), np.concatenate(preds), np.concatenate(preds_real)
    cat = lambda x: np.concatenate(x)
    r = lambda x: round(float(np.mean(x)), 4)
    acted = cmds > 0
    recall = {ACTIONS[a]: r(preds_real[cmds == a] == a) for a in range(1, len(ACTIONS)) if (cmds == a).sum() >= 50}
    return {"examples": int(len(cmds)), "commands": int(acted.sum()),
            "command_acc": r(preds == cmds), "baseline_command_acc": r(cmds == 0),
            "commanded_acc": r(preds_real[acted] == cmds[acted]), "baseline_commanded_acc": r(cmds[acted] == common),
            "recall": recall, "selection_iou": r(cat(ious)), "baseline_selection_iou": r(cat(ious_base)),
            "target_acc": r(cat(hits)), "baseline_target_acc": r(cat(hits_base)),
            "dest_near": r(cat(near)), "baseline_dest_near": r(cat(near_base))}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--matchup", default="TvZ")
    ap.add_argument("--race", default="T", choices=["T", "Z", "P"])
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--lr", type=float, default=5e-4)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, help="only this many player-games (quick tests)")
    ap.add_argument("--class-weight", type=float, default=0.5,
                    help="weigh each command type by frequency^-this in the loss; 0 = off")
    ap.add_argument("--no-init", action="store_true", help="don't start the encoder from the fight model")
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.time()
    jobs = jobs_for(args.matchup, args.race)[:args.limit]
    data = load_all(jobs, args.workers)
    n_train, n_test = len(data["train"][0]), len(data["test"][0])
    print(f"{len(jobs)} player-games; examples: train {n_train:,}, test {n_test:,} ({time.time() - t0:.0f} s)", flush=True)
    config = {"net": {"d": 128, "layers": 3, "heads": 4}, "matchup": args.matchup, "race": args.race,
              "class_weight": args.class_weight}
    net = CommandNet(**config["net"]).to(device)
    if not args.no_init:                     # the unit encoder from the per-unit fight model
        init = latest_fight_model(args.matchup, args.race)
        state = torch.load(init, map_location=device, weights_only=True)["state"]
        enc = {k: v for k, v in state.items() if k.split(".")[0] in ("type_emb", "side_emb", "order_emb", "inp", "body")}
        net.load_state_dict(enc, strict=False)
        config["encoder_from"] = str(init.relative_to(REPO_ROOT))
        print(f"encoder from {init}", flush=True)
    opt = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=1e-4)
    steps = args.epochs * (n_train // args.batch + 1)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=steps)
    counts = np.bincount(data["train"][2], minlength=len(ACTIONS)).astype(np.float64)
    w = np.where(counts > 0, (counts / counts.sum()) ** -args.class_weight, 0.0)
    weights = torch.tensor(w / (w * counts).sum() * counts.sum(), dtype=torch.float32, device=device)
    print("command counts:", {a: int(c) for a, c in zip(ACTIONS, counts)}, flush=True)
    for epoch in range(args.epochs):
        net.train()
        perm = np.random.permutation(n_train)
        total, nb = 0.0, 0
        for s in range(0, n_train, args.batch):
            inputs, labels = batch(data["train"], perm[s:s + args.batch], device)
            loss = losses(net, inputs, labels, weights)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            sched.step()
            total, nb = total + loss.item(), nb + 1
        res = evaluate(net, data["test"], device)
        print(f"epoch {epoch + 1}: loss {total / nb:.3f}  command {res['command_acc']} (none {res['baseline_command_acc']})  "
              f"commanded {res['commanded_acc']} (most common {res['baseline_commanded_acc']})  "
              f"selection IoU {res['selection_iou']} (all own {res['baseline_selection_iou']})  "
              f"target {res['target_acc']} (nearest {res['baseline_target_acc']})  "
              f"dest near {res['dest_near']} (stay {res['baseline_dest_near']})  ({time.time() - t0:.0f} s)", flush=True)
    out = REPO_ROOT / "runs" / "fight_cmd" / f"{args.matchup}_{args.race}_{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    CommandModel(net.cpu(), config).save(out / "model.pt")
    report = {"matchup": args.matchup, "race": args.race, "train_examples": n_train, "epochs": args.epochs,
              "minutes": round((time.time() - t0) / 60, 1), "test": res}
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"saved {out / 'model.pt'}")


if __name__ == "__main__":
    main()

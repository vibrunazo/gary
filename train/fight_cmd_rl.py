"""Reinforcement learning for the fight command model on micro drills (#2; ARCHITECTURE.md §7.8,
T0 micro curriculum).

Starts from the imitation-trained command model with memory (train/fight_cmd.py --memory) and
improves it on drills (gary/drills.py): each round Gary plays a batch of drills several times each,
drawing its commands from the model, through the human interface. Every decision (nothing
included) is judged by what happened in the HORIZON_S seconds after it (zerg value killed minus
terran value lost), against the other plays of the same drill over the same stretch
(group-relative advantages); a PPO-style clipped update makes better decisions likelier, and a KL
penalty keeps the model near the imitation model (human-like). Every few rounds the model is
scored on held-out drills it never trains on; the real test is afterwards, on the pro scenarios:

    python -m train.fight_cmd_rl --rounds 200
    python -m eval.scenarios --run 114 --version v07free --controllers gary --samples 4 \\
        --fight-model runs/fight_cmd_rl/<run>/model.pt
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from gary.bots.terran_v05 import latest_command_model
from gary.drills import behavior, make_drill, run_drill
from gary.policy.fight import tensors
from gary.policy.fight_cmd import MOVES, POINTER, CommandModel
from gary.policy.fight_memory import HIST_K, TOKEN_FEATURES, UNIT_FEATURES

REPO_ROOT = Path(__file__).resolve().parent.parent
HORIZON_S = 10                  # a decision is credited with the next 10 s
ADV_FLOOR = 25                  # value: plays closer than this count as ties
TRAIN_SEEDS = (10_000, 10_000_000)   # drills to train on; seeds below are held out for testing


def play(args: tuple) -> dict:
    family, seed, path, draw, log = args
    return run_drill(make_drill(family, seed), "gary", path, sample_seed=draw, log=log)


def to_go(deaths: list, t: float, horizon: float) -> float:
    return sum(v for f, v in deaths if t < f * 42 / 1000 <= t + horizon)


def decisions(rows: list[dict], horizon: float) -> list[tuple]:
    """(decision, advantage) for every logged decision, grouped by drill."""
    by: dict[str, list[dict]] = {}
    for r in rows:
        if "error" not in r:
            by.setdefault(r["drill"], []).append(r)
    out = []
    for rs in by.values():
        if len(rs) < 2:
            continue
        for k, r in enumerate(rs):
            for d in r.get("log", []):
                g = np.array([to_go(o["deaths"], d["time"], horizon) for o in rs], np.float32)
                a = (g[k] - g.mean()) / max(float(g.std()), ADV_FLOOR)
                if a != 0:
                    out.append((d, float(a)))
    return out


def batch(decs: list, device: str):
    """Padded model inputs and the decisions taken, for a list of (decision, advantage)."""
    n = max(len(d["rows"]) for d, _ in decs)
    B = len(decs)
    units = np.zeros((B, n, 11), np.int16)
    pad = np.ones((B, n), bool)
    uk = np.zeros((B, n), np.int64)
    un = np.zeros((B, n, UNIT_FEATURES), np.float32)
    tok = np.zeros((B, HIST_K, TOKEN_FEATURES), np.float32)
    tk = np.zeros((B, HIST_K), np.int64)
    ta = np.ones((B, HIST_K), bool)
    sel = np.zeros((B, n), bool)
    typ, tgt, cell = np.zeros(B, np.int64), np.zeros(B, np.int64), np.zeros(B, np.int64)
    times, adv = np.zeros(B, np.float32), np.zeros(B, np.float32)
    for b, (d, a) in enumerate(decs):
        m = len(d["rows"])
        units[b, :m], pad[b, :m] = d["rows"], False
        if d["hist"] is not None:
            u_kind, u_num, t_f, t_kind, t_abs = d["hist"]
            uk[b, :m], un[b, :m], tok[b], tk[b], ta[b] = u_kind[:m], u_num[:m], t_f, t_kind, t_abs
        sel[b, d["select"]] = True
        typ[b], tgt[b], cell[b], times[b], adv[b] = d["type"], d["target"], d["cell"], d["time"], a
    t = lambda x: torch.as_tensor(x, device=device)
    inputs = tensors(units, pad, times, device)
    return inputs, (t(uk), t(un), t(tok), t(tk), t(ta)), t(sel), t(typ), t(tgt), t(cell), t(adv)


def log_probs(net, inputs, hist, sel, typ, tgt, cell):
    """Log-probability of each decision (type, then selection, then target or cell), and the
    type distribution's log-probabilities (for the KL penalty)."""
    kind, side, order, num, pad = inputs
    h, glob, own = net.encode(kind, side, order, num, pad, hist)
    type_lp = F.log_softmax(net.command_logits(glob), -1)
    b = torch.arange(len(typ), device=typ.device)
    lp = type_lp[b, typ]
    acted = typ > 0
    sel_l, tgt_l, dst_l = net.rest(h, glob, own, pad, typ.clamp(min=1), sel)
    sel_lp = torch.where(sel, F.logsigmoid(sel_l), F.logsigmoid(-sel_l))
    sel_lp = (sel_lp * own.float()).sum(1)
    lp = lp + torch.where(acted, sel_lp, torch.zeros_like(sel_lp))
    aimed = acted & torch.isin(typ, torch.tensor(POINTER, device=typ.device)) & (tgt >= 0)
    t_lp = F.log_softmax(tgt_l, -1)[b, tgt.clamp(min=0)]
    lp = lp + torch.where(aimed, t_lp, torch.zeros_like(t_lp))
    moved = acted & torch.isin(typ, torch.tensor(MOVES, device=typ.device)) & (cell >= 0)
    c_lp = F.log_softmax(dst_l, -1)[b, cell.clamp(min=0)]
    lp = lp + torch.where(moved, c_lp, torch.zeros_like(c_lp))
    return lp, type_lp


def update(net, ref, opt, decs: list, args, device: str) -> dict:
    net.eval()                                   # no dropout: the same policy that played
    random.shuffle(decs)
    parts = [batch(decs[i:i + args.minibatch], device) for i in range(0, len(decs), args.minibatch)]
    with torch.no_grad():
        old = [log_probs(net, *p[:6])[0] for p in parts]
        ref_lp = [log_probs(ref, *p[:6])[1] for p in parts]
    stats = {"pg": 0.0, "kl": 0.0, "clipped": 0.0, "n": 0}
    for _ in range(args.epochs):
        for k in random.sample(range(len(parts)), len(parts)):
            *inp, adv = parts[k]
            lp, type_lp = log_probs(net, *inp)
            ratio = torch.exp((lp - old[k]).clamp(-20, 20))
            pg = -torch.min(ratio * adv, ratio.clamp(1 - args.clip, 1 + args.clip) * adv).mean()
            kl = (type_lp.exp() * (type_lp - ref_lp[k])).sum(-1).mean()
            loss = pg + args.kl * kl
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            stats["pg"] += pg.item(); stats["kl"] += kl.item()
            stats["clipped"] += ((ratio - 1).abs() > args.clip).float().mean().item(); stats["n"] += 1
    return {k: round(v / max(1, stats["n"]), 4) for k, v in stats.items() if k != "n"}


def test(pool, family: str, n: int, path: str) -> tuple[float, dict]:
    """Held-out drills (seeds 0..n-1): mean net, and what the model did (behavior check)."""
    rows = [r for r in pool.map(play, [(family, s, path, 0, True) for s in range(n)], chunksize=4) if "error" not in r]
    return float(np.mean([r["net"] for r in rows])), behavior(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--init", help="command model to start from (default: the latest with memory)")
    ap.add_argument("--family", nargs="+", default=["home_defense", "mm_vs_lings"],
                    help="drill families, trained on in turn and tested each on its own")
    ap.add_argument("--rounds", type=int, default=200)
    ap.add_argument("--drills", type=int, default=64, help="training drills per round")
    ap.add_argument("--draws", type=int, default=8, help="plays of each drill per round")
    ap.add_argument("--test-every", type=int, default=10)
    ap.add_argument("--test-drills", type=int, default=300, help="held-out drills (seeds 0..n-1)")
    ap.add_argument("--horizon", type=float, default=HORIZON_S)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--kl", type=float, default=0.02, help="weight of the KL penalty to the imitation model")
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--minibatch", type=int, default=256)
    ap.add_argument("--parallel", type=int, default=max(1, (os.cpu_count() or 6) * 2 // 3))
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    init = Path(args.init or latest_command_model(memory=True))
    model = CommandModel.load(init, device)
    ref = CommandModel.load(init, device).net.eval()
    for p in ref.parameters():
        p.requires_grad_(False)
    net = model.net
    opt = torch.optim.Adam(net.parameters(), lr=args.lr)
    out = REPO_ROOT / "runs" / "fight_cmd_rl" / time.strftime(f"{'+'.join(args.family)}_%Y%m%d_%H%M%S")
    out.mkdir(parents=True)
    model.config = {**model.config, "rl": {"init": str(init), **vars(args)}}
    history, best = [], None
    rng = random.Random(0)
    print(f"from {init}; {args.drills} drills x {args.draws} plays per round", flush=True)
    with ProcessPoolExecutor(args.parallel) as pool:
        for rnd in range(args.rounds + 1):
            path = str(out / f"round{rnd}.pt")
            model.save(path)
            if rnd % args.test_every == 0 or rnd == args.rounds:
                scores = {}
                for fam in args.family:
                    scores[fam], beh = test(pool, fam, args.test_drills, path)
                    print(f"round {rnd}: held-out {fam} net {scores[fam]:.0f}; {beh}", flush=True)
                score = float(np.mean(list(scores.values())))
                history.append({"round": rnd, "test_net": {k: round(v, 1) for k, v in scores.items()}})
                if best is None or score > best[0]:
                    best = (score, rnd)
                    model.save(out / "model.pt")
            if rnd == args.rounds:
                break
            t0 = time.time()
            drills = [(args.family[i % len(args.family)], rng.randrange(*TRAIN_SEEDS)) for i in range(args.drills)]
            rows = list(pool.map(play, [(fam, s, path, k, True) for fam, s in drills for k in range(args.draws)],
                                 chunksize=args.draws))
            decs = decisions(rows, args.horizon)
            nets = [r["net"] for r in rows if "error" not in r]
            stats = update(net, ref, opt, decs, args, device) if decs else {}
            errors = sum(1 for r in rows if "error" in r)
            print(f"round {rnd + 1}: train net {np.mean(nets):.0f}, {len(decs)} decisions, {stats}, "
                  f"{errors} errors, {time.time() - t0:.0f} s", flush=True)
            history.append({"round": rnd + 1, "train_net": round(float(np.mean(nets)), 1), **stats})
            for old in out.glob("round*.pt"):
                if old.name != f"round{rnd}.pt":
                    old.unlink()
    (out / "history.json").write_text(json.dumps(history, indent=1), encoding="utf-8")
    print(f"best held-out drills net (mean of families) {best[0]:.0f} at round {best[1]} -> {out / 'model.pt'}")


if __name__ == "__main__":
    main()

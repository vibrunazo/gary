"""Gary's fight command model: the next command in a skirmish, as a player gives it (#2).

The fight model (fight.py) says what each unit should do; a player instead gives one command at a
time to a selection: "these 12 SCVs, attack-move there". This model predicts that command,
AlphaStar-style, one part after the other:

  1. the command type (ACTIONS: nothing, move, attack-move, attack a unit, gather, right-click an
     own unit, stop, hold, stim, return cargo, other)
  2. which of the player's units are selected (each own unit in or out, at most 12)
  3. its target: a unit (a pointer into the set) for attacks, gathering and right-clicks on own
     units, or a point for moves (a cell of a 32x32 grid of 64-pixel cells around the fight)

Same input as the fight model: the units around the fight as the player sees them, mirrored so the
player's main is top-left. Learned from the same pro skirmishes (train/fight_cmd.py): the commands
are rebuilt from the per-unit labels (units told the same thing in the same half second).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

from gary.policy.fight import ACTIONS, MAX_UNITS, N_ORDERS, N_TYPES, tensors

GRID = 32                       # destination cells per side
CELL = 64                       # pixels per cell: the grid covers +-1024 px around the fight
HALF = GRID * CELL // 2
MAX_SELECT = 12
POINTER = [ACTIONS.index(a) for a in ("attack_unit", "gather", "own_unit")]
MOVES = [ACTIONS.index(a) for a in ("move", "attack_move")]


def cell_of(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Grid cell of points relative to the fight center (points outside go to the edge)."""
    cx = np.clip((x + HALF) // CELL, 0, GRID - 1)
    cy = np.clip((y + HALF) // CELL, 0, GRID - 1)
    return (cy * GRID + cx).astype(np.int64)


def point_of(cell: int) -> tuple[float, float]:
    """The center of a grid cell, relative to the fight center."""
    return (cell % GRID + 0.5) * CELL - HALF, (cell // GRID + 0.5) * CELL - HALF


def mlp(i: int, h: int, o: int) -> nn.Module:
    return nn.Sequential(nn.Linear(i, h), nn.ReLU(), nn.Linear(h, o))


class CommandNet(nn.Module):
    def __init__(self, d: int = 128, layers: int = 3, heads: int = 4):
        super().__init__()
        # the unit encoder: same layout as FightNet, so it can start from its weights
        self.type_emb = nn.Embedding(N_TYPES, 48)
        self.side_emb = nn.Embedding(3, 8)
        self.order_emb = nn.Embedding(N_ORDERS, 16)
        self.inp = nn.Linear(48 + 8 + 16 + 9, d)
        layer = nn.TransformerEncoderLayer(d, heads, 4 * d, dropout=0.1, batch_first=True, norm_first=True)
        self.body = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.cmd = mlp(2 * d, d, len(ACTIONS))           # 1. command type, from the whole fight
        self.cmd_emb = nn.Embedding(len(ACTIONS), d)
        self.sel = mlp(d, d, 1)                           # 2. each own unit in the selection or not
        self.query = mlp(3 * d, d, d)                     # 3. target, from selection + type + fight
        self.key = nn.Linear(d, d)
        self.dest = nn.Linear(d, GRID * GRID)

    def encode(self, kind, side, order, num, pad):
        h = self.inp(torch.cat([self.type_emb(kind), self.side_emb(side), self.order_emb(order), num], -1))
        h = self.body(h, src_key_padding_mask=pad)
        own = (side == 1) & ~pad
        mean = lambda m: (h * m[..., None]).sum(1) / m.sum(1, keepdim=True).clamp(min=1)
        glob = torch.cat([mean(own.float()), mean((~pad).float())], -1)
        return h, glob, own

    def command_logits(self, glob):
        return self.cmd(glob)

    def rest(self, h, glob, own, pad, cmd, sel):
        """Selection logits given the command type; target and destination logits given the
        type and the selection (sel: (B, N) bool)."""
        e = self.cmd_emb(cmd)
        sel_l = self.sel(h + e[:, None]).squeeze(-1).masked_fill(~own, -1e9)
        s = sel.float()
        pool = (h * s[..., None]).sum(1) / s.sum(1, keepdim=True).clamp(min=1)
        q = self.query(torch.cat([pool, e, glob[:, :h.shape[-1]]], -1))
        tgt_l = torch.einsum("bd,bnd->bn", q, self.key(h)) / h.shape[-1] ** 0.5
        tgt_l = tgt_l.masked_fill(pad | sel, -1e9)       # not a unit of the selection itself
        return sel_l, tgt_l, self.dest(q)

    def forward(self, kind, side, order, num, pad, cmd, sel):
        """Teacher-forced: all logits given the true command type and selection."""
        h, glob, own = self.encode(kind, side, order, num, pad)
        return (self.command_logits(glob),) + self.rest(h, glob, own, pad, cmd, sel)


class CommandModel:
    kind = "command"

    def __init__(self, net: CommandNet, config: dict):
        self.net, self.config = net.eval(), config

    @classmethod
    def load(cls, path: str | Path, device: str = "cpu") -> "CommandModel":
        ck = torch.load(path, map_location=device, weights_only=True)
        net = CommandNet(**ck["config"]["net"])
        net.load_state_dict(ck["state"])
        model = cls(net.to(device), ck["config"])
        model.path = str(path)
        return model

    def save(self, path: str | Path) -> None:
        torch.save({"state": self.net.state_dict(), "config": {**self.config, "kind": self.kind}}, path)

    @torch.no_grad()
    def decide(self, units: np.ndarray, time_s: float, rng: np.random.Generator,
               temperature: float = 1.0) -> dict | None:
        """One command for a snapshot (units (n, 11)), drawn from the model, or None for
        "nothing": {"type", "select" (row indices), "target" (row or -1), "dest" ((x, y) relative
        to the fight center in the mirrored frame, or None), "p_type"}. temperature < 1 draws
        closer to the model's likeliest choices."""
        dev = next(self.net.parameters()).device
        n = min(len(units), MAX_UNITS)
        pad = np.zeros((1, n), bool)
        inputs = tensors(units[None, :n], pad, np.array([time_s], np.float32), dev)
        h, glob, own = self.net.encode(*inputs)
        tau = temperature
        p = torch.softmax(self.net.command_logits(glob)[0] / tau, -1).double().cpu().numpy()
        cmd = int(rng.choice(len(p), p=p / p.sum()))
        if cmd == 0 or not own.any():
            return None
        c = torch.tensor([cmd], device=dev)
        none = torch.zeros((1, n), dtype=torch.bool, device=dev)
        sel_l, _, _ = self.net.rest(h, glob, own, inputs[4], c, none)
        ps = torch.sigmoid(sel_l[0] / tau).cpu().numpy() * own[0].cpu().numpy()
        chosen = np.nonzero(rng.random(n) < ps)[0]
        if len(chosen) == 0:
            chosen = np.array([int(ps.argmax())])
        if len(chosen) > MAX_SELECT:
            chosen = chosen[np.argsort(-ps[chosen])[:MAX_SELECT]]
        sel = torch.zeros((1, n), dtype=torch.bool, device=dev)
        sel[0, torch.as_tensor(chosen, device=dev)] = True
        _, tgt_l, dst_l = self.net.rest(h, glob, own, inputs[4], c, sel)
        target, dest = -1, None
        if cmd in POINTER:
            pt = torch.softmax(tgt_l[0] / tau, -1).double().cpu().numpy()
            target = int(rng.choice(n, p=pt / pt.sum()))
        elif cmd in MOVES:
            pd = torch.softmax(dst_l[0] / tau, -1).double().cpu().numpy()
            cell = int(rng.choice(len(pd), p=pd / pd.sum()))
            x, y = point_of(cell)
            dest = (x + rng.uniform(-CELL / 2, CELL / 2), y + rng.uniform(-CELL / 2, CELL / 2))
        return {"type": cmd, "select": [int(i) for i in chosen], "target": target, "dest": dest,
                "p_type": float(p[cmd])}


def load_fight_policy(path: str | Path, device: str = "cpu"):
    """The fight model or the command model, whichever the checkpoint holds."""
    from gary.policy.fight import FightModel
    kind = torch.load(path, map_location="cpu", weights_only=True)["config"].get("kind")
    return (CommandModel if kind == "command" else FightModel).load(path, device)

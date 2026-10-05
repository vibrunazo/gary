"""Gary's fight model: what each of its units does in a skirmish (the architecture's Policy).

Learned from pro replays (ingest/fight_dataset.py, trained by train/fight.py). Input: the units
around a fight as the player sees them (own, visible enemy, mineral fields): type, side,
position relative to the fight (mirrored so the player's main is top-left), HP, shields, weapon
cooldown, current order and its target, carrying, completed. A small transformer lets every unit
see every other. Output, per own unit: an action (ACTIONS: nothing, move, attack-move, attack a
unit, gather, right-click an own unit, stop, hold, stim, return cargo, other), the unit it
targets (a pointer into the set) and, for moves, where to (relative to the unit).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

ACTIONS = ["none", "move", "attack_move", "attack_unit", "gather", "own_unit", "stop", "hold",
           "stim", "return_cargo", "other"]
MAX_UNITS = 48
N_TYPES, N_ORDERS = 256, 256
POS_SCALE = 512.0               # pixels
DEST_SCALE = 512.0
# unit row columns (ingest/fight_dataset.py): type, side, x, y, hp, shields, cooldown, order,
# order target row, carrying, completed
TYPE, SIDE, X, Y, HP, SH, CD, ORDER, OTARGET, CARRY, DONE = range(11)


def numeric(units: np.ndarray, time_s: np.ndarray) -> np.ndarray:
    """(..., 9) float features from (..., 11) unit rows and the game time per snapshot (...)."""
    u = units.astype(np.float32)
    t = np.broadcast_to(time_s[..., None], u.shape[:-1])
    return np.stack([u[..., X] / POS_SCALE, u[..., Y] / POS_SCALE, np.minimum(u[..., HP], 2000) / 200.0,
                     np.minimum(u[..., SH], 1000) / 200.0, u[..., CD] / 30.0, (u[..., OTARGET] >= 0).astype(np.float32),
                     (u[..., CARRY] > 0).astype(np.float32), u[..., DONE], t / 600.0], axis=-1)


class FightNet(nn.Module):
    def __init__(self, d: int = 128, layers: int = 3, heads: int = 4):
        super().__init__()
        self.type_emb = nn.Embedding(N_TYPES, 48)
        self.side_emb = nn.Embedding(3, 8)
        self.order_emb = nn.Embedding(N_ORDERS, 16)
        self.inp = nn.Linear(48 + 8 + 16 + 9, d)
        layer = nn.TransformerEncoderLayer(d, heads, 4 * d, dropout=0.1, batch_first=True, norm_first=True)
        self.body = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.act = nn.Linear(d, len(ACTIONS))
        self.query = nn.Linear(d, d)                # pointer to the target unit
        self.key = nn.Linear(d, d)
        self.dest = nn.Linear(d, 2)                 # where to move, relative to the unit

    def forward(self, kind: torch.Tensor, side: torch.Tensor, order: torch.Tensor, num: torch.Tensor,
                pad: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """kind, side, order (B, N) long; num (B, N, 9); pad (B, N) True where there is no unit.
        Returns action logits (B, N, A), target logits (B, N, N), destinations (B, N, 2)."""
        h = self.inp(torch.cat([self.type_emb(kind), self.side_emb(side), self.order_emb(order), num], -1))
        h = self.body(h, src_key_padding_mask=pad)
        target = torch.einsum("bnd,bmd->bnm", self.query(h), self.key(h)) / h.shape[-1] ** 0.5
        target = target.masked_fill(pad[:, None, :], -1e9)
        return self.act(h), target, self.dest(h)


def tensors(units: np.ndarray, pad: np.ndarray, time_s: np.ndarray, device) -> tuple[torch.Tensor, ...]:
    """Model inputs from padded unit rows (B, N, 11), the padding mask (B, N) and time (B,)."""
    u = torch.as_tensor(units.astype(np.int64), device=device)
    return (u[..., TYPE].clamp(0, N_TYPES - 1), u[..., SIDE].clamp(0, 2), u[..., ORDER].clamp(0, N_ORDERS - 1),
            torch.as_tensor(numeric(units, time_s), device=device), torch.as_tensor(pad, device=device))


class FightModel:
    def __init__(self, net: FightNet, config: dict):
        self.net, self.config = net.eval(), config

    @classmethod
    def load(cls, path: str | Path, device: str = "cpu") -> "FightModel":
        ck = torch.load(path, map_location=device, weights_only=True)
        net = FightNet(**ck["config"]["net"])
        net.load_state_dict(ck["state"])
        model = cls(net.to(device), ck["config"])
        model.path = str(path)
        return model

    def save(self, path: str | Path) -> None:
        torch.save({"state": self.net.state_dict(), "config": self.config}, path)

    @torch.no_grad()
    def predict(self, units: np.ndarray, time_s: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """One snapshot: units (n, 11). Per unit: action probabilities (n, A), target probabilities
        (n, n), destination (n, 2) in pixels."""
        dev = next(self.net.parameters()).device
        n = min(len(units), MAX_UNITS)
        u = units[None, :n]
        pad = np.zeros((1, n), bool)
        act, target, dest = self.net(*tensors(u, pad, np.array([time_s], np.float32), dev))
        return (torch.softmax(act[0], -1).cpu().numpy(), torch.softmax(target[0], -1).cpu().numpy(),
                (dest[0] * DEST_SCALE).cpu().numpy())

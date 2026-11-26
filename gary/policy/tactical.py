"""The army's tactical intents (docs/TACTICAL_INTENT.md; option `intent`): the labeller of a cluster's intent, the
numbers the intent model reads, and the models (the intent's switch hazard and next intent, the defence's size).

Shared by the data (train/tactical_intent.py, on the army dataset's commitment ticks) and play
(gary/agent/tactical.py, on the army tracker's grid for the same cluster), so play reads what the data counted: every
number comes from the 16x16 grid (own army, enemy army in sight and seen in 30 s, own buildings, enemy buildings, the
cluster, own losses), the economy, the frame and the cluster's commitment. Race-agnostic: no unit type is named.

The intents (the labeller's rules, written before any table was read; the HOLD rule fixed 2026-11-26: a commitment
in force with its destination unknown is labelled by its kind, not as HOLD):
  DEFEND_BASE  enemy fighters at or next to a home cell (in sight, seen in 30 s, or own losses there) and the cluster is
               sent within a cell of it, or stands within 2 cells of it without a destination
  ATTACK       sent or committed to engage (a cell next to known enemy presence), not at home
  RETREAT      moved 2 cells or more nearer its main, from enemy fighters within 2 cells or fresh losses
  GATHER       any other move
  HOLD         no commitment in force and no new order
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

INTENTS = ("DEFEND_BASE", "ATTACK", "RETREAT", "GATHER", "HOLD")
GRID = 16
KEEP, ENGAGE, MOVE = 0, 1, 2
COMMIT_S = 120
FEATURES = ("minute", "own_army", "cluster_sup", "cluster_share", "army_near_cluster", "army_near_dest", "n_clusters",
            "enemy_army_now", "enemy_army_30", "enemy_bld_ever", "enemy_at_home", "threat_cells", "threat_sup",
            "loss_all", "loss_home", "loss_near", "near_enemy", "d_main", "d_enemy_bld", "d_enemy_army", "d_dest",
            "commit", "age", "minerals", "gas", "supply", "supply_max", "bases", "prev", "held")
SIZER_FEATURES = ("minute", "own_army", "threat_sup", "threat_cells", "loss_home", "d_threat_main", "n_clusters")


def cells(mask: np.ndarray) -> list[tuple[int, int]]:
    ys, xs = np.nonzero(mask.reshape(GRID, GRID))
    return list(zip(ys.tolist(), xs.tolist()))


def dist(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def near(c, cs, r) -> bool:
    return any(dist(c, x) <= r for x in cs)


def _within(grid_ch: np.ndarray, c, r) -> float:
    g = grid_ch.reshape(GRID, GRID)
    return float(g[max(0, c[0] - r):c[0] + r + 1, max(0, c[1] - r):c[1] + r + 1].sum())


class Scene:
    """What a cluster's moment holds, read once from its grid (9 channels as the army dataset's: own army, workers,
    buildings, enemy army / workers / buildings in sight, enemy buildings ever, enemy army seen in 30 s, the cluster)
    and its losses channel."""

    def __init__(self, grid: np.ndarray, loss: np.ndarray | None):
        g = grid.astype(np.int32)
        self.g = g
        self.loss = np.zeros(GRID * GRID, np.int32) if loss is None else loss.astype(np.int32)
        self.home = cells(g[2] > 0)
        self.main = min(self.home, key=lambda c: c[0] + c[1]) if self.home else (0, 0)
        self.enemy = cells((g[3] > 0) | (g[7] > 0))
        self.losses = cells(self.loss > 0)
        self.threat = [c for c in self.home if near(c, self.enemy, 1) or near(c, self.losses, 0)]
        cc = cells(g[8] > 0)
        self.center = cc[0] if cc else self.main
        en = (g[3] + g[7]).reshape(GRID, GRID)
        around = {(y + dy, x + dx) for y, x in self.threat for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                  if 0 <= y + dy < GRID and 0 <= x + dx < GRID}
        self.threat_sup = float(sum(en[y, x] for y, x in around)) / 2


def label(scene: Scene, label_: int, target: int | None, commit: int, dest: tuple | None) -> tuple[str, tuple | None]:
    """The cluster's intent at this tick, and the destination it carries on with ((cell, kind) or None). label_: what it did in the next tick (keep / engage / move), target: its order's
    cell; commit: the commitment in force (0 none, 1 engage, 2 move); dest: (cell, kind) of the order that made it, when
    known (else its kind alone decides)."""
    s = scene
    if label_ in (ENGAGE, MOVE) and target is not None and target >= 0:
        dest = (divmod(int(target), GRID), label_)
    elif commit == 0:
        dest = None
    kind = dest[1] if dest is not None else commit if commit else None
    to = dest[0] if dest is not None else None
    if s.threat and ((to is not None and near(to, s.threat, 1)) or (to is None and near(s.center, s.threat, 2))):
        return "DEFEND_BASE", dest
    if kind is None:
        return "HOLD", dest
    if kind == ENGAGE and (to is None or not near(to, s.home, 0)):
        return "ATTACK", dest
    if kind == MOVE and to is not None and dist(to, s.main) <= dist(s.center, s.main) - 2 and \
            (near(s.center, s.enemy, 2) or near(s.center, s.losses, 2)):
        return "RETREAT", dest
    return "GATHER", dest


def features(scene: Scene, eco, frame: int, commit: int, age: float, dest_cell: tuple | None, n_clusters: int,
             prev: str | None, held: int) -> dict:
    """The intent model's numbers for a cluster's moment (play and data alike)."""
    s, g = scene, scene.g
    army = float(g[0].sum())
    to = dest_cell
    return {"minute": frame / 1440, "own_army": army / 2, "cluster_sup": float(g[8].sum()) / 2,
            "cluster_share": float(g[8].sum()) / max(1.0, army), "army_near_cluster": _within(g[0], s.center, 2) / max(1.0, army),
            "army_near_dest": _within(g[0], to, 2) / max(1.0, army) if to is not None else 0.0, "n_clusters": n_clusters,
            "enemy_army_now": float(g[3].sum()) / 2, "enemy_army_30": float(g[7].sum()) / 2, "enemy_bld_ever": float(g[6].sum()),
            "enemy_at_home": float(sum(g[3].reshape(GRID, GRID)[c] + g[7].reshape(GRID, GRID)[c] for c in s.home)) / 2,
            "threat_cells": len(s.threat), "threat_sup": s.threat_sup, "loss_all": float(s.loss.sum()),
            "loss_home": float(sum(s.loss.reshape(GRID, GRID)[c] for c in s.home)),
            "loss_near": float(near(s.center, s.losses, 2)), "near_enemy": float(near(s.center, s.enemy, 2)),
            "d_main": dist(s.center, s.main), "d_enemy_bld": min((dist(s.center, c) for c in cells(g[6] > 0)), default=16),
            "d_enemy_army": min((dist(s.center, c) for c in s.enemy), default=16),
            "d_dest": dist(s.center, to) if to is not None else -1, "commit": commit, "age": min(float(age), COMMIT_S),
            "minerals": float(eco[0]), "gas": float(eco[1]), "supply": float(eco[2]) / 2, "supply_max": float(eco[3]) / 2,
            "bases": len(s.home), "prev": INTENTS.index(prev) if prev in INTENTS else -1, "held": min(held, 60)}


def sizer_features(scene: Scene, frame: int, n_clusters: int) -> dict:
    s = scene
    return {"minute": frame / 1440, "own_army": float(s.g[0].sum()) / 2, "threat_sup": s.threat_sup,
            "threat_cells": len(s.threat), "loss_home": float(sum(s.loss.reshape(GRID, GRID)[c] for c in s.home)),
            "d_threat_main": min((dist(c, s.main) for c in s.threat), default=0), "n_clusters": n_clusters}


class IntentModel:
    """The intent model (train/tactical_intent.py --train): a switch hazard (does the cluster's intent change in the next
    TICK s), the next intent given a switch, and the defence's size (the pros' supply sent or standing at a threatened
    base, a median)."""

    def __init__(self, d: dict, path: Path | None = None):
        self.d, self.path = d, path
        self.hazard, self.next, self.sizer = d["hazard"], d["next"], d.get("sizer")
        self.features, self.sizer_features = d["features"], d.get("sizer_features", SIZER_FEATURES)

    @classmethod
    def load(cls, path) -> "IntentModel":
        with open(path, "rb") as f:
            return cls(pickle.load(f), Path(path))

    def save(self, path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.d, f)

    def _x(self, x: dict, names) -> np.ndarray:
        return np.array([[float(x[n]) for n in names]], np.float32)

    def p_switch(self, x: dict) -> float:
        return float(self.hazard.predict_proba(self._x(x, self.features))[0, 1])

    def p_next(self, x: dict) -> np.ndarray:
        """Odds of each intent (INTENTS' order) given a switch; the current one 0."""
        p = self.next.predict_proba(self._x(x, self.features))[0]
        out = np.zeros(len(INTENTS))
        for c, v in zip(self.next.classes_, p):
            out[int(c)] = v
        if 0 <= int(x["prev"]) < len(INTENTS):
            out[int(x["prev"])] = 0.0
        return out / out.sum() if out.sum() > 0 else np.full(len(INTENTS), 1 / len(INTENTS))

    def defend_size(self, x: dict) -> float:
        """The pros' median supply defending a threatened base in this state (0 without a sizer)."""
        if self.sizer is None:
            return 0.0
        return max(0.0, float(self.sizer.predict(self._x(x, self.sizer_features))[0]))


def model_path(matchup: str, race: str) -> Path | None:
    """The newest intent model for the matchup and race (runs/intent/<matchup>_<race>_*/model.pkl)."""
    found = sorted((Path(__file__).resolve().parents[2] / "runs" / "intent").glob(f"{matchup}_{race}_*/model.pkl"))
    return found[-1] if found else None

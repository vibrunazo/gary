"""The enemy's plan from what the player has seen of it (docs/REFOCUS.md §3.1, Phase 1 step 6): the odds of each of the
pros' plans (taxonomy/plans.py), learned from the pros' games by train/plan_belief.py, and its inputs, the same in
training and in play.

Inputs (plan_features): the belief model's view of the enemy (gary/policy/belief.py: game time, each enemy type in
sight now, the most in sight at once over 30 s, 90 s and 3 minutes and ever, the seconds since an enemy army unit was in
sight), without the player's own supply and workers, with EXTRA_TYPES and the seconds since each type was first seen;
then the map (a category). One row a second of game time, the row of second s at frame 24 * s (ingest/macro_dataset.py
samples every 24 frames from frame 24).

In play (step 6) it only writes records: PlanMemory keeps the view, one look a second as the data samples it, and
PlanBelief answers from a pinned model file. It draws nothing.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

LURKER_EGG = 97
EXTRA_TYPES = {"Z": [LURKER_EGG]}  # types the plan's inputs take beside the belief model's (the egg tells lurkers)
FIRST_CAP = 600                    # s: since a type was first seen, at most (never seen: FIRST_CAP)


def plan_types(enemy: str) -> list[int]:
    from gary.policy.belief import ENEMY_TYPES
    return ENEMY_TYPES[enemy] + EXTRA_TYPES.get(enemy, [])


def plan_features(seen: np.ndarray, frames: np.ndarray, enemy: str, last_only: bool = False) -> np.ndarray:
    """(T, F) from seen (T, 228) enemy units in sight by type, a row a second: the belief model's view of the enemy
    (features_series without the player's own supply and workers), with EXTRA_TYPES and the seconds since each type was
    first seen. last_only: the last row alone (1, F), as play asks for it."""
    from gary.policy.belief import ARMY_SUPPLY, WINDOWS
    types = plan_types(enemy)
    army = np.array([t in ARMY_SUPPLY[enemy] for t in types])
    s = seen[:, types].astype(np.float32)
    ever = np.maximum.accumulate(s, axis=0)
    first = np.where((ever > 0).any(0), np.argmax(ever > 0, axis=0), -1)
    out, last = [], -10 ** 6
    for t in range(len(s)):
        if s[t, army].sum() > 0:
            last = t
        if last_only and t < len(s) - 1:
            continue
        maxes = [s[max(0, t - w + 1):t + 1].max(0) for w in WINDOWS]
        since_first = np.where((first >= 0) & (first <= t), np.minimum(t - first, FIRST_CAP), FIRST_CAP) / FIRST_CAP
        out.append(np.concatenate([[frames[t] / 24.0 / 600.0], np.log1p(s[t]), *[np.log1p(m) for m in maxes],
                                   np.log1p(ever[t]), since_first, [min(t - last, 600) / 600.0]]).astype(np.float32))
    return np.stack(out)


class PlanMemory:
    """The player's view of the enemy in play, one look a second (the first look in each second; a second with none
    repeats the last)."""

    def __init__(self, enemy: str):
        self.enemy = enemy
        self.rows: list[np.ndarray] = []           # row k: second k + 1 (frame 24 (k + 1)), seen counts by type id

    def look(self, frame: int, obs_units: list[dict], slot: int) -> None:
        sec = frame // 24
        if sec < 1 or sec <= len(self.rows):
            return
        seen = np.zeros(228, np.float32)
        for u in obs_units:
            if u["owner"] not in (slot, 11) and 0 <= u["type"] < 228:
                seen[u["type"]] += 1
        while len(self.rows) < sec - 1:            # (seconds without a look: the last one again)
            self.rows.append(self.rows[-1] if self.rows else np.zeros(228, np.float32))
        self.rows.append(seen)

    def features(self) -> np.ndarray | None:
        if not self.rows:
            return None
        frames = 24 * np.arange(1, len(self.rows) + 1)
        return plan_features(np.stack(self.rows), frames, self.enemy, last_only=True)[0]


class PlanBelief:
    """A saved train/plan_belief.py model (--save), pinned by its path: the odds of each plan."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        saved = pickle.load(open(path, "rb"))
        self.clf, self.maps, self.names = saved["model"], saved["maps"], saved["names"]
        self.sightings = bool(saved.get("sightings"))

    def odds(self, row: np.ndarray, map_name: str | None, sightings: np.ndarray | None = None) -> dict[str, float]:
        m = self.maps.index(map_name) if map_name in self.maps else 0
        extra = [] if not self.sightings else (sightings if sightings is not None else np.full(14, np.nan, np.float32))
        X = np.concatenate([row, extra, [m]])[None]
        p = np.zeros(len(self.names))
        p[self.clf.classes_] = self.clf.predict_proba(X)[0]
        return {self.names[k]: float(p[k]) for k in range(len(p))}

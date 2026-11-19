"""Out of contact: where a player's fighters are placed when no enemy fighter is near (docs/PROGRESS.md, 2026-11-18:
the pros give a standing fighter out of contact 2.0 short orders a minute, Gary 0.5; the army data labels any order
under two army cells "keep", and the role model moves units only in a fight).

The calm model is a role network (gary/policy/roles.py RoleNet) over a snapshot around a bunch of calm fighters,
the same rows and extras as the role model's, deciding for each calm fighter over the next half second one of NAMES:
  keep     no command reached it
  other    a command that isn't a point (a unit right-clicked, stop, hold, stim, a mode)
  far      a point under the army data's reach (ingest/army_dataset.py MOVED cells or more): the commit model's
  reclick  a moving unit's point clicked again (within RECLICK of where it was going): the hands' spam, not a decision
  again    a short point order (under MOVED cells): what this layer carries out, to where the offset head points
The pros give a short order to a bunch (a median 10 units, every one's target the click), so the where is one per
command: its point from the commanded units' middle, learned at every such command (where snapshots, ingest/calm_dataset.py),
drawn once per bunch in play from its units' odds.
Built from the pros' games by ingest/calm_dataset.py, trained by train/roles.py --again (its offset head), played
by gary/agent/calm.py."""
from __future__ import annotations

import math

import numpy as np

from gary.policy.roles import AGAIN

NAMES = ["keep", "other", "far", "reclick", AGAIN]
CALM_SIGHT = 12 * 32          # a fighter with no seen enemy fighter this near is calm (ingest/response_dataset.py SIGHT:
                              # nearer, the role model's)
BUNCH = 8 * 32                # calm fighters this near the bunch's seed are decided in one snapshot
AROUND_OWN = 24 * 32          # the snapshot: own units this near its center (the role datasets' own radius)
AROUND_OTHER = 12 * 32        # ...the enemy's seen units and the resources this near (gary/policy/fight.py FIGHT_AROUND)
RECLICK = 2 * 32              # a moving unit's target this near the click: the same destination clicked again
MOVED = 2                     # army cells (ingest/army_dataset.py MOVED): an order this far is the commit model's
GRID = 16                     # (ingest/army_dataset.py GRID)
POINT_ORDERS = {14}           # an order command with a point that places a unit (attack-move); right-click on ground too


FAR_EDGES = (0.0, 12.0, 20.0, 28.0, 40.0, 56.0, 80.0, 112.0, 160.0)   # tiles: the far points' distances (the calm_far
                              # model's drawn head, train/roles.py --offset-edges)
SMALL = 8                     # (supply x2) a bunch under this the commit model isn't asked about (gary/agent/army.py
                              # MIN_SUP): its far orders are the calm layer's, to the calm_far model's points
MAP_EXTRA = 4                 # the calm model's own extras after the role model's: the way to the main's ramp top and to
                              # the map's middle (mirrored as the rows, / GROUND_SCALE): placement out of contact is
                              # geography, which the role extras give only as distances (the nearest Command Center apart)


def map_extras(tags: list[int], positions: dict, ground, mw: int, mh: int, flip: tuple[bool, bool]) -> np.ndarray:
    """(n, MAP_EXTRA) per unit: the way to its main's ramp top (zeros without a reliable one) and to the map's middle."""
    from gary.policy.roles import GROUND_SCALE
    out = np.zeros((len(tags), MAP_EXTRA), np.float32)
    fx, fy = (-1 if flip[0] else 1), (-1 if flip[1] else 1)
    ramp = getattr(ground, "ramp_top", None) if ground is not None else None
    for i, t in enumerate(tags):
        if t not in positions:
            continue
        x, y = positions[t]
        if ramp is not None:
            out[i, 0], out[i, 1] = fx * (ramp[0] - x) / GROUND_SCALE, fy * (ramp[1] - y) / GROUND_SCALE
        out[i, 2], out[i, 3] = fx * (mw / 2 - x) / GROUND_SCALE, fy * (mh / 2 - y) / GROUND_SCALE
    return out


def army_cell(x: float, y: float, mw: int, mh: int) -> tuple[int, int]:
    """The army data's cell (row, column) of a point; mirroring doesn't change distances between cells."""
    return min(GRID - 1, max(0, int(y * GRID // mh))), min(GRID - 1, max(0, int(x * GRID // mw)))


def calm_fighters(obs: dict, slot: int, supply_x2, is_worker, is_building) -> list[dict]:
    """The player's completed fighters with no enemy fighter it sees within CALM_SIGHT (obs: the player's view)."""
    fighter = lambda u: supply_x2(u["type"]) > 0 and not is_worker(u["type"]) and not is_building(u["type"])
    mine = [u for u in obs["units"] if u["owner"] == slot and u["completed"] and fighter(u)]
    foes = np.array([(u["x"], u["y"]) for u in obs["units"] if u["owner"] not in (slot, 11) and fighter(u)]
                    or [(1e9, 1e9)], np.float64)
    return [u for u in mine if np.sqrt(((foes - (u["x"], u["y"])) ** 2).sum(1)).min() > CALM_SIGHT]


def bunches(calm: list[dict]) -> list[list[dict]]:
    """Calm fighters in bunches: the one with the most calm fighters within BUNCH and those, again with the rest."""
    left, out = sorted(calm, key=lambda u: u["tag"]), []
    while left:
        near = lambda s: [u for u in left if math.dist((u["x"], u["y"]), (s["x"], s["y"])) <= BUNCH]
        seed = max(left, key=lambda s: len(near(s)))
        group = near(seed)
        out.append(group)
        ids = {u["tag"] for u in group}
        left = [u for u in left if u["tag"] not in ids]
    return out


def snapshots(obs: dict, slot: int, flip: tuple[bool, bool], supply_x2, is_worker, is_building, max_units: int):
    """[(rows, tags, center, calm tags)]: one snapshot per bunch of calm fighters, rows as the role model's
    (gary/policy/fight.py rows_at), centered on the bunch."""
    from gary.policy.fight import rows_at
    out = []
    for group in bunches(calm_fighters(obs, slot, supply_x2, is_worker, is_building)):
        cx = sum(u["x"] for u in group) / len(group)
        cy = sum(u["y"] for u in group) / len(group)
        rows, tags = rows_at(obs, slot, flip, (cx, cy), AROUND_OWN, AROUND_OTHER, max_units)
        out.append((rows, tags, (cx, cy), {u["tag"] for u in group}))
    return out

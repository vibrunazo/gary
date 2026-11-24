"""Where a player has looked: the three sighting states of docs/REFOCUS.md §3.1 (seen, confirmed absent, unscouted), for
the enemy-plan belief (train/plan_belief.py). The belief's sighting counts (gary/policy/belief.py) say what was seen;
they can't say what was looked for and not found, so "no tech building seen by 8:00" read as evidence for a pro, who
looks, and as the same evidence for Gary, who doesn't (docs/PROGRESS.md 2026-11-23: Gary had seen the Zerg's tech by
6:00 in 5% of its games, the pros 60%). This keeps, per base, when the player last had a unit near it and what stood
there then, so absence counts only where the player looked.

The same in the data (ingest/sighting_dataset.py, from re-simulated pro games, the player's view) and in play: the
player's units, the enemy units it sees, the map's bases (gary/mapinfo.py). The enemy's main is known once an enemy
building is seen at a start location, or when one start is left (two-player maps from the start).
"""
from __future__ import annotations

import math

import numpy as np

LOOK = 8 * 32                 # px: a unit of the player's this near a base's center has looked at it
HALL_NEAR = 6 * 32            # px: an enemy town hall this near a base's center stands at that base
RECENT = 180                  # s: the other bases looked at within this
CAP = 600                     # s: since the last look, at most (never looked: CAP)
N = 7                         # the features
OWN_HALLS = {106, 131, 132, 133, 154}   # every race's town halls: a base the player holds isn't looked at


MAIN_BUILDING = 12 * 32       # px: an enemy building this near a start: the enemy's main
START_EMPTY = 6 * 32          # px: a unit of the player's this near a start with no enemy building in sight: not there


class EnemyMain:
    """Where the enemy's main is, for every race and map, in one place (Gary's g.enemy_main, the sighting states): the
    start where an enemy building was seen; or the one start left once the others were found empty; or, on a map with
    one start for the enemy, that one. Until 2026-11-23 only the army's scout under option `watch` set it, so the tech
    scan of answers.py couldn't fire on a map with more than one enemy start (all 20 scans of RD285a were on two maps
    of eight)."""

    def __init__(self, starts: list[tuple[float, float]], is_building) -> None:
        """starts: the enemy's possible start locations (px); is_building(type) -> bool."""
        self.starts = [tuple(s) for s in starts]
        self.is_building = is_building
        self.empty: set[int] = set()                   # starts a unit of the player's found empty
        self.main: tuple[float, float] | None = self.starts[0] if len(self.starts) == 1 else None

    def look(self, mine: list[tuple[float, float]], enemy: list[dict]) -> tuple[float, float] | None:
        """mine: the player's units' positions; enemy: the enemy units it sees."""
        if self.main is not None:
            return self.main
        for k, s in enumerate(self.starts):
            if k in self.empty:
                continue
            if any(self.is_building(u["type"]) and math.dist((u["x"], u["y"]), s) <= MAIN_BUILDING for u in enemy):
                self.main = s
                return s
            if any(math.dist(p, s) <= START_EMPTY for p in mine):
                self.empty.add(k)
        left = [s for k, s in enumerate(self.starts) if k not in self.empty]
        if len(left) == 1:
            self.main = left[0]
        return self.main


class SightingState:
    def __init__(self, mapinfo, slot: int, own_start: tuple[int, int], halls: set[int], buildings) -> None:
        """mapinfo: the map's bases and starts; halls: the enemy race's town-hall types; buildings(type) -> bool."""
        self.bases = list(mapinfo.bases)
        self.slot = slot
        self.own = min(self.bases, key=lambda b: math.dist(b.center, own_start))
        self.starts = [b for b in self.bases if b.start and b is not self.own]
        self.halls, self.is_building = halls, buildings
        self.mapinfo = mapinfo
        self.own_nat = mapinfo.natural_of(self.own)
        self.own_halls: set[int] = set()               # bases where the player has its own town hall (not looked at)
        self.last_look: dict[int, int] = {}            # base index -> frame of the last look
        self.hall_at_look: dict[int, bool] = {}        # base index -> an enemy hall stood there at that look
        self.enemy_main = self.starts[0] if len(self.starts) == 1 else None
        self.looked_starts: set[int] = set()

    def look(self, units: list[dict], frame: int) -> None:
        """One look: units, the player's view (its own units and the enemy units it sees)."""
        mine = np.array([(u["x"], u["y"]) for u in units if u["owner"] == self.slot] or [(-1e9, -1e9)], np.float64)
        enemy = [u for u in units if u["owner"] not in (self.slot, 11)]
        own_halls = [(u["x"], u["y"]) for u in units if u["owner"] == self.slot and u["type"] in OWN_HALLS]
        for k, b in enumerate(self.bases):
            if any(math.dist(h, b.center) <= HALL_NEAR for h in own_halls):
                self.own_halls.add(k)
            if b is self.own or b is self.own_nat or k in self.own_halls:
                continue
            if np.sqrt(((mine - b.center) ** 2).sum(1)).min() <= LOOK:
                self.last_look[k] = frame
                self.hall_at_look[k] = any(u["type"] in self.halls and math.dist((u["x"], u["y"]), b.center) <= HALL_NEAR
                                           for u in enemy)
                if b.start:
                    self.looked_starts.add(k)
        if self.enemy_main is None:
            for b in self.starts:                      # an enemy building at a start: its main
                if any(self.is_building(u["type"]) and math.dist((u["x"], u["y"]), b.center) <= 12 * 32 for u in enemy):
                    self.enemy_main = b
                    break
            left = [b for b in self.starts if self.bases.index(b) not in self.looked_starts]
            if self.enemy_main is None and len(left) == 1:
                self.enemy_main = left[0]

    def _since(self, base, frame: int) -> float:
        k = self.bases.index(base)
        return min(CAP, (frame - self.last_look[k]) / 24) if k in self.last_look else CAP

    def features(self, frame: int) -> np.ndarray:
        """(N,): main known; seconds since the enemy main was looked at (while unknown: since any start was); since
        its natural was; a hall at the natural at that look (-1 never looked); the other bases looked at within RECENT
        and how many showed a hall; the starts left unlooked (scaled)."""
        if self.enemy_main is not None:
            main_since = self._since(self.enemy_main, frame)
            nat = self.mapinfo.natural_of(self.enemy_main)
            nat_since = self._since(nat, frame)
            k = self.bases.index(nat)
            nat_hall = (1.0 if self.hall_at_look[k] else 0.0) if k in self.hall_at_look else -1.0
            skip = {self.bases.index(self.enemy_main), k}
        else:
            main_since = min([self._since(b, frame) for b in self.starts] or [CAP])
            nat_since, nat_hall, skip = CAP, -1.0, set()
        others = [k for k in self.last_look if k not in skip and k not in self.own_halls
                  and (frame - self.last_look[k]) / 24 <= RECENT]
        halls = sum(1 for k in others if self.hall_at_look.get(k))
        unlooked = sum(1 for b in self.starts if self.bases.index(b) not in self.looked_starts)
        return np.array([float(self.enemy_main is not None), main_since / CAP, nat_since / CAP, nat_hall,
                         len(others) / 4.0, halls / 4.0, unlooked / 3.0], np.float32)

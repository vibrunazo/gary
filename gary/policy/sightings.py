"""Where a player has looked, and what it found: the three sighting states of docs/REFOCUS.md §3.1 (seen, confirmed
absent, unscouted), §4.2's SightingState, for the enemy-plan belief (train/plan_belief.py), every race and matchup.

The belief's sighting counts (gary/policy/belief.py) say what was seen; they can't say what was looked for and not found,
so "no tech building seen by 8:00" read as evidence for a pro, who looks, and as the same evidence for Gary, who doesn't
(docs/PROGRESS.md 2026-11-23). This keeps, per region (each base of the map but the player's own), when the player last
looked at it, how much of it the look covered, and which of the enemy's halls and tech stood there then: absence counts
only where the player looked, and a stale look is not "never checked".

A look is how much of a region the player had in sight: the share of its points (every STEP within REGION of its
center, nearer it than any other base) within sight of a unit or building of the player's (SIGHT, Brood War's radii;
a ground unit or building sees nothing on higher ground, a flyer and a scan see every height) or of a Comsat scan.
Without the heights, 64% of the model's wrong calls in TvT were an eye below the building it was said to see (the
pros' games, 2026-11-23). A unit near the region's center was the first try, and the pros' games refuted it
(docs/PROGRESS.md 2026-11-23, eval/scouting.py): it caught 18-73% of their sights of the enemy's tech, and 9-55% of
its "looks" had tech standing out of sight. A scan is no unit in the observation (only the place it shows turns
visible: checked on a pro game, 2026-11-23), so its point is given to look() (in play Gary's own scan, in the data the
replay's command). A region is looked at with any cover, and the plan's tech confirmed absent there only by a look of
ABSENT_COVER or more that found none.

The same in the data (ingest/sighting_dataset.py, re-played games, the player's view) and in play. The enemy's main is
EnemyMain's, the one shared place (Gary's g.enemy_main).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

REGION = 14 * 32              # px: a region's points (and the enemy's buildings in it) this near its center
STEP = 2 * 32                 # px: between a region's points
SCAN_SEES = 10 * 32           # px: a scan's sight
ABSENT_COVER = 0.5            # a look this covering that found none of the plan's tech: confirmed absent
# sight radii in tiles (Brood War's), by type; others DEFAULT_SIGHT (a building BUILDING_SIGHT)
SIGHT = {0: 7, 1: 9, 2: 8, 3: 8, 5: 10, 30: 10, 7: 7, 8: 7, 9: 10, 11: 8, 12: 11, 32: 7, 34: 9, 58: 8,
         37: 5, 38: 6, 39: 7, 41: 7, 42: 9, 43: 7, 44: 11, 45: 10, 46: 10, 47: 5, 62: 10, 103: 8, 35: 4, 36: 4, 97: 4,
         13: 3, 64: 8, 65: 7, 66: 8, 67: 7, 68: 8, 69: 8, 70: 8, 71: 9, 72: 11, 73: 6, 83: 10, 84: 9, 60: 9, 61: 7, 63: 10,
         106: 10, 124: 11, 131: 9, 132: 10, 133: 11, 154: 11, 156: 8, 162: 11, 144: 10, 146: 10}
DEFAULT_SIGHT, BUILDING_SIGHT = 7, 9
RECENT = 180                  # s: the other regions looked at within this
CAP = 600                     # s: since a look, at most (never: CAP)
HALLS = {"Z": (131, 132, 133), "T": (106,), "P": (154,)}
OWN_HALLS = {t for v in HALLS.values() for t in v}   # a region the player holds isn't looked at
# the tech that tells each race's plan (taxonomy/label_all.py's rules: the Zerg's Spire or Hydralisk Den, the Terran's
# Factory or Starport, the Protoss's Robotics Facility, Citadel of Adun or Stargate), and the other tech kept as seen
# (a Lair tells no plan)
PLAN_TECH = {"Z": (141, 137, 135), "T": (113, 114), "P": (155, 163, 167)}
OTHER_TECH = {"Z": (132, 133, 138, 142, 139), "T": (111, 112, 116, 123, 120, 122), "P": (160, 164, 165, 159, 166)}
N = 14                        # the features

MAIN_BUILDING = 20 * 32       # px: an enemy building this near a start, and nearer it than any other: the enemy's main
                              # (12 until 2026-11-23: the pros see the main's buildings from its edge, a Probe 17 tiles
                              # from the Command Center seeing the Factory and the Barracks)
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
        for u in enemy:                                # (a building overrides a start found empty: a unit near a start
            if not self.is_building(u["type"]):        # that couldn't see it, up a cliff, must not lose the main)
                continue
            s = min(self.starts, key=lambda s: math.dist((u["x"], u["y"]), s))
            if math.dist((u["x"], u["y"]), s) <= MAIN_BUILDING:
                self.main = s
                return s
        for k, s in enumerate(self.starts):
            if k not in self.empty and any(math.dist(p, s) <= START_EMPTY for p in mine):
                self.empty.add(k)
        left = [s for k, s in enumerate(self.starts) if k not in self.empty]
        if len(left) == 1:
            self.main = left[0]
        return self.main


def sight_px(unit_type: int) -> float:
    from gary.policy.army import is_building
    return SIGHT.get(unit_type, BUILDING_SIGHT if is_building(unit_type) else DEFAULT_SIGHT) * 32


def region_points(mapinfo) -> list[np.ndarray]:
    """Each base's points: every STEP within REGION of its center, nearer it than any other base, on the map."""
    centers = np.array([b.center for b in mapinfo.bases], np.float64)
    w, h = mapinfo.size
    out = []
    for k, c in enumerate(centers):
        xs = np.arange(c[0] - REGION, c[0] + REGION + 1, STEP)
        ys = np.arange(c[1] - REGION, c[1] + REGION + 1, STEP)
        pts = np.array([(x, y) for x in xs for y in ys if 0 <= x < w and 0 <= y < h
                        and (x - c[0]) ** 2 + (y - c[1]) ** 2 <= REGION ** 2], np.float64).reshape(-1, 2)
        if len(pts):
            near = np.argmin(((pts[:, None, :] - centers[None]) ** 2).sum(-1), 1)
            pts = pts[near == k] if (near == k).any() else pts[:1]
        out.append(pts)
    return out


def covered(pts: np.ndarray, eyes: np.ndarray, radii: np.ndarray, eye_h: np.ndarray | None = None,
            pt_h: np.ndarray | None = None) -> np.ndarray:
    """(len(pts),) bool: each point within any eye's radius (eyes (n, 2) px, radii (n,) px), and with the heights
    (eye_h (n,), pt_h (len(pts),)) not above the eye's."""
    if not len(eyes) or not len(pts):
        return np.zeros(len(pts), bool)
    inside = ((pts[:, None, :] - eyes[None]) ** 2).sum(-1) <= radii[None] ** 2
    if eye_h is not None and pt_h is not None:
        inside &= eye_h[None, :] >= pt_h[:, None]
    return inside.any(1)


SEES_ALL = 9                  # an eye's height that sees every height (a flyer, a scan)


def height_at(heights, points) -> np.ndarray:
    """Ground heights (0 low, 1 middle, 2 high) at pixel points, from Game.terrain()'s minitile grid (None: none)."""
    pts = np.asarray(points, np.float64).reshape(-1, 2)
    if heights is None or not len(pts):
        return None
    ys = np.clip((pts[:, 1] // 8).astype(int), 0, heights.shape[0] - 1)
    xs = np.clip((pts[:, 0] // 8).astype(int), 0, heights.shape[1] - 1)
    return heights[ys, xs].astype(np.int16)


def eye_heights(heights, units: list[dict], scans) -> np.ndarray | None:
    """Each eye's height: a flyer's and a scan's SEES_ALL, a ground unit's or building's its ground's."""
    if heights is None:
        return None
    from gary.races import FLYERS
    h = height_at(heights, [(u["x"], u["y"]) for u in units])
    h = h if h is not None else np.zeros(0, np.int16)
    h = np.where([u["type"] in FLYERS for u in units], SEES_ALL, h) if len(units) else h
    return np.concatenate([h, np.full(len(scans), SEES_ALL, np.int16)]).astype(np.int16)


@dataclass
class Region:
    """A region's last look: its frame, the share of it in sight, and the enemy's hall and tech in sight in it then."""
    frame: int
    cover: float
    hall: bool
    tech: frozenset


class SightingState:
    """§4.2's SightingState: seen (enemy type -> (most in sight at once, last frame)), confirmed_absent (region -> the
    frame of its last look, which found none of the plan's tech), unscouted (the regions never looked at); and per
    region its last look (staleness and cover)."""

    def __init__(self, mapinfo, slot: int, own_start: tuple[int, int], enemy: str, is_building, heights=None) -> None:
        """mapinfo: the map's bases (the regions); slot: the player's; own_start: its main (px); enemy: the enemy's race
        letter; is_building(type) -> bool; heights: Game.terrain()'s ground heights (None: every height seen)."""
        self.heights = heights
        self.bases = list(mapinfo.bases)
        self.slot, self.enemy, self.mapinfo = slot, enemy, mapinfo
        self.own = min(self.bases, key=lambda b: math.dist(b.center, own_start))
        self.own_nat = mapinfo.natural_of(self.own)
        self.main = EnemyMain([b.center for b in self.bases if b.start and b is not self.own], is_building)
        self.halls, self.plan_tech = set(HALLS[enemy]), set(PLAN_TECH[enemy])
        self.kept = self.halls | self.plan_tech | set(OTHER_TECH[enemy])
        self.own_halls: set[int] = set()               # regions where the player has a town hall
        self.points = region_points(mapinfo)
        self.point_h = [height_at(heights, p) for p in self.points]
        self.regions: dict[int, Region] = {}           # region -> its last look
        self._seen: dict[int, tuple[int, int]] = {}    # enemy type -> (most in sight at once, last frame)
        self.plan_first: int | None = None             # frame the plan's tech was first seen

    # §4.2's three states
    @property
    def seen(self) -> dict[int, tuple[int, int]]:
        return dict(self._seen)

    @property
    def confirmed_absent(self) -> dict[int, int]:
        return {k: r.frame for k, r in self.regions.items() if r.cover >= ABSENT_COVER and not (r.tech & self.plan_tech)}

    @property
    def unscouted(self) -> frozenset[int]:
        return frozenset(k for k in range(len(self.bases)) if k not in self.regions and not self._mine(k))

    def _mine(self, k: int) -> bool:
        b = self.bases[k]
        return b is self.own or b is self.own_nat or k in self.own_halls

    def look(self, units: list[dict], frame: int, scans: tuple = ()) -> None:
        """One look: units, the player's view (its own units and the enemy units it sees); scans, the points of the
        player's scans showing now."""
        mine = [u for u in units if u["owner"] == self.slot]
        enemy = [u for u in units if u["owner"] not in (self.slot, 11)]
        pos = np.array([(u["x"], u["y"]) for u in mine] or [(-1e9, -1e9)], np.float64)
        eyes = np.array([(u["x"], u["y"]) for u in mine] + [tuple(p) for p in scans], np.float64).reshape(-1, 2)
        radii = np.array([sight_px(u["type"]) for u in mine] + [SCAN_SEES] * len(scans), np.float64)
        eye_h = eye_heights(self.heights, mine, scans)
        counts: dict[int, int] = {}
        for u in enemy:
            if u["type"] in self.kept:
                counts[u["type"]] = counts.get(u["type"], 0) + 1
        for t, n in counts.items():
            self._seen[t] = (max(n, self._seen.get(t, (0, 0))[0]), frame)
        if self.plan_first is None and any(t in self.plan_tech for t in counts):
            self.plan_first = frame
        for k, b in enumerate(self.bases):
            if any(u["type"] in OWN_HALLS and math.dist((u["x"], u["y"]), b.center) <= 6 * 32 for u in mine):
                self.own_halls.add(k)
            if self._mine(k):
                continue
            near = ((eyes - b.center) ** 2).sum(1) <= (REGION + radii) ** 2 if len(eyes) else np.zeros(0, bool)
            cover = float(covered(self.points[k], eyes[near], radii[near], eye_h[near] if eye_h is not None else None,
                                  self.point_h[k]).mean()) \
                if near.any() and len(self.points[k]) else 0.0
            there = [u for u in enemy if u["type"] in self.kept and math.dist((u["x"], u["y"]), b.center) <= REGION
                     and self.mapinfo.base_near((u["x"], u["y"])) is b]
            if cover > 0 or there:
                self.regions[k] = Region(frame, cover, any(u["type"] in self.halls for u in there),
                                         frozenset(u["type"] for u in there))
        self.main.look([tuple(p) for p in pos], enemy)

    def _region(self, base) -> Region | None:
        return self.regions.get(self.bases.index(base)) if base is not None else None

    def features(self, frame: int) -> np.ndarray:
        """(N,), every race alike: the enemy's main known; for its main and its natural (while the main is unknown: the
        start looked at last, and no natural): seconds since the last look, its cover, a hall there then and the plan's
        tech there then (-1: never looked); the other regions looked at within RECENT and how many showed a hall; the
        starts never looked at; the plan's tech seen anywhere, and the seconds since it first was."""
        since = lambda r: (min(CAP, (frame - r.frame) / 24) if r is not None else CAP) / CAP
        known = self.main.main is not None
        if known:
            main = self.mapinfo.base_near(self.main.main)
            nat = self.mapinfo.natural_of(main)
        else:
            looked = [b for b in self.bases if b.start and b is not self.own and self._region(b) is not None]
            main = max(looked, key=lambda b: self._region(b).frame) if looked else None
            nat = None
        out = [float(known)]
        for b in (main, nat):
            r = self._region(b)
            out += [since(r), r.cover if r else 0.0, float(r.hall) if r else -1.0,
                    float(bool(r.tech & self.plan_tech)) if r else -1.0]
        skip = {self.bases.index(b) for b in (main, nat) if b is not None}
        others = [k for k, r in self.regions.items() if k not in skip and not self._mine(k)
                  and (frame - r.frame) / 24 <= RECENT]
        unlooked = sum(1 for k, b in enumerate(self.bases) if b.start and b is not self.own and k not in self.regions)
        out += [len(others) / 4.0, sum(1 for k in others if self.regions[k].hall) / 4.0, unlooked / 3.0,
                float(self.plan_first is not None),
                (min(CAP, (frame - self.plan_first) / 24) if self.plan_first is not None else CAP) / CAP]
        return np.array(out, np.float32)

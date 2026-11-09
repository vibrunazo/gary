"""Where a building decided now stands: its base (the main, the natural, a newer base) and its side of it (the front,
or by the minerals), learned from the pros' buildings (ingest/placement_dataset.py, train/placement.py; #65). It
replaced the pros' placement table (a stop-gap blind to the game, gp0.21dev): the pros' cannons go by a mineral line
once they have seen a Spire or Mutalisks, the table's went on schedule.

The inputs, the dataset's: per base its town hall, buildings, of this type, static defense, workers and recent losses
(BASE_FEATURES); the minute, how many of this type the player had started, the bases held; the building type and the
build style (categories); the enemy units in sight now and the most of each type seen at once (log1p, the enemy race's
types: gary/races.py)."""

from __future__ import annotations

import math
import pickle
from pathlib import Path

import numpy as np

BASES = ("main", "natural", "newer")
SIDES = ("front", "minerals")
CLASSES = [(b, s) for b in BASES for s in SIDES]      # class = base * 2 + side
BASE_FEATURES = ("hall", "buildings", "same", "static", "workers", "workers_lost", "buildings_lost")
LOSS_S = 60                    # losses this recent count
GONE = 72                      # frames: a unit gone this long and not back is lost (a worker in a gas building comes back)
NEAR = 10 * 32                 # px: a unit this near a base's centre is at it
HELD = 6 * 32                  # px: a town hall this near a base's centre holds it
LOOK_EVERY = 48                # frames between the losses' looks (the dataset's)


def kinds(R) -> list[int]:
    """The race's buildings placed by the model (town halls and gas aside: the executor places those itself; a Terran
    add-on stands where its building's room is), in the order of the type's category."""
    addons = set(getattr(R.data, "ADDON_PARENT", {}))
    return sorted(t for t in R.sizes if t not in R.town_halls and t != R.gas_building and t not in addons)


class Losses:
    """The player's own workers and buildings lost, as the dataset counts them: gone since the last look, lost once
    gone GONE frames and not back."""

    def __init__(self, R):
        self.R = R
        self.prev: dict = {}
        self.gone: dict = {}          # tag -> (frame, x, y, a worker)
        self.types: dict = {}         # every own unit's type by tag, as first seen (play's count of a building started)
        self.last = -1 << 30

    def look(self, frame: int, mine: dict) -> None:
        """mine: the player's units by tag, now."""
        R = self.R
        for tag, u in self.prev.items():
            if tag not in mine and (u["type"] == R.worker or u["type"] in R.sizes):
                self.gone[tag] = (frame, u["x"], u["y"], u["type"] == R.worker)
        for tag in [t for t in self.gone if t in mine]:
            del self.gone[tag]
        for tag, u in mine.items():
            self.types.setdefault(tag, u["type"])
        self.prev, self.last = mine, frame

    def started(self, uid: int, mine: list[dict]) -> int:
        """How many of this building the player has started: the dataset's count when it decides one more."""
        return len({t for t, k in self.types.items() if k == uid} | {u["tag"] for u in mine if u["type"] == uid})

    def recent(self, frame: int) -> list[tuple]:
        return [(x, y, w) for f, x, y, w in self.gone.values() if GONE <= frame - f < LOSS_S * 24]


def newer_bases(bases, main, natural, own: list[dict], R) -> list:
    """The bases other than the main and the natural with one of the player's town halls (finished or not)."""
    halls = [(v["x"], v["y"]) for v in own if v["type"] in R.town_halls]
    return [b for b in bases if b is not main and b is not natural and any(math.dist(b.center, h) < HELD for h in halls)]


def base_features(own: list[dict], uid: int, main, natural, newer: list, R, static, lost: list[tuple]) -> list:
    """(3, BASE_FEATURES): per base kind (the main, the natural, the newer bases together) the player's units there."""
    feats = []
    for at in ([main], [natural] if natural is not None else [], newer):
        near = lambda x, y: any(math.dist(b.center, (x, y)) < NEAR for b in at)
        here = [v for v in own if near(v["x"], v["y"])]
        gone = [w for x, y, w in lost if near(x, y)]
        feats.append([float(any(v["type"] in R.town_halls for v in here)),
                      sum(1 for v in here if v["type"] in R.sizes and v["type"] not in R.town_halls),
                      sum(1 for v in here if v["type"] == uid),
                      sum(1 for v in here if v["type"] in static),
                      sum(1 for v in here if v["type"] == R.worker),
                      sum(1 for w in gone if w), sum(1 for w in gone if not w)])
    return feats


def enemy_types(matchup: str, race: str) -> list[int]:
    """The enemy race's unit and building ids the seen inputs keep."""
    from gary.races import enemy_of
    e = enemy_of(matchup, race)
    return sorted(set(e.names) & set(range(228)))


def encode(bases: np.ndarray, glob: np.ndarray, kind: np.ndarray, style: np.ndarray, seen: np.ndarray,
           seen_max: np.ndarray, types: list[int]) -> np.ndarray:
    """(n, features): the per-base features flat, the minute, the type's count started, the bases held, the type's
    index and the style (categories, last two columns of the head; no style its own category, 254), then log1p of the
    seen counts."""
    n = len(glob)
    style = np.where(np.asarray(style) < 0, 254, style).reshape(n, 1).astype(np.float32)
    head = np.concatenate([bases.reshape(n, -1), glob[:, :3], glob[:, 3:4], style], 1)
    return np.concatenate([head, np.log1p(seen[:, types].astype(np.float32)),
                           np.log1p(seen_max[:, types].astype(np.float32))], 1).astype(np.float32)


def categorical(bases_features: int) -> list[int]:
    """The columns encode() gives as categories: the type's index and the style."""
    head = 3 * bases_features + 3
    return [head, head + 1]


class PlacementModel:
    """The trained model: P(base, side) for a building decided now."""

    def __init__(self, path):
        with open(path, "rb") as f:
            d = pickle.load(f)
        self.clf, self.types, self.styles, self.path = d["model"], d["types"], d["styles"], str(path)

    def odds(self, X: np.ndarray) -> np.ndarray:
        """(n, 6): the six classes' odds (a class the training never saw: 0)."""
        p = np.zeros((len(X), len(CLASSES)), np.float32)
        p[:, self.clf.classes_] = self.clf.predict_proba(X)
        return p

    @staticmethod
    def find(matchup: str, race: str, root: Path = Path(__file__).resolve().parents[2] / "runs" / "placement") \
            -> "PlacementModel | None":
        """The newest model of the matchup's race (train/placement.py), or None."""
        runs = sorted(Path(root).glob(f"{matchup}_{race}_*/model.pkl"))
        return PlacementModel(runs[-1]) if runs else None


class ProTiles:
    """The pros' building tiles on one map from one start (ingest/build_tiles.py): per pro game, its builds by
    (building, base tile, side) as [(tile x, tile y, the how-manieth of its type at that base)], and each game's style.
    Side 0 the front, 1 by the minerals, None either (for a race whose side no model decides)."""

    def __init__(self, games: list[dict]):
        self.games = []
        self.styles = []
        for gm in games:
            by = {}
            for uid, bx, by_, side, tx, ty, _, k in gm["builds"]:
                by.setdefault((uid, (bx, by_), side), []).append((tx, ty, k))
                by.setdefault((uid, (bx, by_), None), []).append((tx, ty, k))   # (either side: no side decided)
            self.games.append(by)
            self.styles.append(gm.get("style", -1))
        common: dict = {}
        for by in self.games:
            for key, spots in by.items():
                for tx, ty, _ in spots:
                    common.setdefault(key, {}).setdefault((tx, ty), 0)
                    common[key][tx, ty] += 1
        # (every game's tiles of a key, the commonest first: where the drawn pro's own are taken or don't fit)
        self.common = {key: sorted(c, key=lambda t: -c[t]) for key, c in common.items()}

    def at_base(self, base_tile: tuple[int, int]) -> list[int]:
        """The games with a building at this base."""
        return [i for i, by in enumerate(self.games) if any(key[1] == base_tile for key in by)]

    @staticmethod
    def find(matchup: str, race: str, map_hash: str | None, main_tile: tuple[int, int],
             root: Path = Path(__file__).resolve().parents[2] / "runs" / "tiles") -> "ProTiles | None":
        """The newest table of the matchup's race, its games on this map from this start, or None."""
        import json
        runs = sorted(Path(root).glob(f"{matchup}_{race}_*/tiles.json"))
        if not runs or map_hash is None:
            return None
        m = json.loads(runs[-1].read_text(encoding="utf-8")).get(map_hash)
        games = [gm for gm in (m or {}).get("games", []) if tuple(gm["main"]) == tuple(main_tile)]
        return ProTiles(games) if games else None

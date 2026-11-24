"""Scans sampled at the pros' timings and targets (option `scansample`, docs/REFOCUS.md Phase 1 step 5).

STOP-GAP (AGENTS.md "The scan sampler"): no model decides scans. The pros' scouting scans (at the enemy's main, natural
or other bases; eval/scouting.py, 300 modern games a matchup, 2026-11-23) come at a rate per minute of a Comsat with a
scan's energy that hardly depends on whether they have seen the enemy's plan (TvZ 1.52 before, 1.37 after) or on the
Comsat's age, the condition REFOCUS §6 row 8 writes for a sampler of their timings rather than a learned model. So:
while a Comsat has a scan's energy (and, once lurkers were seen, one more for the Detect rule), a scan at the pros' rate
for the game minute (RATE), aimed at the main, the natural or another base by the pros' shares at that minute
(TARGETS), a region looked at in the last RECENT_LOOK (gary/policy/sightings.py, half of it or more in sight) passed
over for the others. In place of answers.py's tech scan while on. Replace with a learned scan model (the pros' scans as
events, with what they have seen as inputs). Measure: the scouting measure (REFOCUS §4.3) against the pros'.
"""
from __future__ import annotations

import math
import random

from gary import terran as T
from gary.agent.intents import Intent

# the pros' scouting scans a minute of a ready Comsat, by game minute (the last for later minutes, the first for
# earlier), and their targets' shares (main, natural, other bases), by the Terran's matchup
RATE = {"TvZ": {5: 2.67, 6: 0.88, 7: 1.32, 8: 0.97, 9: 0.91, 10: 1.1},
        "TvT": {6: 0.27, 7: 0.23, 8: 0.39, 9: 0.44, 10: 0.52},
        "TvP": {5: 0.13, 6: 0.59, 7: 0.73, 8: 0.69, 9: 0.57}}
TARGETS = {"TvZ": {5: (0.54, 0.41, 0.05), 6: (0.29, 0.45, 0.26), 7: (0.16, 0.46, 0.38), 8: (0.23, 0.38, 0.38),
                   9: (0.19, 0.35, 0.47)},
           "TvT": {6: (0.63, 0.12, 0.25), 7: (0.32, 0.34, 0.34), 8: (0.15, 0.17, 0.69), 9: (0.18, 0.22, 0.60)},
           "TvP": {6: (0.73, 0.20, 0.07), 7: (0.62, 0.24, 0.15), 8: (0.57, 0.25, 0.18), 9: (0.44, 0.15, 0.41)}}
ENERGY = 50
RECENT_LOOK = 60 * 24         # frames: a region looked at this recently (half of it or more) isn't scanned
LOOK_EVERY = 12               # frames between the sighting states' looks
SCAN_LASTS = 7 * 24
LURKERS = (103, 97)
OTHERS = 3                    # "other bases": the stalest of the enemy's main's nearest this many


def _by_minute(table: dict, minute: int):
    keys = sorted(table)
    return table[min(max(minute, keys[0]), keys[-1])] if minute not in table else table[minute]


class ScanSampler:
    def __init__(self, g) -> None:
        from gary.policy.army import is_building
        from gary.policy.sightings import SightingState
        self.g = g
        mu = "Tv" + g.enemy.race if getattr(g, "enemy", None) is not None else g.matchup
        self.rate, self.targets = RATE.get(mu, RATE["TvZ"]), TARGETS.get(mu, TARGETS["TvZ"])
        try:                                      # (the ground's heights: a unit sees nothing above it)
            heights = g.hi.game.terrain()[1]
        except Exception:                         # (no terrain where the game has none: every height seen)
            heights = None
        self.state = SightingState(g.map, g.slot, g.main.center, mu[-1], is_building, heights)
        self.rng = random.Random(f"scansample/{g.game_seed}/{g.hi.slot}")
        self.last = None
        self.next_look = 0
        self.scans: list[tuple[int, tuple[int, int]]] = []
        self.lurkers = False

    def look(self, obs: dict) -> None:
        g, f = self.g, self.g.hi.frame
        if f < self.next_look:
            return
        self.next_look = f + LOOK_EVERY
        units = [u for u in obs["units"] if u["owner"] in (g.slot, 11)
                 or "visible_to" not in u or (u["visible_to"] >> g.slot) & 1]
        if not self.lurkers and any(u["type"] in LURKERS and u["owner"] not in (g.slot, 11) for u in units):
            self.lurkers = True
        self.state.look(units, f, tuple(p for t, p in self.scans if f - t <= SCAN_LASTS))

    def _recent(self, base) -> bool:
        r = self.state._region(base)
        return r is not None and r.cover >= 0.5 and self.g.hi.frame - r.frame <= RECENT_LOOK

    def step(self, mine: list[dict]) -> bool:
        """A scan at the pros' rate, if a Comsat is ready. True if Gary acted."""
        g, f = self.g, self.g.hi.frame
        dt, self.last = (f - self.last) if self.last is not None else 0, f
        need = ENERGY * (2 if self.lurkers else 1)
        comsat = max((u for u in mine if u["type"] == T.COMSAT and u["completed"] and (u.get("energy") or 0) >= need),
                     key=lambda u: u.get("energy") or 0, default=None)
        if comsat is None or g.enemy_main is None or dt <= 0:
            return False
        minute = int(f // 1440)
        if self.rng.random() >= 1 - math.exp(-_by_minute(self.rate, minute) * dt / 1440):
            return False
        main = g.map.base_near(g.enemy_main)
        nat = g.map.natural_of(main)
        skip = [self.state.own, self.state.own_nat, main, nat]      # (Bases aren't hashable: by identity)
        others = sorted((b for b in g.map.bases if not any(b is x for x in skip)),
                        key=lambda b: math.dist(b.center, main.center))[:OTHERS]
        other = min(others, key=lambda b: self.state._region(b).frame if self.state._region(b) else -1, default=None)
        places = [main, nat, other]
        weights = list(_by_minute(self.targets, minute))
        weights = [0.0 if b is None or self._recent(b) else w for b, w in zip(places, weights)]
        if sum(weights) <= 0:
            return False
        target = self.rng.choices(places, weights=weights)[0]
        x, y = target.center
        self.scans.append((f, (x, y)))
        g.motor.start(Intent("SCAN", [], (x, y), {"comsat": comsat["tag"], "x": int(x), "y": int(y)}, "macro:scansample"))
        what = "main" if target is main else "natural" if target is nat else "another base"
        g.say(f"scans the enemy's {what} ({x}, {y}), sampled at the pros' rate")
        return True

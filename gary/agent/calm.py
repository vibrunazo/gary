"""The calm layer (option `calm`): a standing fighter out of contact placed as the pros place theirs (gary/policy/calm.py).

Each half second, every calm fighter's next half second is drawn at the calm model's rates (its class weights out, over
the half seconds since its last draw); the short orders ("again") drawn for standing units are carried out as moves to
where the offset head points, units whose points are near each other in one click. The other decisions are left to
their layers: far orders to the commit model, the rest to nobody (keep, a click again, a non-point command). Moving
units are drawn too (the model's odds are learned over all calm units) but not ordered: a short order given to a unit on
a commit move would stop it short (the pros' hops while moving, docs/PROGRESS.md 2026-11-18, are a later step).
A turn rule of the army layer (army.py turn_rules), before the commit model's questions."""
from __future__ import annotations

import math
import random

import numpy as np

from gary.agent.intents import Intent
from gary.decision_log import LOG
from gary.policy.army import is_building, is_worker, supply_x2
from gary.policy.calm import NAMES, snapshots
from gary.policy.roles import AGAIN, MAX_UNITS

STEP = 12                     # frames: a decision a half second, as the data's labels
STANDING = {2, 3, 107}        # (ingest/calm_dataset.py STANDING)
NEAR = 3 * 32                 # units whose points are this near share a click (gary/agent/roles.py AGAIN_NEAR)
MAX_GROUP = 12                # (gary/agent/roles.py MAX_GROUP)


class Calm:
    def __init__(self, g, memory=None):
        from gary.agent.manifests import model_for
        from gary.policy.roles import RoleModel
        self.g = g
        self.model = RoleModel.load(model_for("calm", g.matchup, g.race.letter))
        self.k = list(self.model.config["roles"]).index(AGAIN)
        self.rng = random.Random(0)
        self.next = 0
        self.prev: dict[int, tuple[float, float]] = {}
        self.prev_frame: int | None = None
        self.drawn_at: dict[int, int] = {}       # unit -> frame of its last draw
        self.first_seen: dict[int, int] = {}
        self.ground = None
        self.queue: list[Intent] = []

    def _ground(self):
        from gary.policy.roles import Ground
        g = self.g
        if self.ground is None:
            self.ground = False
            if getattr(g.hi.game, "terrain", None) is not None and g.map is not None and g.main is not None:
                try:
                    start = min(g.map.starts, key=lambda s: math.dist(s, g.main.center))
                    self.ground = Ground.of(g.hi.game, start)
                except Exception:                 # (a map the analysis can't read: no terrain inputs)
                    self.ground = False
        return self.ground or None

    def step(self, obs: dict, mine: list[dict], done: list[dict]) -> str | None:
        g, now = self.g, self.g.hi.frame
        while self.queue:                        # (one click a turn: the hands)
            it = self.queue.pop(0)
            here = {u["tag"]: u for u in done}
            tags = [t for t in g.leases.free(it.units, "army") if t in here and here[t]["order"] in STANDING]
            if tags:
                return self._send(tags, it.target, it.params["p"])
        if now < self.next:
            return None
        self.next = now + STEP
        self._decide(obs, now)
        return None

    def _decide(self, obs: dict, now: int) -> None:
        from gary.policy.roles import RACE_SHELTERS, extra_features, own_extras, terrain_features
        g = self.g
        positions = {u["tag"]: (u["x"], u["y"]) for u in obs["units"]}
        prev, elapsed = self.prev, (now - self.prev_frame) if self.prev_frame is not None else 0
        self.prev, self.prev_frame = positions, now
        if 0 < elapsed != STEP:                  # motion per half second, as the model learned it
            prev = {t: (positions[t][0] - (positions[t][0] - p[0]) * STEP / elapsed,
                        positions[t][1] - (positions[t][1] - p[1]) * STEP / elapsed)
                    for t, p in prev.items() if t in positions}
        by_tag = {u["tag"]: u for u in obs["units"]}
        own = [u for u in obs["units"] if u["owner"] == g.slot]
        for u in own:
            if u["completed"] and supply_x2(u["type"]) > 0 and not is_worker(u["type"]) and not is_building(u["type"]):
                self.first_seen.setdefault(u["tag"], now)
        fx, fy = (-1 if g.flip[0] else 1), (-1 if g.flip[1] else 1)
        moves: list[tuple[dict, tuple[float, float], float]] = []
        for rows, tags, _, calm in snapshots(obs, g.slot, g.flip, supply_x2, is_worker, is_building, MAX_UNITS):
            extra = extra_features(rows, tags, positions, prev if elapsed else {}, g.flip)
            extra[:, 6:] = terrain_features(tags, positions, self._ground(),
                                            [(u["x"], u["y"]) for u in own if u["type"] in g.race.town_halls],
                                            [(u["x"], u["y"]) for u in own if u["type"] in RACE_SHELTERS[g.race.letter]
                                             and u["completed"]], g.flip)
            own_extras(extra, tags, by_tag, g.slot, self.first_seen, now)
            time_s = obs["frame"] * 42 / 1000
            odds = self.model.rates(self.model.predict(rows, extra, time_s))
            offsets = self.model.predict_offset(rows, extra, time_s)
            for i, t in enumerate(tags[:MAX_UNITS]):
                if t not in calm:
                    continue
                q = odds[i] / odds[i].sum()
                n = max(1.0, (now - self.drawn_at.get(t, now - STEP)) / STEP)
                self.drawn_at[t] = now
                p = 1 - (1 - float(q[self.k])) ** n      # (its odds over the half seconds since its last draw)
                if self.rng.random() >= p:
                    continue
                u = by_tag[t]
                standing = u["order"] in STANDING
                if LOG.on:
                    LOG.add(f"calm_{g.race.letter.lower()}", frame=now, tag=t, p=p, standing=standing)
                if not standing:
                    continue
                dx, dy = offsets[i] * 32
                moves.append((u, (max(0.0, u["x"] + fx * dx), max(0.0, u["y"] + fy * dy)), p))
        while moves:                             # (units whose points are near share a click, at their mean point)
            seed = moves[0][1]
            group = [m for m in moves if math.dist(m[1], seed) < NEAR][:MAX_GROUP]
            moves = [m for m in moves if m not in group]
            x = sum(m[1][0] for m in group) / len(group)
            y = sum(m[1][1] for m in group) / len(group)
            tags = [m[0]["tag"] for m in group]
            self.queue.append(Intent("ARMY_MOVE", tags, (int(x), int(y)), {"p": max(m[2] for m in group)}, "army"))
            LOG.decision(g.hi.side, "calm", now, f"move to ({int(x) // 32},{int(y) // 32})", max(m[2] for m in group),
                         inputs={"units": len(tags)}, by="model: the calm model's again (short order), drawn",
                         then="queued")

    def _send(self, tags: list[int], point, p: float) -> str:
        x, y = int(point[0]), int(point[1])
        self.g.motor.start(Intent("ARMY_MOVE", tags, (x, y), {"tags": tags, "x": x, "y": y, "attack": False, "p": p,
                                                             "fight": 0.0, "done": [], "boxes": 0}, "army"))
        return "army:calm"

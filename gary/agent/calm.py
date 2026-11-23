"""The calm layer (option `calm`): a standing fighter out of contact placed as the pros place theirs (gary/policy/calm.py).

Each half second, each bunch of calm fighters decides once whether it gets a short order ("again"), at its units' mean
odds (the calm model's rates, its class weights out, over the half seconds since their last draw), as the pros give one
command to a bunch; its standing units are then moved, in one click, to a point drawn from their offset odds from their
middle (ingest/calm_dataset.py's where snapshots). The other decisions are left to
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
from gary.policy.calm import map_extras, snapshots
from gary.policy.roles import AGAIN, EXTRA, MAX_UNITS, offset_of

STEP = 12                     # frames: a decision a half second, as the data's labels
STANDING = {2, 3, 107}        # (ingest/calm_dataset.py STANDING)
MAX_GROUP = 12                # (gary/agent/roles.py MAX_GROUP)


class Calm:
    def __init__(self, g, memory=None):
        from gary.agent.manifests import model_for
        from gary.policy.roles import RoleModel
        self.g = g
        self.model = RoleModel.load(model_for("calm", g.matchup, g.race.letter))
        self.k = list(self.model.config["roles"]).index(AGAIN)
        self.k_far = list(self.model.config["roles"]).index("far")
        try:                                     # the far points (ingest/calm_dataset.py --far): optional
            self.far = RoleModel.load(model_for("calm_far", g.matchup, g.race.letter))
        except SystemExit:
            self.far = None
        self.rng = random.Random(f"calm/{g.game_seed}/{g.hi.slot}")   # (the game's and the side's: it was 0, #64)
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
        army = [u for u in own if u["completed"] and u["type"] in g.army_types]
        asked = {u["tag"] for c in g.army._clusters(army) for u in c}     # (the units the commit model is asked about)
        with_map = self.model.config["net"]["n_extra"] > EXTRA     # (a model with the map extras: gary/policy/calm.py)
        time_s = obs["frame"] * 42 / 1000
        for rows, tags, _, calm in snapshots(obs, g.slot, g.flip, supply_x2, is_worker, is_building, MAX_UNITS):
            extra = extra_features(rows, tags, positions, prev if elapsed else {}, g.flip)
            extra[:, 6:] = terrain_features(tags, positions, self._ground(),
                                            [(u["x"], u["y"]) for u in own if u["type"] in g.race.town_halls],
                                            [(u["x"], u["y"]) for u in own if u["type"] in RACE_SHELTERS[g.race.letter]
                                             and u["completed"]], g.flip)
            own_extras(extra, tags, by_tag, g.slot, self.first_seen, now)
            if with_map:
                t = g.army.tracker                 # (the map's size in pixels, as the army tracker keeps it)
                extra = np.concatenate([extra, map_extras(tags, positions, self._ground(), t.mw, t.mh, g.flip)], 1)
            odds = self.model.rates(self.model.predict(rows, extra, time_s))
            ps, pf, standing, small = [], [], [], []
            for i, t in enumerate(tags[:MAX_UNITS]):
                if t not in calm:
                    continue
                q = odds[i] / odds[i].sum()
                n = max(1.0, (now - self.drawn_at.get(t, now - STEP)) / STEP)
                self.drawn_at[t] = now
                ps.append(1 - (1 - float(q[self.k])) ** n)     # (its odds over the half seconds since its last draw)
                if by_tag[t]["order"] in STANDING:
                    standing.append(i)
                    if t not in asked:
                        small.append(i)
                        pf.append(1 - (1 - float(q[self.k_far])) ** n)
            # far: the standing units no cluster the commit model is asked about holds (under SMALL supply), at their mean
            # far odds, to the calm_far model's point (the pros send such bunches far: docs/PROGRESS.md 2026-11-19)
            if small and self.far is not None and self.rng.random() < float(np.mean(pf)):
                self._order(rows, extra, time_s, small, by_tag, tags, float(np.mean(pf)), self.far, "far", now)
                standing = [i for i in standing if i not in small]
            # one decision a bunch, as the pros give one command to a bunch (a median 10 units): at its units' mean odds
            p = float(np.mean(ps)) if ps else 0.0
            go = bool(standing) and self.rng.random() < p
            if LOG.on and ps:
                LOG.add(f"calm_{g.race.letter.lower()}", frame=now, units=len(ps), standing=len(standing), p=p, go=go,
                        small=len(small))
            if go:
                self._order(rows, extra, time_s, standing, by_tag, tags, p, self.model, "again", now)

    def _order(self, rows, extra, time_s, idx: list[int], by_tag: dict, tags: list[int], p: float, model, what: str,
               now: int) -> None:
        """The units idx to a point drawn from the model's offset odds averaged over them, from their middle; one click
        (or one per MAX_GROUP)."""
        g = self.g
        fx, fy = (-1 if g.flip[0] else 1), (-1 if g.flip[1] else 1)
        us = [by_tag[tags[i]] for i in idx]
        cx, cy = sum(u["x"] for u in us) / len(us), sum(u["y"] for u in us) / len(us)
        bins = model.offset_odds(rows, extra, time_s)
        if bins is not None:                     # (drawn at their averaged odds, as the data's points: from the middle)
            w = bins[idx].mean(0)
            b = min(int(np.searchsorted(np.cumsum(w), self.rng.random() * w.sum(), side="right")), len(w) - 1)
            dx, dy = (v * 32 for v in offset_of(b, model.edges))
        else:
            dx, dy = model.predict_offset(rows, extra, time_s)[idx].mean(0) * 32
        t = g.army.tracker
        x, y = min(max(0.0, cx + fx * dx), t.mw - 1), min(max(0.0, cy + fy * dy), t.mh - 1)
        for k in range(0, len(us), MAX_GROUP):
            part = [u["tag"] for u in us[k:k + MAX_GROUP]]
            self.queue.append(Intent("ARMY_MOVE", part, (int(x), int(y)), {"p": p}, "army"))
        LOG.decision(g.hi.side, "calm", now, f"{what}: move to ({int(x) // 32},{int(y) // 32})", p,
                     inputs={"units": len(us)}, by=f"model: the calm model's {what}, drawn a bunch", then="queued")

    def _send(self, tags: list[int], point, p: float) -> str:
        x, y = int(point[0]), int(point[1])
        self.g.motor.start(Intent("ARMY_MOVE", tags, (x, y), {"tags": tags, "x": x, "y": y, "attack": False, "p": p,
                                                             "fight": 0.0, "done": [], "boxes": 0}, "army"))
        return "army:calm"

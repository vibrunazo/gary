"""The army's tactical intents in play (option `intent`; docs/TACTICAL_INTENT.md): one intent over the army and its
defence detachments, decided by the intent model (gary/policy/tactical.py: a switch hazard and the next intent, learned
from the pros' commitment ticks), each with its units, its target and its record.

Every TICK seconds, on the army's main ground cluster's grid (the army tracker's, as the commit model reads it):
  - the main intent goes on, or switches at the model's hazard, drawn (the game's seed and the side's), to the next
    intent drawn from the next head's odds; a new one's target is the commit model's destination odds' likeliest cell on
    the intent's side (enemy presence for ATTACK, the threatened home cells for DEFEND_BASE, nearer the main for
    RETREAT, anywhere else for GATHER, none for HOLD);
  - enemy fighters at home while the main intent is elsewhere: a detachment, the nearest ground fighters up to the
    pros' median supply defending in that state (the model's sizer), attack-moved to the threat; it ends after END_S
    with no enemy there (the pros' DEFEND_BASE hold, median 20 s), its units back to the main intent.
Each unit belongs to one intent (`of`). The leaves read it (docs/TACTICAL_INTENT.md §4): the commit model takes its
cluster's intent as an input and the intent's target as its destination (gary/agent/army.py); the role model the fight's
intent (gary/agent/roles.py); the calm layer leaves alone units to this layer, which sends them to their group; the
reinforce rule hands new units to it; the control groups follow its groups, a type of an intent's group on a key
(gary/agent/motor.py; tanks sieged and flyers keep keys of their own type). An army turn rule (gary/agent/army.py
turn_rules), before the calm layer.
"""
from __future__ import annotations

import math
import random

import numpy as np

from gary.agent.intents import Intent
from gary.decision_log import LOG
from gary.policy.army import supply_x2
from gary.policy.tactical import INTENTS, Scene, dist, features, near, sizer_features
from gary.races import AIR_FIGHTERS

TICK = 5 * 24                      # the intent model's tick (the army dataset's TICK)
END_S = 20                         # a detachment's threat gone this long: it ends (the pros' DEFEND_BASE hold, median)
ALONE = 6 * 32                     # no other fighter this near: alone (gary/agent/sightings.py)
CONTACT = 8 * 32                   # an enemy fighter this near: in contact (the roles' then)
JOIN_EVERY = 2 * 24
GRID = 16


class Tactical:
    name = "intent"

    def __init__(self, g, model):
        self.g = g
        self.model = model
        self.rng = random.Random(f"intent/{g.game_seed}/{g.hi.slot}")
        self.main: dict | None = None      # {"id", "kind", "since", "target", "rid", "ticks"}
        self.details: list[dict] = []      # DEFEND_BASE detachments: {"id", "cell", "point", "units", "size", "since", "quiet", "rid"}
        self.of: dict[int, str] = {}       # unit tag -> its intent's id
        self.queue: list[Intent] = []
        self.next = 0
        self.next_join = 0
        self.n = 0
        self.last_x: dict | None = None    # (the pipe check's: the numbers of the last decision)
        self.forced: str | None = None     # (the pipe check's: an intent forced for the main)
        self.joining: set[int] = set()     # units alone this layer sends to their group
        self.types: dict[int, int] = {}    # unit tag -> type (a detachment's supply)

    # --- what the leaves read -----------------------------------------------------------------------------------------
    def intent_of(self, tag: int) -> dict | None:
        iid = self.of.get(tag)
        if iid is None:
            return None
        if self.main is not None and self.main["id"] == iid:
            return self.main
        return next((d for d in self.details if d["id"] == iid), None)

    def intent_index(self, tags) -> int:
        """The intent most of these units belong to (INTENTS index), -1 none."""
        kinds = [it["kind"] for it in (self.intent_of(t) for t in tags) if it is not None]
        if not kinds:
            return INTENTS.index(self.main["kind"]) if self.main is not None else -1
        return INTENTS.index(max(set(kinds), key=kinds.count))

    def cluster_intent(self, group: list[dict]) -> tuple[int, int | None, list[dict]]:
        """A cluster's intent for the commit model (INTENTS index, -1 none), its target cell (None) and the units it
        orders: the main intent's units of the cluster (a detachment's units take this layer's orders), or, a cluster
        all of one detachment's, that detachment's."""
        if self.main is None:
            return -1, None, group
        mains = [u for u in group if self.of.get(u["tag"], self.main["id"]) == self.main["id"]]
        if mains:
            return INTENTS.index(self.main["kind"]), self.main.get("target"), mains
        it = self.intent_of(group[0]["tag"])
        return (INTENTS.index(it["kind"]), it.get("target"), group) if it is not None else (-1, None, group)

    def groups(self, army: list[dict]) -> list[list[dict]]:
        """The control groups' partition: the main intent's ground units, each detachment's, the flyers apart."""
        out: dict[str, list[dict]] = {}
        air = []
        for u in army:
            if u["type"] in AIR_FIGHTERS:
                air.append(u)
                continue
            out.setdefault(self.of.get(u["tag"], "main"), []).append(u)
        return [v for v in out.values() if v] + ([air] if air else [])

    def lone_free(self, tag: int) -> bool:
        """A unit this layer sends to its group (the calm layer leaves it alone)."""
        return tag in self.joining

    # --- the turn -----------------------------------------------------------------------------------------------------
    def step(self, obs: dict, mine: list[dict], done: list[dict]) -> str | None:
        g, now = self.g, self.g.hi.frame
        while self.queue:                                   # (one order a turn: the hands)
            it = self.queue.pop(0)
            here = {u["tag"] for u in done}
            tags = [t for t in g.leases.free(it.units, "intent") if t in here] if getattr(g, "leases", None) else \
                [t for t in it.units if t in here]
            if tags:
                x, y = it.target
                g.motor.start(Intent(it.kind, tags, (x, y), {"tags": tags, "x": x, "y": y,
                                                             "attack": it.kind == "ARMY_ATTACK", "p": it.params.get("p", 1.0),
                                                             "fight": 0.0, "done": [], "boxes": 0,
                                                             "origin": it.params.get("origin", "intent")}, "intent"))
                return "army:intent"
        if now >= self.next_join:
            self.next_join = now + JOIN_EVERY
            self._join(obs, done)
        return None

    def look(self, obs: dict) -> None:
        """Every turn (gary/agent/arbiter.py), whoever has the hands: the intent decided on its clock."""
        if self.g.army is None or self.g.hi.frame < self.next:
            return
        self.next = self.g.hi.frame + TICK
        mine = [u for u in obs["units"] if u["owner"] == self.g.slot]
        self._decide(obs, mine, [u for u in mine if u["completed"]])

    def _army(self, done: list[dict]) -> list[dict]:
        types = self.g.army.types if getattr(self.g.army, "types", None) is not None else self.g.army_types
        return [u for u in done if u["type"] in types and u["completed"]]

    def _decide(self, obs: dict, mine: list[dict], done: list[dict]) -> None:
        g, now = self.g, self.g.hi.frame
        army = self._army(done)
        alive = {u["tag"] for u in army}
        self.of = {t: i for t, i in self.of.items() if t in alive}
        self.types = {u["tag"]: u["type"] for u in army}
        clusters = g.army._clusters(army)
        ground = [c for c in clusters if not all(u["type"] in AIR_FIGHTERS for u in c)]
        if not ground:
            for u in army:
                self.of.setdefault(u["tag"], self.main["id"] if self.main else "main")
            return
        group = max(ground, key=lambda c: sum(supply_x2(u["type"]) for u in c))
        cx, cy = sum(u["x"] for u in group) / len(group), sum(u["y"] for u in group) / len(group)
        here = g.army.tracker.cell(cx, cy)
        held, age = g.army._commitment(here, False)
        spec = g.army.model.spec
        prev = self.main["kind"] if self.main else None
        t = g.army.tracker.copy() if hasattr(g.army.tracker, "copy") else g.army.tracker
        grid, glob = t.inputs(obs, group, (held, age), -1, intent=INTENTS.index(prev) if prev else None)
        g9 = grid[0][:9]
        loss = grid[0][spec.channel("losses")] if spec.losses else None
        scene = Scene(g9, loss)
        me = obs["me"]
        eco = (me["minerals"], me["gas"], me["supply_used"] * 2, me["supply_max"] * 2)
        dest = divmod(self.main["target"], GRID) if self.main and self.main.get("target") is not None else None
        x = features(scene, eco, now, held, age, dest, len(ground), prev, self.main["ticks"] if self.main else 0)
        self.last_x = x
        if self.forced is not None:
            kind, p, by = self.forced, 1.0, "forced (the pipe check)"
            switch = self.main is None or self.main["kind"] != kind
        elif self.main is None:
            q = self.model.p_next(x)
            kind = INTENTS[int(np.argmax(q))]
            p, by, switch = float(q.max()), "model: the intent model's next intent (the first)", True
        else:
            ps = self.model.p_switch(x)
            switch = self.rng.random() < ps
            if switch:
                q = self.model.p_next(x)
                kind = INTENTS[int(self.rng.choices(range(len(INTENTS)), weights=q.tolist())[0])]
                p, by = float(q[INTENTS.index(kind)]), f"model: switch at {ps:.0%}, the next intent drawn"
            else:
                kind, p, by = self.main["kind"], 1 - ps, f"model: held (switch {ps:.0%})"
        if switch:
            target = self._target(kind, scene, grid, glob, here)
            self.n += 1
            iid = f"I{self.n}"
            top = None if self.forced else [[k, round(float(v), 3)] for k, v in zip(INTENTS, self.model.p_next(x))]
            r = LOG.decision(g.hi.side, "intent", now, kind, p, top,
                             {"units": len(group), "army": round(x["cluster_share"], 2), "at": self._name(here),
                              "target": self._name(target) if target is not None else None,
                              "threat": round(scene.threat_sup, 1), "cohesion": round(x["army_near_cluster"], 2)},
                             by, then=f"{prev or 'none'} -> {kind}")
            self.main = {"id": iid, "kind": kind, "since": now, "target": target, "rid": LOG.link(r)["id"] if r else None,
                         "ticks": 1, "trigger": by}
            g.army.next_ask, g.army.ask_turn = now, 0      # (a switch is an event: the main cluster asked now, biggest first)
        else:
            self.main["ticks"] += 1
            if self.main["kind"] in ("ATTACK", "DEFEND_BASE", "RETREAT") and self.main.get("target") is None:
                self.main["target"] = self._target(self.main["kind"], scene, grid, glob, here)
        for u in army:
            if self.of.get(u["tag"]) not in {d["id"] for d in self.details}:
                self.of[u["tag"]] = self.main["id"]
        self._detachments(obs, army, scene, len(ground), now)

    def _target(self, kind: str, scene: Scene, grid, glob, here: int) -> int | None:
        """The intent's target: the commit model's destination odds' likeliest cell on the intent's side."""
        if kind == "HOLD":
            return None
        g = self.g
        where, _ = g.army.model.predict(grid, glob)
        w = np.asarray(where[0], np.float64)
        m = np.asarray(grid[0][:9]).reshape(-1, GRID, GRID)
        enemy = (m[3] > 0) | (m[6] > 0) | (m[7] > 0)
        nearby = enemy.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nearby |= np.roll(np.roll(enemy, dy, 0), dx, 1)
        cells = [(c // GRID, c % GRID) for c in range(GRID * GRID)]
        center = divmod(here, GRID)
        if kind == "ATTACK":
            ok = [nearby.reshape(-1)[c] and not near(cells[c], scene.home, 0) for c in range(GRID * GRID)]
        elif kind == "DEFEND_BASE":
            ok = [near(cells[c], scene.threat, 1) for c in range(GRID * GRID)] if scene.threat else [False] * (GRID * GRID)
        elif kind == "RETREAT":
            ok = [dist(cells[c], scene.main) <= dist(center, scene.main) - 2 for c in range(GRID * GRID)]
        else:
            ok = [not nearby.reshape(-1)[c] for c in range(GRID * GRID)]
        p = w * np.array(ok, np.float64)
        return int(p.argmax()) if p.max() > 0 else None

    def _detachments(self, obs: dict, army: list[dict], scene: Scene, n_ground: int, now: int) -> None:
        g = self.g
        for d in list(self.details):                        # (ends: the threat gone END_S)
            if near(d["cell"], scene.threat, 1):
                d["quiet"] = None
            elif d["quiet"] is None:
                d["quiet"] = now
            alive = {u["tag"] for u in army}
            d["units"] &= alive
            if d["quiet"] is not None and now - d["quiet"] >= END_S * 24 or not d["units"]:
                self.details.remove(d)
                for t in d["units"]:
                    self.of[t] = self.main["id"]
                LOG.decision(g.hi.side, "intent", now, "DEFEND_BASE ended", None, None, {"units": len(d["units"])},
                             "the threat gone" if d["units"] else "its units gone", then=f"{d['id']} -> {self.main['kind']}")
        if not scene.threat or self.main["kind"] == "DEFEND_BASE":
            return
        cell = max(scene.threat, key=lambda c: float((scene.g[3] + scene.g[7]).reshape(GRID, GRID)[c]))
        if any(dist(cell, d["cell"]) <= 1 for d in self.details):
            return
        size = self.model.defend_size(sizer_features(scene, now, n_ground))
        if size < 1.0:
            return
        point = g.army.tracker.center(cell[0] * GRID + cell[1])
        free = [u for u in army if u["type"] not in AIR_FIGHTERS and self.of.get(u["tag"]) == self.main["id"]]
        free.sort(key=lambda u: math.dist((u["x"], u["y"]), point))
        take, sup = [], 0.0
        for u in free:
            if sup >= size:
                break
            take.append(u)
            sup += supply_x2(u["type"]) / 2
        if not take:
            return
        self.n += 1
        d = {"id": f"I{self.n}", "kind": "DEFEND_BASE", "cell": cell, "point": point, "units": {u["tag"] for u in take},
             "size": size, "since": now, "quiet": None, "target": cell[0] * GRID + cell[1]}
        self.details.append(d)
        for u in take:
            self.of[u["tag"]] = d["id"]
        r = LOG.decision(g.hi.side, "intent", now, "DEFEND_BASE (detachment)", None, None,
                         {"units": len(take), "supply": round(sup, 1), "size": round(size, 1),
                          "threat": round(scene.threat_sup, 1), "at": self._name(d["target"]), "army": len(army)},
                         "model: the pros' median defence in this state",
                         then=f"{len(take)} of the {self.main['kind']} army's units, the rest carry on")
        d["rid"] = LOG.link(r)["id"] if r else None
        go = [u["tag"] for u in take if math.dist((u["x"], u["y"]), point) > ALONE]
        if go:
            self.queue.append(Intent("ARMY_ATTACK", go, (int(point[0]), int(point[1])), {"origin": "intent defend"}, "army"))

    def _join(self, obs: dict, done: list[dict]) -> None:
        """Ground fighters alone, out of contact and standing, in no asked cluster: sent to their intent's group."""
        g = self.g
        army = self._army(done)
        if not army or self.main is None:
            self.joining = set()
            return
        asked = {u["tag"] for c in g.army._clusters(army) for u in c}
        enemy = [(u["x"], u["y"]) for u in obs["units"] if u["owner"] not in (g.slot, 11) and supply_x2(u["type"]) > 0]
        lone = []
        for u in army:
            if u["type"] in AIR_FIGHTERS or u["tag"] in asked or u["type"] == 30:      # (a sieged tank stays: its mode's)
                continue
            if any(v is not u and math.dist((u["x"], u["y"]), (v["x"], v["y"])) < ALONE for v in army):
                continue
            if any(math.dist((u["x"], u["y"]), e) < CONTACT for e in enemy):
                continue
            lone.append(u)
        self.joining = {u["tag"] for u in lone}
        by_group: dict[str, list[dict]] = {}
        for u in lone:
            by_group.setdefault(self.of.get(u["tag"], self.main["id"]), []).append(u)
        for iid, us in by_group.items():
            mates = [v for v in army if self.of.get(v["tag"]) == iid and v["tag"] in asked]
            if not mates:
                continue
            mx, my = sum(v["x"] for v in mates) / len(mates), sum(v["y"] for v in mates) / len(mates)
            go = [u["tag"] for u in us if u["order"] in (2, 3, 107)]     # (standing: STANDING of the calm layer)
            if go:
                self.queue.append(Intent("ARMY_MOVE", go, (int(mx), int(my)), {"origin": "intent join"}, "army"))

    def reinforce(self, new: list[dict], at_home: list[dict]) -> bool:
        """The reinforce rule's new units (gary/agent/fight.py ReinforceRule): into a detachment short of its size, else to
        their intent's group; never alone into the fight. True if handled."""
        if self.main is None:
            return False
        for d in self.details:
            have = sum(supply_x2(self.types.get(t, 0)) / 2 for t in d["units"])
            if have < d["size"]:
                for u in new:
                    self.of[u["tag"]] = d["id"]
                    d["units"].add(u["tag"])
                x, y = d["point"]
                self.queue.append(Intent("ARMY_ATTACK", [u["tag"] for u in new], (int(x), int(y)),
                                         {"origin": "intent reinforce"}, "army"))
                return True
        for u in new:
            self.of[u["tag"]] = self.main["id"]
        return False                                          # (the join step walks them to the group when alone)

    def _name(self, cell) -> str | None:
        if cell is None:
            return None
        y, x = divmod(int(cell), GRID)
        cx, cy = self.g.army.tracker.center(int(cell))
        return f"({int(cx) // 32},{int(cy) // 32})"

"""The Protoss executor (docs/REFACTOR.md Phase 4): what only Protoss hands do, over the race-neutral
Executor. A probe places a building and leaves (it warps in alone: nothing to resume, no add-ons); units
are trained from their buildings, as the Terran's are; a building other than a Nexus, Pylon or
Assimilator stands only in a Pylon's power field, which the game's placement check holds (can_place:
no Gateway spot beside a Nexus without a Pylon), so the hands' part is the Pylons: one ahead of
production for supply, and one when a powered building found no powered spot. An Archon or Dark Archon the
macro decides is two of its Templar merged: the two nearest each other (the least energy between them breaking
ties), selected exactly and T (R) pressed, held while they walk together, and its decision taken back if
they don't (an order cancelled the merge, or one died): the dataset counts the Archons begun."""

from __future__ import annotations

import math

from gary import commands as C
from gary import protoss as P
from gary.agent.executor import HALL_CLEAR, Executor
from gary.agent.macro import BUILD, EXPAND, RESEARCH, TRAIN, UPGRADE, WAIT
from gary.agent.gary import Gary, Task
from gary.agent.intents import Intent

UNPOWERED = {P.NEXUS, P.PYLON, P.ASSIMILATOR}    # what stands without a Pylon's power
POWER_SHORT_FOR = 20 * 24                        # a powered build that found no powered spot calls a Pylon this long
POWER_NEAR = 16 * 32                             # option place: a Pylon this near a base's centre is at it (the spot search's
                                                 # radius: at 12 tiles the natural's wall Pylon toward its choke wasn't, and its
                                                 # Forge called a Pylon every 12 s, 7-41 in 14 of round PL217a's 48 games)
MERGING = {105, 106, 183}                        # ArchonWarp, CompletingArchonSummon, DarkArchonMeld: merging already
MERGE_FOR = 6 * 24                               # a merge not given by then is given up (its decision taken back)
MERGE_SEEN = 2 * 24                              # a merge's key this long ago shows its Templar merging, or it didn't
ROOM_MIN = 64                                    # a Pylon's spot powers this many free tiles no other Pylon does (half
                                                 # its field: at 24, two tiles from the last one passed)
# the game's power field (OpenBW psi_field_mask: a building's center this far from a Pylon's, in pixels, by quarter)
FIELD_MASK = ((1, 1, 1, 1, 1, 1, 1, 1), (1, 1, 1, 1, 1, 1, 1, 1), (1, 1, 1, 1, 1, 1, 1, 0), (1, 1, 1, 1, 1, 1, 0, 0),
              (1, 1, 1, 0, 0, 0, 0, 0))


def _in_field(rx: int, ry: int) -> bool:
    x, y = abs(rx) - (rx < 0), abs(ry) - (ry < 0)
    return x < 256 and y < 160 and bool(FIELD_MASK[y // 32][x // 32])


# the tiles (offsets from a Pylon's top-left tile) whose centers its field powers
FIELD = [(ox, oy) for oy in range(-6, 8) for ox in range(-9, 11) if _in_field(ox * 32 - 16, oy * 32 - 16)]


class ProtossExecutor(Executor):
    build_order = C.ORDER_PLACE_PROTOSS_BUILDING

    def __init__(self, g: Gary):
        super().__init__(g)
        self.power_short = -10 ** 9                  # when a powered building last found no powered spot
        self.power_for: tuple | None = None          # option place: (base, side) a drawn building found no power at
        self.room_only = False                       # (spot: a Pylon's candidates with room only, at every base first)
        g.task_runners["merge"] = self._task_merge
        self.merges: list[dict] = []                 # merges given and not begun yet: their Templar, Archon, key's frame

    # --- what a decision means for Protoss hands ---------------------------------------------------

    def carry_out(self, act: int, uid: int, obs: dict, mine: list[dict], done: list[dict], me: dict) -> dict | None:
        """A command to a building (a unit, research, an upgrade), a build task for a probe, WAIT (its
        building is busy, a Pylon is coming), or None (Gary can't)."""
        g = self.g
        have = {u["type"] for u in done}
        if act == TRAIN and uid in P.MERGE:
            return self._merge_plan(uid, mine, done)
        if act == TRAIN and uid in g.race.producer:
            if me["supply_used"] + g.race.supply[uid] > me["supply_max"]:
                return self.wait("supply: a Pylon is coming") if self._pylon_coming(mine) else self.no("supply")
            b = self.free_building(obs, mine, done, g.race.producer[uid], depth=self.train_depth)
            return self._command_or_wait(b, done, g.race.producer[uid], act, uid, g.race.costs[uid])
        if act == BUILD and uid == g.race.gas_building:
            spot = self.free_geyser(obs, mine)
            return {"kind": "build", "where": spot[0], "data": {"spot": spot[1]}, "cost": g.race.costs[uid]} \
                if spot else self.no("no free geyser")
        if act == BUILD and uid in g.race.sizes and uid != g.race.town_hall:
            if uid not in UNPOWERED and P.PYLON not in have:
                return self.wait("no Pylon's power yet: one is coming", coming=True) if self._pylon_coming(mine) \
                    else self.no("no Pylon's power")
            where, side = self.place(uid, mine)
            if self.place_on and uid != P.PYLON and uid not in UNPOWERED and self._power_coming(where, mine):
                # (option place: drawn for a base whose only Pylons are still warping in, it waits for them rather than
                # standing at another base, as a wall's Gateway waits for the wall's Pylon)
                return self.wait("no power at its base yet: a Pylon is coming there", coming=True)
            if self.place_on and uid != P.PYLON and uid not in UNPOWERED and not self._pylon_at(where, mine):
                if g.building(P.PYLON):
                    return self.wait("no Pylon at its base: one is on its way", coming=True)
                # (option place: drawn for a base with no Pylon of Gary's, a Pylon there first and the building after it,
                # as the pros' natural Pylon stands before their cannon there: the spot search's fallback stood it at
                # another base, the first cannon in the main in 23% of games, the pros' 5%, 11 of round PL216a's 48 as
                # the natural's Nexus warped in with nothing else at the natural)
                return {"kind": "build", "where": where, "data": {"side": side}, "cost": g.race.costs[P.PYLON],
                        "unit": P.PYLON, "first": True}
            if uid == P.PYLON and self.power_for is not None and g.hi.frame - self.power_short < POWER_SHORT_FOR:
                where, side = self.power_for         # (the Pylon where the power was missing; kept for the window, as
                                                     # carry_out also answers what Gary can do, not only what it does)
            return {"kind": "build", "where": where, "data": {"side": side}, "cost": g.race.costs[uid]}
        if act == EXPAND and uid == g.race.town_hall:
            base = self.free_base(obs)
            return {"kind": "build", "where": "natural" if base is g.natural else base,
                    "cost": g.race.costs[g.race.town_hall]} if base else self.no("no free base")
        if act == RESEARCH and uid in g.race.research and uid not in g.researched:
            where, cost = g.race.research[uid]
            b = self.free_building(obs, mine, done, where)
            return self._command_or_wait(b, done, where, act, uid, cost)
        if act == UPGRADE and uid in g.race.upgrade:
            where, cost, levels = g.race.upgrade[uid]
            level = g.upgraded[uid]
            if level >= levels:
                return self.no("done already")
            need = P.UPGRADE_LEVEL_2_NEEDS.get(uid)
            if level >= 1 and need is not None and need not in have:
                return self.no(f"no {P.NAMES[need]} for its next level")
            b = self.free_building(obs, mine, done, where)
            cost = (cost[0] + 75 * level, cost[1] + 75 * level)
            return self._command_or_wait(b, done, where, act, uid, cost)
        if act == RESEARCH and uid in g.researched:
            return self.no("done already")
        return self.no("not a decision Gary-P carries out")

    def _merge_plan(self, uid: int, mine: list[dict], done: list[dict]) -> dict | None:
        g = self.g
        kind = P.MERGE[uid]
        given = {t for m in self.merges for t in m["tags"]}
        free = [u for u in done if u["type"] == kind and u["order"] not in MERGING and u["tag"] not in given
                and g.unselectable.get(u["tag"], 0) <= g.hi.frame]
        if len(free) < 2:
            coming = sum(1 for u in mine if u["type"] == kind) + self.in_production(mine)[kind] >= 2
            return self.wait(f"two {P.NAMES[kind]} to merge: coming") if coming else self.no(f"no two {P.NAMES[kind]}")
        a, b = min(((a, b) for i, a in enumerate(free) for b in free[i + 1:]),
                   key=lambda p: (round(math.dist((p[0]["x"], p[0]["y"]), (p[1]["x"], p[1]["y"])) / 64),
                                  p[0]["energy"] + p[1]["energy"]))
        return {"kind": "merge", "id": uid, "tags": [a["tag"], b["tag"]], "cost": (0, 0)}

    def release_reservations(self, mine: list[dict]) -> None:
        super().release_reservations(mine)
        g = self.g
        units = {u["tag"]: u for u in mine}
        for m in list(self.merges):
            us = [units.get(t) for t in m["tags"]]
            if any(u is not None and u["type"] == m["id"] for u in us):
                g.leases.release(m["tags"])              # (an Archon began: what it does next is the fight's)
                self.merges.remove(m)
            elif g.hi.frame >= m["at"] + MERGE_SEEN and not all(u is not None and u["order"] in MERGING for u in us):
                self.undecided(TRAIN, m["id"])           # (cancelled, or one died: no Archon)
                g.leases.release(m["tags"])
                self.merges.remove(m)

    def _task_merge(self, obs: dict, mine: list[dict], t: Task) -> None:
        """Exactly the two Templar selected (the motor's clicks), then the merge key. Given up, the decision taken
        back, when one is gone or MERGE_FOR passed (the dataset counts the Archons that formed)."""
        g, d = self.g, t.data
        units = [u for u in mine if u["tag"] in d["tags"]]
        d.setdefault("key", ("merge",))
        if len(units) < 2 or g.hi.frame - t.started > MERGE_FOR:
            self.undecided(TRAIN, d["id"])
            g.task = None
            return
        if not g.motor._exact(obs, units, set(obs["selection"]), set(d["tags"]), t):
            if g.task is None:                           # (its clicks didn't take them)
                self.undecided(TRAIN, d["id"])
            return
        r = g.hi.merge_archon(dark=d["id"] == P.DARK_ARCHON)
        if not r.accepted:
            return                                       # (no APM left: again next turn)
        g.leases.take(d["tags"], Intent("MERGE", list(d["tags"]), None, {}, "hands:merge"))
        self.merges.append({"tags": list(d["tags"]), "id": d["id"], "at": max(r.land_frame, g.hi.frame)})
        g.say(f"merge: 2 {P.NAMES[P.MERGE[d['id']]]} -> {P.NAMES[d['id']]}")
        g.task = None

    def spot(self, unit_type: int, base, builder: int, side: str = "front") -> tuple[int, int] | None:
        """A Pylon at the nearest spot, at its base or another of Gary's, whose field powers ROOM_MIN free buildable
        tiles that no other Pylon (built, warping in, or reserved) powers; else the nearest as before. Nearest alone,
        each Pylon went inside the last ones' fields: 7 within 6 tiles of each other at 7:00 in a PvZ game, the whole
        map with 18 Gateway spots by the game's check and one with room to walk around it (17 Gateways a game dropped,
        no spot for them, in rounds ST186a and SV187a, while it had more Pylons than the pros)."""
        if unit_type == P.PYLON:
            mine = [u for u in self.g.hi.observe()["units"] if u["owner"] == self.g.slot]
            try:
                for s in ([side, "front"] if side == "minerals" else [side]):   # (no room by the minerals: the front)
                    self.room_only = s != "minerals"     # (by the mineral line: the cannons' power, as the pros')
                    for b in [base] + [o for o in self.my_bases(mine) if o is not base]:
                        if spot := self._base_spot(unit_type, b, builder, side=s):
                            return spot
            finally:
                self.room_only = False
        if self.place_on and unit_type not in UNPOWERED:
            if spot := self._base_spot(unit_type, base, builder, side=side):
                return spot
            # (option place: no power where it was drawn; at that base's front for now, or another base's, and the
            # next Pylon there: a cannon by the mineral line drew one in 2 of 5 after 5:00 and stood there in 1 of 10,
            # at newer bases 1 in 25 of 4; a full main sent PvT's opening tech to the natural's Pylon, Robotics
            # Facilities there 50% before 5:00 and Cybernetics Cores 38%, the pros' 2% and 6%, round PT204a)
            g = self.g
            self.power_short = g.hi.frame
            self.power_for = ("main" if base is g.main else "natural" if base is g.natural else base, side)
            side = "front"
        return super().spot(unit_type, base, builder, side)

    def spot_order(self, unit_type: int, cands: list[tuple[float, int, int]]) -> list[tuple[float, int, int]]:
        if unit_type != P.PYLON or not cands or not self.room_only:
            return cands
        room, x0, y0 = self.pylon_room(cands)
        return [c for c in cands if room[c[2] - y0, c[1] - x0] >= ROOM_MIN]

    def pylon_room(self, cands: list[tuple[float, int, int]]):
        """(room, x0, y0): room[ty - y0, tx - x0] the free buildable tiles a Pylon at (tx, ty) would power that no
        other Pylon does, over the candidates' box."""
        import numpy as np
        g = self.g
        x0 = min(tx for _, tx, _ in cands) - 10
        y0 = min(ty for _, _, ty in cands) - 7
        x1 = max(tx for _, tx, _ in cands) + 12
        y1 = max(ty for _, _, ty in cands) + 9
        terrain = self.terrain()
        if terrain is not None:
            build = terrain[0]
            free = np.zeros((y1 - y0, x1 - x0), bool)
            sy0, sx0 = max(0, y0), max(0, x0)
            sy1, sx1 = min(build.shape[0], y1), min(build.shape[1], x1)
            free[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = build[sy0:sy1, sx0:sx1]
        else:
            free = np.ones((y1 - y0, x1 - x0), bool)
        pylons = [(tx, ty) for ut, tx, ty in g.reserved if ut == P.PYLON]
        units = g.hi.observe()["units"]
        if self.place_on and g.natural is not None and not self.hall_at(g.natural, [u for u in units if u["owner"] == g.slot]):
            # (option place: the natural's site kept for its Nexus, as _base_spot keeps it: counted as room, the
            # natural's first Pylon powered mostly that site, and the gateway-first Gateway found no spot there, placed
            # at 2:26 against the pros' 1:13, its first Zealot at 3:27 against their 1:54, round PL210a)
            hw, hh = g.race.sizes[g.race.town_hall]
            bx, by = g.natural.tile
            free[max(0, by - HALL_CLEAR - y0):max(0, by + hh + HALL_CLEAR - y0),
                 max(0, bx - HALL_CLEAR - x0):max(0, bx + hw + 2 + HALL_CLEAR - x0)] = False
        for u in units:
            size = g.race.sizes.get(u["type"]) if u["owner"] == g.slot else (2, 1) if u["owner"] == 11 and u["type"] != P.GEYSER \
                else (4, 2) if u["type"] == P.GEYSER else None
            if size is None:
                continue
            bx, by = (u["x"] - size[0] * 16) // 32 - x0, (u["y"] - size[1] * 16) // 32 - y0
            free[max(0, by):max(0, by + size[1]), max(0, bx):max(0, bx + size[0])] = False
            if u["type"] == P.PYLON and u["owner"] == g.slot:
                pylons.append(((u["x"] - 32) // 32, (u["y"] - 32) // 32))
        hy, hx = free.shape
        powered = np.zeros_like(free)
        for px, py in pylons:
            for ox, oy in FIELD:
                x, y = px + ox - x0, py + oy - y0
                if 0 <= x < hx and 0 <= y < hy:
                    powered[y, x] = True
        new = (free & ~powered).astype(np.int16)
        room = np.zeros_like(new)
        for ox, oy in FIELD:                     # room[y, x]: the new tiles a Pylon at (x, y) would power
            dst = room[max(0, -oy):hy - max(0, oy), max(0, -ox):hx - max(0, ox)]
            dst += new[max(0, oy):hy - max(0, -oy), max(0, ox):hx - max(0, -ox)]
        return room, x0, y0

    def _power_coming(self, where, mine: list[dict]) -> bool:
        """The base has Pylons on their way (warping in or placed) and none finished."""
        c = self.g.base(where).center
        near = lambda x, y: math.dist(c, (x, y)) < POWER_NEAR
        if any(u["type"] == P.PYLON and u["completed"] and near(u["x"], u["y"]) for u in mine):
            return False
        return any(u["type"] == P.PYLON and near(u["x"], u["y"]) for u in mine) or \
            any(ut == P.PYLON and near(tx * 32 + 32, ty * 32 + 32) for ut, tx, ty in self.g.reserved)

    def _pylon_at(self, where, mine: list[dict]) -> bool:
        """A Pylon of Gary's at the base: finished, warping in or placed."""
        c = self.g.base(where).center
        return any(u["type"] == P.PYLON and math.dist(c, (u["x"], u["y"])) < POWER_NEAR for u in mine) or \
            any(ut == P.PYLON and math.dist(c, (tx * 32 + 32, ty * 32 + 32)) < POWER_NEAR for ut, tx, ty in self.g.reserved)

    def _pylon_coming(self, mine: list[dict]) -> bool:
        g = self.g
        return any(u["type"] == P.PYLON and not u["completed"] for u in mine) or \
            any(ut == P.PYLON for ut, *_ in g.reserved) or g.building(P.PYLON)

    def supply_due(self, obs: dict, mine: list[dict], done: list[dict], me: dict) -> tuple[int, str, bool] | None:
        """A Pylon ahead of production (option depots: while each producer has less than 2 supply left, as the
        Terran's depot), or for power: a powered building found no powered spot in the last POWER_SHORT_FOR."""
        g = self.g
        if self._pylon_coming(mine) or g.macro.plan(BUILD, P.PYLON, obs, mine, done, me) in (None, WAIT):
            return None
        producers = sum(1 for u in done if u["type"] in g.race.production)
        if me["supply_max"] < 200 and me["supply_max"] - me["supply_used"] < 2 * producers:
            return BUILD, f"rule: a Pylon ahead of production ({me['supply_max'] - me['supply_used']} left, {producers} producers)", \
                False
        if g.hi.frame - self.power_short < POWER_SHORT_FOR:
            return BUILD, "rule: a Pylon for power (a building found no powered spot)", True
        return None

    def fail_build(self, t: Task, why: str = "") -> None:
        """A powered building with no spot: no Pylon's field had room for it (the game's check holds power)."""
        if t.unit_type not in UNPOWERED and why == "no spot for it":
            self.power_short = self.g.hi.frame
        super().fail_build(t, why)

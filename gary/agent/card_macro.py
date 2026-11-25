"""Arm B (docs/REFOCUS.md §3.3, Phase 1 step 8): the recipe card held by the macro with a reserve and a mask, no new
model. Options `armb` (adherence "reactive") and `strict` (adherence "strict", for drills), or a StrategySpec handed to
build_gary (gary/agent/strategy.py: a style's card, a card from a replay, a compiled prompt).

The card (gary/policy/card.py): each one-off milestone the style's modern pros make by 8:00 in half their games, at their
median time t (the replay's clock: 42 ms a frame) and with tol, the pros' 90th percentile of distance from it.

  emit      a milestone not had by EMIT_AHEAD_S before its time is the macro's goal once its money is there (after the
            trunk's directives' goals; in strict mode it takes the place of a goal of the model's own that waits); while
            its money comes it is held in the reserve, less what the income brings as a building's worker walks, and the
            model decides on (as the goal it held the macro: the SCVs waited behind it)
  reserve   for RESERVE_S before its emission (not after), a milestone's money is spoken for: of its minerals what the
            income (the workers at MINING) won't bring by then, summed in the milestones' order (and a due one's waiting
            for its money, above), in Gary.committed() (the
            one reserve: a milestone placed, parked, queued or the goal is counted there already or by the goal's own
            check, so it leaves the reserve); its gas whole, in the macro's kept money
  mask      before the card's horizon (its last milestone's time and tol), the model's one-off draws (tech buildings,
            add-ons, research, upgrades: macro.py _one_off) that are off the card are passed over: in reactive mode those
            the card covers (a style's card covers the taxonomy's key items, taxonomy/discover.py KEY_ITEMS: off it, under
            half the style's pros make it by 8:00; a Comsat, an upgrade or an Armory is no key item, so the card says
            nothing of them and they are never masked) under MASK_P of the model's odds; in strict mode every off-card
            one-off, and any card item drawn before its window (t - tol). An item of an active trunk directive is never
            masked. MASK_P written from step 7a-7b's records (32 games, style 1, 2026-11-24): of the covered items off
            the card before the horizon, the first Machine Shop (8 decisions under 0.10, 3 over) and Science Facility
            (6, 10), nothing else; without the coverage the Comsat (20 of 50), the infantry upgrades (29 of 49) and the
            Barracks after the third (41 of 51) would have been masked.
  yield     in reactive mode, while a trunk directive has an item left to ask, the card reserves and emits nothing (the
            macro asks the trunk first)

Not a stop-gap (AGENTS.md): a decoder of the pros' own timings for a chosen card, and steering for drills. Every goal and
mask is in the records, under the card's strategy_state record (gary/decision_log.py link).
"""
from __future__ import annotations

from gary.decision_log import LOG
from gary.policy.card import item_of

EMIT_AHEAD_S = 10          # a milestone is the goal this long before its time (the builder walks, the order lands at t)
RESERVE_S = 30             # its money held from this long before its emission
MASK_P = 0.10              # reactive: an off-card one-off under these odds is passed over before the horizon
ASK_AGAIN = 10 * 24        # a milestone's goal not carried out is asked again after this
MONEY_WAIT = 30 * 24       # a due milestone's money is held this long at most (the macro's GOAL_TIMEOUT)
FRAME_MS = 42              # the replay's clock (ingest/inventory.py FRAME_MS): a card's seconds -> frames


def frame_of(t: float) -> int:
    return int(round(t * 1000 / FRAME_MS))


class CardPlan:
    """One side's card, held by the macro (gary/agent/macro.py LearnedMacro.card)."""

    def __init__(self, g, card: list[dict], card_id: str, mode: str = "reactive", source: str = "",
                 covers: list | None = None):
        from gary.agent.macro import EXPAND, describe
        self.g, self.mode, self.card_id = g, mode, card_id
        self.card = sorted(card, key=lambda m: m["t"])
        self.horizon = max((frame_of(m["t"] + m["tol"]) for m in self.card), default=0)
        decisions = g.macro.model.spec.decisions
        self.item: dict[str, tuple[int, int]] = {}             # card item name -> (act, uid) of a macro decision
        for act, uid in decisions:
            name = item_of(describe(g.race, act, uid))
            if name not in self.item or act == EXPAND:         # (a Command Center on the card is the expansion)
                self.item[name] = (act, uid)
        self.missing = sorted({m["item"] for m in self.card} - set(self.item))
        self.covers = None if covers is None else {(i, n) for i, n in covers}   # None: every one-off (a replay's card)
        self.initial: dict[str, int] | None = None              # items had at the start (the main's town hall)
        self.asked: dict[tuple[str, int], int] = {}
        self.rid = None
        self.source = source
        self.masked = 0
        self.money_wait: dict[tuple[str, int], tuple[int, int]] = {}    # due milestones waiting for money -> (lead, since)

    # --- what Gary has ---------------------------------------------------------------------------------------------
    def _count(self, item: str, mine: list[dict]) -> int:
        from gary.agent.macro import EXPAND, RESEARCH, UPGRADE
        act, uid = self.item[item]
        g = self.g
        if act == RESEARCH:
            return 1 if uid in g.researched else 0
        if act == UPGRADE:
            return g.upgraded[uid]
        if act == EXPAND:
            uid = g.race.town_hall
        return g.macro.count(mine, uid)

    def have(self, item: str, mine: list[dict]) -> int:
        if item not in self.item:
            return 0
        return self._count(item, mine) - (self.initial or {}).get(item, 0)

    def start(self, mine: list[dict]) -> None:
        """At the first step: the starting items, and the card's record."""
        if self.initial is not None:
            return
        self.initial = {i: self._count(i, mine) for i in self.item}
        r = LOG.trunk(self.g.hi.side, self.g.hi.frame, "strategy_state", transition="card", card_id=self.card_id,
                      adherence=self.mode, source=self.source,
                      milestones=[[m["item"], m["n"], m["t"], m["tol"]] for m in self.card],
                      not_decisions=self.missing, emit_ahead_s=EMIT_AHEAD_S, reserve_s=RESERVE_S,
                      mask_p=None if self.mode == "strict" else MASK_P, horizon_s=round(self.horizon * FRAME_MS / 1000))
        self.rid = r["id"]

    # --- the trunk's directives ------------------------------------------------------------------------------------
    def _directive_items(self) -> set[str]:
        tr = getattr(self.g.macro, "trunk", None)
        if tr is None:
            return set()
        return {item_of(n) for d in tr.state.active_directives for n, _ in d.items}

    def _directive_pending(self, mine: list[dict]) -> bool:
        tr = getattr(self.g.macro, "trunk", None)
        if tr is None or self.mode == "strict":
            return False
        for d in tr.state.active_directives:
            for n, k in d.items:
                it = tr._item(n)
                if it is not None and tr._have(*it, mine) < k:
                    return True
        return False

    # --- emit, reserve, mask ---------------------------------------------------------------------------------------
    def _open(self, mine: list[dict]):
        """The milestones not had yet, in order of time: (milestone, its emission frame)."""
        out = []
        for m in self.card:
            if m["item"] in self.item and self.have(m["item"], mine) < m["n"]:
                out.append((m, frame_of(m["t"] - EMIT_AHEAD_S)))
        return out

    def next_goal(self, obs: dict, mine: list[dict], done: list[dict], me: dict) -> dict | None:
        """The first milestone due, not had, that Gary can do or wait for: a goal in the macro's format."""
        from gary.agent.macro import WAIT
        g, f = self.g, self.g.hi.frame
        if self._directive_pending(mine):
            return None
        for m, at in self._open(mine):
            if f < at:
                break
            key = (m["item"], m["n"])
            if f - self.asked.get(key, -ASK_AGAIN) < ASK_AGAIN:
                continue
            act, uid = self.item[m["item"]]
            if any(b["act"] == act and b["id"] == uid for b in g.macro.queued_builds) or \
                    (act, uid) in {k for k, _ in g.macro.queued}:
                continue                                    # (decided already, waiting for its producer)
            plan = g.macro.plan(act, uid, obs, mine, done, me, capped=False)
            if plan is None:
                self.money_wait.pop(key, None)
                continue
            if plan is not WAIT and (lead := self._short(key, plan, mine, me)) is not None:
                # (its money not there yet: not the goal, which held the macro while it waited, the SCVs too: 17 at
                # 6:00 in a strict style-2 game, 20-24 in the suite's; its money held in the reserve instead, less
                # what the income brings while its builder walks, so the model decides on with the rest; for
                # MONEY_WAIT at most, then asked again after ASK_AGAIN, as the goal was dropped and asked again)
                since = self.money_wait.get(key, (0, f))[1]
                if f - since >= MONEY_WAIT:
                    self.money_wait.pop(key)
                    self.asked[key] = f
                    LOG.order(g.hi.side, f, f"{m['item']} (card)", "dropped",
                              f"its money not there in {MONEY_WAIT // 24} s: asked again in {ASK_AGAIN // 24} s",
                              by="card", parent=self.rid)
                    continue
                if key not in self.money_wait:
                    LOG.order(g.hi.side, f, f"{m['item']} (card)", "waiting", "its money: held in the card's reserve",
                              by="card", parent=self.rid)
                self.money_wait[key] = (lead, since)
                continue
            self.money_wait.pop(key, None)
            self.asked[key] = f
            return {"act": act, "id": uid, "p": 1.0, "since": f, "name": f"{m['item']} (card)", "uncapped": True,
                    "card": key, "due_s": m["t"]}
        return None

    def _short(self, key, plan: dict, mine: list[dict], me: dict) -> int | None:
        """A due milestone's money isn't there (the macro's own test: its minerals less what the income brings while a
        building's worker walks, its gas whole, after what is spoken for and kept but its own share of the reserve):
        the minerals the income brings meanwhile, or None if it is there."""
        from gary.agent.macro import MINING, WALK_AHEAD
        g, mac = self.g, self.g.macro
        minerals, gas = plan["cost"]
        workers = sum(1 for u in mine if u["type"] == g.race.worker)
        lead = int(max(WALK_AHEAD, mac._walk_s(plan)) * MINING * workers) if plan["kind"] == "build" else 0
        kept_m, kept_g = mac._kept_cost(card=False)
        prior_m, prior_g = self.reserve(mine, before=key)       # (only the milestones before it: each waited for
        budget = me["minerals"] - (g.committed() - self.reserve(mine)[0] + prior_m) - kept_m   # the others' gas)
        if budget >= minerals - lead and me["gas"] - kept_g - prior_g >= gas:
            return None
        return lead

    def adopt(self, goal: dict, mine: list[dict]) -> bool:
        """Strict: the model's own goal is a due milestone's item: it is kept as the milestone (replaced by the same item,
        a style-3 drill's Factory drawn by the dice at 2:34 waited 8 s more as the card's)."""
        f = self.g.hi.frame
        for m, at in self._open(mine):
            if f < at:
                break
            if self.item[m["item"]] == (goal["act"], goal["id"]):
                goal["card"] = (m["item"], m["n"])
                self.money_wait.pop(goal["card"], None)
                LOG.order(self.g.hi.side, f, goal["name"], "kept", f"the card's {m['item']} #{m['n']} is due: the "
                          "model's own goal is it", by="card", parent=self.rid)
                return True
        return False

    def reserve(self, mine: list[dict] | None = None, before=None) -> tuple[int, int]:
        """The money held for the milestones about to be emitted, and those due that wait for their money (minerals,
        gas; the gas no more than Gary has: held beyond it, the macro's gas test refused even its gasless goals, the
        SCVs and the expansion, a strict game at 12 SCVs from 4:00 to 8:00); before: only the milestones before this
        one."""
        g = self.g
        if mine is None:
            mine = getattr(g, "_mine", None)
        if mine is None or self.initial is None:
            return 0, 0
        if self._directive_pending(mine):
            return 0, 0
        f = g.hi.frame
        goal = g.macro.goal
        held = {(goal["act"], goal["id"])} if goal else set()
        held |= {(b["act"], b["id"]) for b in g.macro.queued_builds} | {k for k, _ in g.macro.queued}
        held |= {(None, ut) for ut, *_ in g.reserved} | {(None, t.unit_type) for t in g.parked}
        from gary.agent.macro import EXPAND, MINING
        income = MINING * sum(1 for u in mine if u["type"] == g.race.worker)     # minerals a second
        need = sm = sg = 0
        for m, at in self._open(mine):
            if f < at - RESERVE_S * 24:
                break
            key = (m["item"], m["n"])
            if key == before:
                break
            if f >= at and key not in self.money_wait:   # (due: emitted, the goal's own check holds its money; one past
                continue                    # its time that can't start yet held its money for minutes, the SCVs waiting)
            act, uid = self.item[m["item"]]
            ut = g.race.town_hall if act == EXPAND else uid
            if (act, uid) in held or (None, ut) in held or g.building(ut):
                continue
            c = g.executor.cost_of(act, uid)
            # (minerals: what the income won't bring by each one's emission, summed in order; a Command Center's whole
            # 400 held for 30 s stopped the SCVs, the strict smoke game's 20 at 6:00 to 24 without the card; one due
            # that waits for its money: less what comes while its builder walks)
            need += c[0]
            sm = max(sm, need - (self.money_wait[key][0] if f >= at else income * (at - f) / 24))
            sg += c[1]
        me = getattr(g, "_me", None)
        return int(max(0, sm)), (min(sg, max(0, me["gas"])) if me is not None else sg)

    def mask(self, act: int, uid: int, p: float, one_off: bool, mine: list[dict]) -> str | None:
        """Why the model's draw of this decision is passed over, or None."""
        from gary.agent.macro import describe
        if self.g.hi.frame >= self.horizon:
            return None
        item = item_of(describe(self.g.race, act, uid))
        if item in self._directive_items():
            return None
        n = self.have(item, mine) + 1
        m = next((m for m in self.card if m["item"] == item and m["n"] == n), None)
        if m is not None:
            if self.mode == "strict" and self.g.hi.frame < frame_of(m["t"] - m["tol"]):
                return f"card: {item} #{n} is due at {m['t']:.0f}s (strict)"
            return None
        if not one_off:
            return None
        if self.mode == "strict":
            return f"card: {item} #{n} is off the card (strict)"
        if (self.covers is None or (item, n) in self.covers) and p < MASK_P:
            return f"card: {item} #{n} is off the card, under {MASK_P:.0%}"
        return None

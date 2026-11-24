"""The strategic trunk (docs/REFOCUS.md §3.2, Phase 1 step 7b; option `trunk`): a persistent StrategyState whose
reactive directives are started by the pros' conditional choice frequencies given the plan belief, and carried out
as the macro's goals, every step of it in the records and joined by ids (gary/decision_log.py link).

Every 30 s from 2:30 to 10:00 (the belief's samples, as its data's): the belief (gary/policy/plan_belief.py, a pinned
model; with the sighting state's looked split), then each directive not yet started is scored
(gary/agent/selector.py ProFrequencyScorer: P_pro(branch | belief, own state), a pinned table of
train/pro_branch.py) and started where P_pro reaches the table's threshold with its support. (and where its interval is clear of the same cell's with a low belief: the part of the choice the belief makes).
A started directive asks
its items, in order, as the macro's goals (the first one Gary lacks and can make or wait for; asked again after
ASK_AGAIN), and ends when Gary has every item (no withdrawal in this first version: a directive started on a wrong
belief runs to its end, so a false start shows in the games). After 10:00 no new belief and no new directive; the
started ones go on.

Every race and matchup builds it: where there is no belief model, table or directive for the matchup, the providers
answer "not enough evidence" (once, in the records) and the trunk does nothing. It draws nothing; its rng (the game's
seed and the slot) is passed to the providers for the contract's sake.

Directives (race-keyed: (race, enemy race) -> name -> items, by the race's names):
  PREP_VS_LURKER (T against Z): a Factory, a Machine Shop, Siege Mode, 2 Siege Tanks, a Starport, a Control Tower, a
  Science Facility, 2 Science Vessels (answers.py's lurker answer without Irradiate and its later tanks)
"""
from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

from gary.agent.contracts import (CandidateBranch, Directive, NotEnoughEvidence, OwnContext, PlanBelief,
                                  SightingView, StrategyState)
from gary.decision_log import LOG

REPO = Path(__file__).resolve().parents[2]
FIRST_S, LAST_S, EVERY_S = 150, 600, 30      # the belief's samples (s), as train/plan_belief.py's
ASK_AGAIN = 30 * 24                          # a directive's item not carried out is asked again after this
LOOK_EVERY = 48                              # frames between the trunk's own sighting looks (without scansample's)
TRAIN, BUILD, RESEARCH = 0, 3, 4             # the macro's acts (gary/agent/macro.py)
DIRECTIVES = {
    ("T", "Z"): {"PREP_VS_LURKER": (("Factory", 1), ("Machine Shop", 1), ("Siege Mode", 1),
                                    ("Siege Tank", 2), ("Starport", 1), ("Control Tower", 1),
                                    ("Science Facility", 1), ("Science Vessel", 2))},
}
EXIT = "every item had (started); no withdrawal in this version"


class BeliefProvider:
    """contracts.PlanBeliefProvider: the pinned plan belief for a side's slot against the enemy's race."""

    def __init__(self, g, path: str | None):
        from gary.policy.plan_belief import PlanBelief as Model, PlanMemory
        self.g = g
        self.enemy = g.enemy.race if getattr(g, "enemy", None) is not None else None
        self.model = Model(REPO / path) if path and (REPO / path).exists() and self.enemy else None
        self._memory_cls = PlanMemory
        self.state = None                    # the sighting state: scansample's if it runs, else the trunk's own
        self.reset()
        self.map_name = None
        name = getattr(g.map, "name", None) if g.map is not None else None
        if name:
            import sys
            sys.path.insert(0, str(REPO / "ingest"))
            from ladder_maps import clean_name
            self.map_name = clean_name(name)

    def reset(self) -> None:
        self.memory = self._memory_cls(self.enemy) if self.model is not None else None
        self.next_s = FIRST_S
        self.next_look = 0
        self.own_state = None

    def _sightings(self):
        sc = getattr(self.g.macro, "scouting", None)
        if sc is not None:
            return sc.state                  # (scansample looks every LOOK_EVERY with its scans)
        if self.own_state is None:
            from gary.policy.army import is_building
            from gary.policy.sightings import SightingState
            try:
                heights = self.g.hi.game.terrain()[1]
            except Exception:                # (no terrain: every height seen)
                heights = None
            self.own_state = SightingState(self.g.map, self.g.slot, self.g.main.center, self.enemy, is_building, heights)
        return self.own_state

    def update(self, obs: dict, ctx: OwnContext):
        if self.model is None:
            return NotEnoughEvidence("plan_belief", f"no plan belief model for {ctx.matchup} {ctx.race}")
        g, f = self.g, obs["frame"]
        st = self._sightings()
        if st is self.own_state and f >= self.next_look:
            self.next_look = f + LOOK_EVERY
            units = [u for u in obs["units"] if u["owner"] in (g.slot, 11)
                     or "visible_to" not in u or (u["visible_to"] >> g.slot) & 1]
            st.look(units, f)                # (no scans: the trunk's own state knows none)
        self.memory.look(f, obs["units"], g.slot)
        if len(self.memory.rows) <= self.next_s or self.next_s > LAST_S:
            return None
        self.next_s += EVERY_S
        row = self.memory.features()
        if row is None:
            return None
        from gary.policy.plan_belief import is_looked, tech_of
        odds = self.model.odds(row, self.map_name)
        tech = {}
        for k, p in odds.items():
            tech[tech_of(k)] = tech.get(tech_of(k), 0.0) + p
        feats = st.features(f)
        main = st.main.main
        mreg = st._region(g.map.base_near(main)) if main is not None else None
        view = SightingView(st.seen, st.confirmed_absent, st.unscouted,
                            {k: (r.frame, round(r.cover, 2)) for k, r in st.regions.items()},
                            is_looked(feats), st.plan_first)
        evidence = {"obs_f": int(f), "plan_tech_first_f": st.plan_first,
                    "main_known": main is not None, "main_look_f": mreg.frame if mreg else None,
                    "main_cover": round(mreg.cover, 2) if mreg else None,
                    "sightings": "scansample's" if st is not self.own_state else "the trunk's own (no scans)"}
        top = sorted(odds.items(), key=lambda kv: -kv[1])[:5]
        r = LOG.trunk(g.hi.side, f, "plan_belief", odds=[[k, round(p, 3)] for k, p in top],
                      tech={k: round(v, 3) for k, v in tech.items()}, looked=view.looked, evidence=evidence,
                      model=Path(self.model.path).parent.name)
        return PlanBelief(f, odds, tech, view, evidence, r["id"], Path(self.model.path).parent.name)


class Trunk:
    """contracts.StrategyTrunkProvider, and the macro's source of a directive's goals."""

    def __init__(self, g, cfg: dict):
        from gary.agent.selector import ProFrequencyScorer
        self.g = g
        key = f"{g.matchup}_{g.race.letter}" if g.matchup else None
        self.belief = BeliefProvider(g, (cfg.get("plan_belief") or {}).get(key))
        tables = {b: REPO / p for b, p in ((cfg.get("tables") or {}).get(key) or {}).items() if (REPO / p).exists()}
        self.scorer = ProFrequencyScorer(tables)
        enemy = g.enemy.race if getattr(g, "enemy", None) is not None else None
        self.directives = DIRECTIVES.get((g.race.letter, enemy), {})
        self.rng = random.Random(f"trunk/{g.game_seed}/{g.hi.slot}")
        card, card_id = [], None
        cards = cfg.get("cards")
        if cards and (REPO / cards).exists() and g.macro is not None and key == "TvZ_T":
            from gary.policy.card import load_cards
            style = g.macro.tracker.style
            card = load_cards(REPO / cards)["cards"].get(str(style)) or []
            card_id = f"{Path(cards).stem} style {style}" if card else None
        self.state = StrategyState(card_id, card, "reactive")
        self.done: set[str] = set()                            # directives ended
        self.start_rid: dict[str, int] = {}                    # directive -> its strategy_state record
        self.asked: dict[tuple[int, int], int] = {}            # item -> frame last asked
        self.pending: dict[tuple[int, int], tuple[int, int, int]] = {}   # item -> (decision id, had then, frame)
        self.said: set[str] = set()                            # "not enough evidence" said once per provider and why
        self._ids = None

    # --- the own state ------------------------------------------------------------------------------------------
    def context(self, obs: dict, mine: list[dict], me: dict) -> OwnContext:
        g = self.g
        units = Counter(g.race.names.get(u["type"], str(u["type"])) for u in mine)
        res = frozenset(g.race.tech_names.get(t, str(t)) for t in g.researched)
        return OwnContext(obs["frame"], g.race.letter, g.enemy.race if getattr(g, "enemy", None) is not None else None, g.matchup,
                          self.belief.map_name, dict(units), res, int(me.get("minerals", 0)), int(me.get("gas", 0)),
                          int(me.get("supply_used", 0)), int(me.get("supply_max", 0)))

    def _item(self, name: str) -> tuple[int, int] | None:
        """(act, id) of an item by the race's names."""
        from gary.policy.army import is_building
        race = self.g.race
        if self._ids is None:
            self._ids = {"tech": {v: k for k, v in race.tech_names.items()}, "unit": {v: k for k, v in race.names.items()}}
        if name in self._ids["tech"]:
            return RESEARCH, self._ids["tech"][name]
        uid = self._ids["unit"].get(name)
        if uid is None:
            return None
        return (BUILD if is_building(uid) else TRAIN), uid

    def _have(self, act: int, uid: int, mine: list[dict]) -> int:
        return (1 if uid in self.g.researched else 0) if act == RESEARCH else self.g.macro.count(mine, uid)

    # --- the provider's step -------------------------------------------------------------------------------------
    def step_state(self, belief, current: StrategyState, ctx: OwnContext, rng) -> tuple[StrategyState, list[dict]]:
        """contracts.StrategyTrunkProvider.step: score the directives not started, start those that pass."""
        g, out = self.g, []
        if isinstance(belief, NotEnoughEvidence):
            return current, out
        active = {d.id for d in current.active_directives}
        cands = [CandidateBranch(n, {}) for n in self.directives if n not in active and n not in self.done]
        siege = "Siege Mode" in ctx.researched
        for c in cands:
            if siege and c.name == "PREP_VS_LURKER":     # (the pros' table counts only moments before Siege Mode)
                if "siege first" not in self.said:
                    self.said.add("siege first")
                    out.append(LOG.trunk(g.hi.side, ctx.frame, "branch_select", parent=belief.record_id, branch=c.name,
                                         offered=False, why="Siege Mode ordered already: the pros' table has no moment"))
                continue
            s = self.scorer.score(belief, current, ctx, [c])[c.name]
            if isinstance(s, NotEnoughEvidence):
                out.append(LOG.trunk(g.hi.side, ctx.frame, "branch_select", parent=belief.record_id, branch=c.name,
                                     not_enough=s.why))
                continue
            thr = self.scorer.tables[c.name]["meta"]["threshold"]
            take = s.take
            r = LOG.trunk(g.hi.side, ctx.frame, "branch_select", parent=belief.record_id, branch=c.name,
                          chosen=c.name if take else "none", p_pro=s.p, interval=[s.lo, s.hi], n=s.n, cell=s.cell,
                          backoff=s.level, threshold=thr, contrast_p=s.base_p, contrast_hi=s.base_hi,
                          table=self.scorer.tables[c.name]["name"],
                          pro_won_if_taken=s.pro_won_if_taken, pro_won_if_not=s.pro_won_if_not,
                          note="P_pro decides; the pros' win rates are context only")
            out.append(r)
            if not take:
                continue
            items = self.directives[c.name]
            sr = LOG.trunk(g.hi.side, ctx.frame, "strategy_state", parent=r["id"], transition="start", directive=c.name,
                           items=[list(i) for i in items], exit=EXIT, p_pro=s.p, n=s.n,
                           active=sorted(active | {c.name}))
            d = Directive(c.name, {"p_pro": s.p, "n": s.n, "cell": s.cell}, items, ctx.frame, EXIT, sr["id"])
            current.active_directives.append(d)
            current.history.append({"f": ctx.frame, "transition": "start", "directive": c.name, "record": sr["id"]})
            self.start_rid[c.name] = sr["id"]
            active.add(c.name)
            g.say(f"strategy: {c.name} (pros {s.p:.0%} of {s.n} games in {s.cell})")
            out.append(sr)
        return current, out

    def step(self, obs: dict, mine: list[dict], me: dict) -> None:
        """Every macro step: the belief's sample when due, the directives scored, ended and their items' fates."""
        g = self.g
        ctx = self.context(obs, mine, me)
        b = self.belief.update(obs, ctx)
        if isinstance(b, NotEnoughEvidence):
            if b.why not in self.said:
                self.said.add(b.why)
                LOG.trunk(g.hi.side, ctx.frame, "branch_select", not_enough=b.why)
        elif b is not None:
            self.state, _ = self.step_state(b, self.state, ctx, self.rng)
        for item, (rid, had, f0) in list(self.pending.items()):
            if self._have(*item, mine) > had:
                del self.pending[item]
                LOG.trunk(g.hi.side, ctx.frame, "fate", parent=rid, item=self._name(*item), fate="started",
                          after_s=round((ctx.frame - f0) / 24, 1))
        for d in list(self.state.active_directives):
            if all(self._have(*self._item(n), mine) >= k for n, k in d.items if self._item(n) is not None):
                self.state.active_directives.remove(d)
                self.done.add(d.id)
                r = LOG.trunk(g.hi.side, ctx.frame, "strategy_state", parent=d.trigger_record_id, transition="end",
                              directive=d.id, why="completed", after_s=round((ctx.frame - d.started_frame) / 24, 1),
                              active=sorted(x.id for x in self.state.active_directives))
                self.state.history.append({"f": ctx.frame, "transition": "end", "directive": d.id, "record": r["id"]})
                g.say(f"strategy: {d.id} done")

    def _name(self, act: int, uid: int) -> str:
        race = self.g.race
        return (race.tech_names.get(uid) if act == RESEARCH else race.names.get(uid)) or str(uid)

    def next_goal(self, obs: dict, mine: list[dict], done: list[dict], me: dict) -> dict | None:
        """The first item of an active directive Gary lacks and can make (or wait for), as a macro goal."""
        g, f, mac = self.g, self.g.hi.frame, self.g.macro
        for d in self.state.active_directives:
            for name, n in d.items:
                item = self._item(name)
                if item is None:
                    continue
                if self._have(*item, mine) >= n or f - self.asked.get(item, -ASK_AGAIN) < ASK_AGAIN:
                    continue
                plan = mac.plan(*item, obs, mine, done, me)
                if not isinstance(plan, dict) or plan.get("kind") == "wait":
                    continue
                self.asked[item] = f
                return {"act": item[0], "id": item[1], "p": 1.0, "since": f, "name": f"{name} ({d.id})",
                        "directive": d.id, "parent": d.trigger_record_id, "p_pro": d.params["p_pro"],
                        "n_pro": d.params["n"]}
        return None

    def decided(self, goal: dict, r: dict, mine: list[dict]) -> None:
        """The macro's decision record of a directive's goal: its fate is watched from now."""
        item = (goal["act"], goal["id"])
        self.pending[item] = (r["id"], self._have(*item, mine), self.g.hi.frame)

"""Log-only providers beside play (option `shadow`, docs/REFOCUS.md Phase 1 step 6): the plan belief
(gary/policy/plan_belief.py) and the recipe card's tags (gary/policy/card.py), written to the records ("plan" and
"card", gary/decision_log.py) and nothing else.

Log-only means it cannot move play: it gives no order, holds no hands, changes no state another layer reads and draws
from no random stream (the belief is a deterministic model, the card the style's, the tags rules). Both are pinned:
the belief's model file and the cards file are named in the manifest, never the newest in a glob. Checked by the
parity hashes with it on (tests/test_parity.py).
"""
from __future__ import annotations

from pathlib import Path

from gary.decision_log import LOG

REPO = Path(__file__).resolve().parents[2]
FIRST_S, LAST_S, EVERY_S = 150, 600, 30   # the belief's records: as train/plan_belief.py samples (s)


class Shadow:
    def __init__(self, g, belief_path: str | None, cards_path: str | None):
        from gary.policy.card import CardTagger, load_cards, race_costs
        from gary.policy.plan_belief import PlanBelief, PlanMemory
        self.g = g
        self.side = g.hi.side
        enemy = g.enemy.race if getattr(g, "enemy", None) is not None else None
        self.belief = PlanBelief(REPO / belief_path) if belief_path and enemy and (REPO / belief_path).exists() else None
        self.memory = PlanMemory(enemy) if self.belief is not None else None
        self.next_s = FIRST_S
        self.map_name = None
        name = getattr(g.map, "name", None) if g.map is not None else None
        if name:
            import sys
            sys.path.insert(0, str(REPO / "ingest"))
            from ladder_maps import clean_name
            self.map_name = clean_name(name)
        self.tagger, self.card_id = None, None
        if cards_path and (REPO / cards_path).exists():
            style = g.macro.tracker.style if g.macro is not None else None
            card = load_cards(REPO / cards_path)["cards"].get(str(style))
            if card is not None:
                self.card_id = f"{Path(cards_path).stem} style {style}"
                self.tagger = CardTagger(card, self.card_id, race_costs(g.race))
        self.read = 0                          # LOG.records read so far
        self.buildings: set[int] = set()       # own building tags seen
        self.first_look = True
        self.researched: set[str] = set()

    def step(self, obs: dict, mine: list[dict], me: dict) -> None:
        from gary.policy.card import is_one_off, item_of
        f = obs["frame"]
        if self.memory is not None:
            self.memory.look(f, obs["units"], self.g.slot)
            if len(self.memory.rows) > self.next_s and self.next_s <= LAST_S:   # (row next_s, as the data's sample)
                self.next_s += EVERY_S
                row = self.memory.features()
                if row is not None:
                    odds = self.belief.odds(row, self.map_name)
                    top = sorted(odds.items(), key=lambda kv: -kv[1])[:5]
                    tech = {}
                    for k, p in odds.items():
                        t = k.split(",")[-1].strip() if "," in k else k
                        tech[t] = round(tech.get(t, 0.0) + p, 3)
                    LOG.shadow(self.side, f, "plan", odds=[[k, round(p, 3)] for k, p in top], tech=tech,
                               model=Path(self.belief.path).parent.name)
        if self.tagger is None:
            return
        from gary.policy.army import is_building
        names = self.g.race.names
        for u in mine:
            if u["tag"] in self.buildings or u["type"] not in names or not is_building(u["type"]):
                continue
            self.buildings.add(u["tag"])
            if not self.first_look:             # (the buildings Gary starts with were never ordered)
                self.tagger.start(names[u["type"]], f)
        self.first_look = False
        recs = LOG.records
        for r in recs[self.read:]:
            if r.get("side") != self.side or ("slot" in r and r["slot"] != self.g.slot):
                continue
            if r.get("kind") == "decision" and r.get("layer") == "macro":
                t = self.tagger.decision(r["f"], r.get("choice"), is_one_off(self.g.race, r.get("choice") or ""),
                                         r.get("over"))
                if t is not None:
                    LOG.shadow(self.side, f, "card", card=self.card_id, p=r.get("p"),
                               by="dice" if r.get("by") == "dice" else "rule", **t)
            elif r.get("kind") == "order" and r.get("fate") == "sent":
                w = r.get("what", "")
                for verb in ("research ", "upgrade "):
                    if w.startswith(verb):
                        name = w[len(verb):].split(" (")[0]
                        if name not in self.researched:
                            self.researched.add(name)
                            self.tagger.start(item_of(name), r["f"])
        self.read = len(recs)
        for t in self.tagger.check(f, me.get("minerals", 0), me.get("gas", 0)):
            LOG.shadow(self.side, f, "card", card=self.card_id, **t)

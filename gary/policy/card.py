"""The recipe card and its tags (docs/REFOCUS.md §3.2-3.3, Phase 1 step 6, log-only).

The card of a style (written 2026-11-23 for Arm 0, eval/style_adherence.py arm0): each one-off milestone the style's
modern pros on the ladder maps make by 8:00 in at least half their games, at their median first time (its command,
taxonomy/discover.py first_times), with their own spread around it (the median absolute deviation: how well a pro
holds the card); it is due at that time and the pros' 90th percentile of distance from it. One-off: a building, an add-on, an expansion, a research or an upgrade; units, Supply Depots and
Missile Turrets are production and belong to no card (§3.3).

The tags (§3.3 "Log-only soak"): each macro decision of a one-off is on_card (its item and count are the card's next
of that item) or off_card; each milestone at its due time (the card's time and the pros' spread) is on time or
delayed, and why:
  odds    not yet decided: the macro's odds or its draw didn't pick it
  money   decided, the minerals or gas short of its cost at the due time
  busy    decided, its producer busy or a requirement missing (a decision passed over for it said so)
  hands   decided, affordable, its producer free: not started yet (the builder on its way, the hands elsewhere)
It draws nothing and changes nothing: one code path for the records of played games (eval/card_tags.py) and for play
(gary/agent/shadow.py).
"""
from __future__ import annotations

import json
from pathlib import Path

ALIASES = {"expand": "Command Center", "U-238 Shells": "U-238 Shells (Marine Range)"}   # (a macro choice's name -> the
                                                                                         # key item's)
NOT_ONE_OFF = {"T": {"depot1", "turret", "medic", "vulture", "tank", "valkyrie", "wraith"},
               "Z": {"muta", "lurker", "ling", "hydra", "drone", "overlord"},
               "P": {"zealot", "dragoon", "reaver", "dt", "corsair", "pylon"}}
SHARE_MIN = 0.5                                         # of the style's pros, by 8:00, for a milestone on the card
TOL_PCT = 90                                            # a milestone is due at the card's time and this percentile of
                                                        # the pros' distance from it (a pro is late one time in ten)


def build_cards(pros_by_style: dict, race: str) -> dict:
    """{style: [milestone]} from each style's pros' first times ({feat: seconds}); milestone {feat, item, n, t, tol}."""
    import numpy as np
    from taxonomy.discover import KEY_ITEMS
    items = {f: (name, n) for f, name, n in KEY_ITEMS[race]}
    out = {}
    for style, rows in pros_by_style.items():
        card = []
        for f, (name, n) in items.items():
            v = [r[f] for r in rows if f in r]
            if f in NOT_ONE_OFF.get(race, set()) or len(v) < SHARE_MIN * len(rows):
                continue
            t = float(np.median(v))
            dev = [abs(x - t) for x in v]
            card.append({"feat": f, "item": name, "n": n, "t": round(t, 1), "mad": round(float(np.median(dev)), 1),
                         "tol": round(float(np.percentile(dev, TOL_PCT)), 1), "share": round(len(v) / len(rows), 2)})
        out[str(style)] = sorted(card, key=lambda m: m["t"])
    return out


def load_cards(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


REPLAY_NAMES = {"ComSat": "Comsat Station"}              # (a replay item's name -> the macro choice's)


def item_of(choice: str) -> str:
    """One name for an item, whether a macro choice's or a replay item's (ingest/build_orders.py names upgrades
    "Terran Infantry Weapons", the macro "Infantry Weapons")."""
    choice = REPLAY_NAMES.get(choice, choice)
    if choice.startswith("Terran "):
        choice = choice[len("Terran "):]
    return ALIASES.get(choice, choice)


class CardTagger:
    """One game's tags against one card. Fed decisions (decided), starts (started) and the money and the decisions
    passed over at each step (check); returns the records to write."""

    def __init__(self, card: list[dict], card_id: str, cost: dict[str, tuple[int, int]]):
        self.card, self.card_id, self.cost = card, card_id, cost
        self.names = {m["item"] for m in card}
        self.decided: dict[tuple[str, int], int] = {}     # (item, n) -> frame first decided
        self.started: dict[str, list[int]] = {}           # item -> frames started
        self.blocked: dict[str, int] = {}                 # item -> last frame a decision passed over it as busy / needs
        self.done: set[tuple[str, int]] = set()

    def have(self, item: str, frame: int) -> int:
        return sum(1 for f in self.started.get(item, ()) if f <= frame)

    def start(self, item: str, frame: int) -> None:
        self.started.setdefault(item, []).append(frame)

    def decision(self, frame: int, choice: str, one_off: bool, over: list | None = None) -> dict | None:
        """A macro decision: its tag (on_card / off_card) if a one-off, else None. over: the options it passed over, with
        why (a busy producer, a missing requirement)."""
        for opt, why in over or ():
            if any(w in why for w in ("busy", "can't now: no ", "needs")):
                self.blocked[item_of(opt)] = frame
        if not one_off or not choice:
            return None
        item = item_of(choice)
        n = self.have(item, frame) + 1
        on = any(m["item"] == item and m["n"] == n for m in self.card)
        first = (item, n) not in self.decided
        self.decided.setdefault((item, n), frame)
        return {"tag": "on_card" if on else "off_card", "item": item, "n": n, "again": not first}

    def check(self, frame: int, minerals: float, gas: float) -> list[dict]:
        """The milestones due by now (the card's time and the pros' spread), each once: on time or delayed, and why."""
        out = []
        for m in self.card:
            key = (m["item"], m["n"])
            due = 24 * (m["t"] + m["tol"])
            if key in self.done or frame < due:
                continue
            self.done.add(key)
            if self.have(m["item"], frame) >= m["n"]:
                out.append({"milestone": m["feat"], "tag": "on time", "due_s": round(due / 24)})
                continue
            d = self.decided.get(key)
            if d is None:
                why = "odds"
            else:
                c = self.cost.get(m["item"], (0, 0))
                if minerals < c[0] or gas < c[1]:
                    why = "money"
                elif self.blocked.get(m["item"], -1) >= d:
                    why = "busy"
                else:
                    why = "hands"
            out.append({"milestone": m["feat"], "tag": f"delayed({why})", "due_s": round(due / 24),
                        "decided_s": None if d is None else round(d / 24)})
        return out


def race_costs(race) -> dict[str, tuple[int, int]]:
    """Name -> (minerals, gas) for a Race's units, buildings, research and upgrades (its first level)."""
    out = {race.names[k]: tuple(v) for k, v in race.costs.items() if k in race.names}
    out.update({race.tech_names[k]: tuple(v[1]) for k, v in race.research.items() if k in race.tech_names})
    out.update({race.upgrade_names[k]: tuple(v[1]) for k, v in race.upgrade.items() if k in race.upgrade_names})
    out["Command Center"] = out.get("Command Center", (400, 0))
    out.update({k: out[v] for v, k in ALIASES.items() if v in out})
    return out


def is_one_off(race, choice: str) -> bool:
    """A building (not a depot or a turret), an add-on, an expansion, a research or an upgrade."""
    if choice == "expand":
        return True
    if choice in race.tech_names.values() or choice in race.upgrade_names.values():
        return True
    k = {v: k for k, v in race.names.items()}.get(choice)
    if k is None or k in race.supply or k == race.worker or k == race.supply_provider:
        return False
    return choice not in ("Missile Turret", "Supply Depot", "Spore Colony", "Sunken Colony", "Creep Colony",
                          "Photon Cannon", "Pylon", "Overlord")

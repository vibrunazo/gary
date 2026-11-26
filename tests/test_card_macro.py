"""The recipe card held by the macro (gary/agent/card_macro.py), on a stand-in Gary: a milestone met once is never
reopened, nothing is emitted, reserved or masked past the card's horizon, and strict mode masks only the off-card
one-offs a style's card covers (a Comsat or an upgrade is no departure from it); a replay's card, covering every
one-off, masks them all.

Run: python tests/test_card_macro.py"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gary.agent.card_macro import CardPlan, frame_of
from gary.agent.macro import BUILD, EXPAND
from gary.race import Race

T = Race.of("T")
BARRACKS, ACADEMY, COMSAT, CC = 111, 112, 107, T.town_hall


def _plan(mode: str = "strict", covers=(("Barracks", 1), ("Academy", 1), ("Command Center", 1))):
    reserved: list = []                       # buildings placed and not started: counted by have(), not by _started()

    def count(mine, uid):
        return sum(1 for u in mine if u["type"] == uid) + sum(1 for ut in reserved if ut == uid)

    macro = SimpleNamespace(model=SimpleNamespace(spec=SimpleNamespace(
        decisions=[(BUILD, BARRACKS), (BUILD, ACADEMY), (BUILD, COMSAT), (EXPAND, CC)])),
        count=count, trunk=None, goal=None, queued_builds=[], queued=[])
    g = SimpleNamespace(race=T, hi=SimpleNamespace(frame=0, side="T"), macro=macro, researched=set(), upgraded={})
    card = [{"item": "Barracks", "n": 1, "t": 85.0, "tol": 28.0},
            {"item": "Command Center", "n": 1, "t": 162.0, "tol": 47.0},
            {"item": "Academy", "n": 1, "t": 220.0, "tol": 55.0}]
    p = CardPlan(g, card, "test", mode, covers=None if covers is None else list(covers))
    p.initial = {i: 1 if i == "Command Center" else 0 for i in p.item}      # (the main's town hall)
    return p, g, reserved


def _mine(*types):
    return [{"type": CC}] + [{"type": t} for t in types]


def test_met_once_stays_met():
    p, g, _ = _plan()
    g.hi.frame = frame_of(80)
    assert [m["item"] for m, _ in p._open(_mine())] == ["Barracks", "Command Center", "Academy"]
    p._open(_mine(BARRACKS, CC))                             # the Barracks and the natural stand
    assert ("Barracks", 1) in p.achieved and ("Command Center", 1) in p.achieved
    g.hi.frame = frame_of(200)                               # both lost: not asked for again
    assert [m["item"] for m, _ in p._open(_mine())] == ["Academy"]


def test_placed_not_started_does_not_latch():
    p, g, reserved = _plan()
    g.hi.frame = frame_of(80)
    reserved.append(BARRACKS)                                # placed, its builder walking: had, not met
    assert "Barracks" not in [m["item"] for m, _ in p._open(_mine())]
    assert ("Barracks", 1) not in p.achieved
    reserved.clear()                                         # the placement failed: open again
    assert "Barracks" in [m["item"] for m, _ in p._open(_mine())]


def test_nothing_past_the_horizon():
    p, g, _ = _plan()
    assert p.horizon == frame_of(220 + 55)
    g.hi.frame = p.horizon
    p.money_wait[("Academy", 1)] = (0, 0)
    assert p._open(_mine()) == [] and p.money_wait == {}
    assert p.mask(BUILD, ACADEMY, 0.0, True, _mine()) is None


def test_strict_masks_only_what_a_style_card_covers():
    p, g, _ = _plan("strict")
    g.hi.frame = frame_of(120)
    assert p.mask(BUILD, COMSAT, 0.2, True, _mine()) is None                  # not covered: no departure from the card
    p2, g2, _ = _plan("strict", covers=(("Barracks", 1), ("Command Center", 1), ("Comsat Station", 1)))
    g2.hi.frame = frame_of(120)
    assert "off the card (strict)" in p2.mask(BUILD, COMSAT, 0.2, True, _mine())   # covered and off this card
    p3, g3, _ = _plan("strict", covers=None)                                  # a replay's card: every one-off
    g3.hi.frame = frame_of(120)
    assert "off the card (strict)" in p3.mask(BUILD, COMSAT, 0.2, True, _mine())
    assert "is due at 220s (strict)" in p.mask(BUILD, ACADEMY, 0.5, True, _mine())   # a card item before its window


def test_reactive_unchanged():
    p, g, _ = _plan("reactive", covers=(("Comsat Station", 1),))
    g.hi.frame = frame_of(120)
    assert p.mask(BUILD, COMSAT, 0.05, True, _mine()) is not None             # covered, under MASK_P
    assert p.mask(BUILD, COMSAT, 0.5, True, _mine()) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")

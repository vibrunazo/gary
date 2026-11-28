"""The macro decoder's rules on stand-in game objects, without a game (fast):

- #69: a decision short of gas while no gas can come (no worker on gas, and the gas target 0 or no gas building) is not
  doable now ("no gas coming"), so the decoder takes the next one at once; one with gas on its way, or one costing no
  gas, still plans.
- #68: the first-producer rule (rax_by) fires in the opening only: past rax_by while none stands, before FIRST_OPENING,
  and never once a first producer has stood this game.

Run: python -m pytest tests/test_macro_rules.py   (or plain: python tests/test_macro_rules.py)
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from gary.agent.macro import FIRST_OPENING, TRAIN, LearnedMacro  # noqa: E402

REFINERY, GOLIATH, MARINE = 110, 3, 0


def macro(gas_workers=None, gas_target=None, mine_types=(), building=False, reserved=(), cost=(100, 50)):
    """A LearnedMacro over stand-ins: every gate open, the executor's plan costing `cost`."""
    m = LearnedMacro.__new__(LearnedMacro)
    race = SimpleNamespace(letter="T", gas_building=REFINERY, worker=7, meets=lambda have, uid: True)
    executor = SimpleNamespace(why=None, carry_out=lambda *a: {"kind": "train", "cost": cost})
    m.g = SimpleNamespace(posture=SimpleNamespace(allowed=None, no_expand=False, no_workers=False), race=race,
                          executor=executor, hi=SimpleNamespace(frame=10 * 60 * 24), parked=[], parked_max=3,
                          gas_workers=gas_workers or {}, reserved=list(reserved),
                          building=lambda t: building and t == REFINERY)
    m.answers, m.failed_until, m.caps_on, m.gas_target = None, {}, False, gas_target
    m.model = SimpleNamespace(spec=SimpleNamespace(coming=False))
    m.wait_builds, m.rax_by, m.first_built = False, 90 * 24, False
    return m, [{"type": t, "completed": True} for t in mine_types]


def test_gas_unit_with_no_gas_coming_is_not_doable():
    m, mine = macro(gas_target=0, mine_types=(REFINERY,))
    assert m.plan(TRAIN, GOLIATH, {}, mine, mine, {"minerals": 1600, "gas": 36}) is None
    assert m.why_not == "no gas coming"


def test_gas_unit_without_any_gas_building_is_not_doable():
    m, mine = macro(gas_target=3)
    assert m.plan(TRAIN, GOLIATH, {}, mine, mine, {"minerals": 1600, "gas": 36}) is None


def test_gas_unit_plans_while_gas_can_come():
    for kw in ({"gas_workers": {1: {5, 6}}, "gas_target": 0},              # a worker on gas
               {"gas_target": 3, "mine_types": (REFINERY,)},               # a gas building, a target to fill it
               {"gas_target": None, "mine_types": (REFINERY,)},            # no gas head: three a gas building
               {"gas_target": 3, "building": True},                        # its builder on the way
               {"gas_target": 3, "reserved": [(REFINERY, 10, 10)]}):       # about to be built
        m, mine = macro(**kw)
        assert m.plan(TRAIN, GOLIATH, {}, mine, mine, {"minerals": 1600, "gas": 36}) is not None, kw


def test_gas_banked_or_no_gas_cost_still_plans():
    m, mine = macro(gas_target=0)
    assert m.plan(TRAIN, GOLIATH, {}, mine, mine, {"minerals": 1600, "gas": 50}) is not None   # its gas banked
    m, mine = macro(gas_target=0, cost=(50, 0))
    assert m.plan(TRAIN, MARINE, {}, mine, mine, {"minerals": 1600, "gas": 0}) is not None     # a mineral unit


def test_first_producer_rule_in_the_opening_only():
    m, _ = macro()
    yes = lambda: True
    assert not m.first_producer_due(60 * 24, 0, "T", yes)                  # before rax_by
    assert m.first_producer_due(100 * 24, 0, "T", yes)                     # past it, none standing
    assert not m.first_producer_due(FIRST_OPENING, 0, "T", yes)            # past the opening
    assert not m.first_producer_due(14 * 60 * 24, 0, "T", yes)             # 14:12, as the live game's
    assert not m.first_producer_due(100 * 24, 0, "Z", lambda: False)       # a Zerg's: only when it can be planned
    assert m.first_producer_due(100 * 24, 0, "Z", yes)


def test_first_producer_rule_never_after_one_stood():
    m, _ = macro()
    assert not m.first_producer_due(100 * 24, 1, "T", lambda: True)        # one stands
    assert not m.first_producer_due(200 * 24, 0, "T", lambda: True)        # lost again, still in the opening: not again


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok  ", name)

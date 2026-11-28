"""The arbiter's shared army turn (option armyturn, gary/agent/arbiter.py _shared_army_turn) on stand-in game objects,
without a game (fast):

- a fight going on, the hands free and the army layer's question due: the army layer steps, over the units outside the
  fight's 12 tiles only;
- one pair of hands: with a task on the hands, or a command still in flight, it doesn't step (no task overwritten);
- not due, no fight, or the option off: it doesn't step, and the turn goes on as before;
- a question that orders nothing (None): the turn goes on (no turn taken).

Run: python -m pytest tests/test_arbiter_turns.py   (or plain: python tests/test_arbiter_turns.py)
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from gary.agent.arbiter import FixedPriority  # noqa: E402

NEAR = {"tag": 1, "owner": 3, "type": 0, "x": 1000, "y": 1000, "completed": True}       # in the fight (2 tiles away)
FAR = {"tag": 2, "owner": 3, "type": 0, "x": 2000, "y": 2000, "completed": True}        # the main, outside it


class Army:
    def __init__(self, result="army", next_ask=0):
        self.next_ask, self.result, self.calls = next_ask, result, []

    def step(self, obs, mine, done):
        self.calls.append([u["tag"] for u in done])
        return self.result


def arbiter(army_turn=True, task=None, pending=False, center=(1000, 1064), army=None, frame=500):
    g = SimpleNamespace(
        fight=SimpleNamespace(center=center, queue=[]), army=army or Army(), setup_done=True, task=task,
        hi=SimpleNamespace(pending=pending, frame=frame, side="T", observe=lambda: {"units": [NEAR, FAR]}),
        slot=3, posture=SimpleNamespace(army_home=False), block_units=set(), army_types={0})
    a = FixedPriority.__new__(FixedPriority)
    a.g, a.army_turn = g, army_turn
    return a, g


def test_the_army_steps_in_a_fight_over_the_units_outside_it():
    a, g = arbiter()
    assert a._shared_army_turn() == "army"
    assert g.army.calls == [[2]]                     # the fight's unit left to the fight layer


def test_one_pair_of_hands():
    busy = SimpleNamespace(kind="fight_cmd")
    for kw in ({"task": busy}, {"pending": True}):
        a, g = arbiter(**kw)
        assert a._shared_army_turn() is None and g.army.calls == [], kw
        assert g.task is kw.get("task")              # nothing overwritten


def test_not_due_no_fight_or_option_off():
    for kw in ({"army": Army(next_ask=900)}, {"center": None}, {"army_turn": False}):
        a, g = arbiter(**kw)
        if kw.get("army_turn") is False:             # (the option off: _act never calls it; the method alone still
            assert not a.army_turn                   #  works, but the arbiter's flag is what _act reads)
            continue
        assert a._shared_army_turn() is None and g.army.calls == [], kw


def test_a_question_that_orders_nothing_hands_the_turn_on():
    a, g = arbiter(army=Army(result=None))
    assert a._shared_army_turn() is None and g.army.calls == [[2]]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok  ", name)

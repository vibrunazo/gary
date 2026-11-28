"""The arbiter's shared army turn (option armyturn, gary/agent/arbiter.py _shared_army_turn) on stand-in game objects,
without a game (fast):

- a fight going on, the hands free and the army layer's question due: the army layer steps, over the units outside the
  fight's 12 tiles only;
- one pair of hands: with a task on the hands, or a command still in flight, it doesn't step (no task overwritten);
- not due, or no fight: it doesn't step; a question that orders nothing (None) hands the turn on;
- the order (_act): the fight's queued orders go first; the shared turn goes before the macro's turn and leaves it due;
  with the option off, the macro's turn comes as before;
- the throttle: within COMMIT_TICK of a shared turn that used the hands, none; questions answered "keep" unthrottled.

Run: python -m pytest tests/test_arbiter_turns.py   (or plain: python tests/test_arbiter_turns.py)
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import gary.agent.arbiter as arb  # noqa: E402
from gary.agent.arbiter import COMMIT_TICK, FixedPriority  # noqa: E402

NEAR = {"tag": 1, "owner": 3, "type": 0, "x": 1000, "y": 1000, "completed": True}       # in the fight (2 tiles away)
FAR = {"tag": 2, "owner": 3, "type": 0, "x": 2000, "y": 2000, "completed": True}        # the main, outside it


class Army:
    def __init__(self, result="army", next_ask=0):
        self.next_ask, self.result, self.calls = next_ask, result, []

    def step(self, obs, mine, done):
        self.calls.append([u["tag"] for u in done])
        return self.result


def arbiter(army_turn=True, task=None, pending=False, center=(1000, 1064), army=None, frame=500, queue=None):
    calls = []
    fight = SimpleNamespace(center=center, queue=list(queue or []), next_fight=10 ** 9,
                            next_queued=lambda obs=None: fight.queue.pop(0) if fight.queue else None)
    g = SimpleNamespace(
        fight=fight, army=army or Army(), setup_done=True, task=task, macro_turn=False,
        hi=SimpleNamespace(pending=pending, frame=frame, side="T",
                           observe=lambda: {"units": [NEAR, FAR], "me": {}}),
        slot=3, posture=SimpleNamespace(army_home=False, update=lambda: None), block_units=set(), army_types={0},
        motor=SimpleNamespace(start=lambda it: calls.append(("fight", it))),
        executor=SimpleNamespace(release_reservations=lambda mine: None, resume_construction=lambda mine: False,
                                 resume_parked=lambda obs, mine: False),
        macro=SimpleNamespace(step=lambda *a: calls.append(("macro",))))
    a = FixedPriority.__new__(FixedPriority)
    a.g, a.army_turn, a.shared_used = g, army_turn, -COMMIT_TICK
    return a, g, calls


def test_the_army_steps_in_a_fight_over_the_units_outside_it():
    a, g, _ = arbiter()
    assert a._shared_army_turn() == "army"
    assert g.army.calls == [[2]]                     # the fight's unit left to the fight layer


def test_one_pair_of_hands():
    busy = SimpleNamespace(kind="fight_cmd")
    for kw in ({"task": busy}, {"pending": True}):
        a, g, _ = arbiter(**kw)
        assert a._shared_army_turn() is None and g.army.calls == [], kw
        assert g.task is kw.get("task")              # nothing overwritten


def test_not_due_or_no_fight():
    for kw in ({"army": Army(next_ask=900)}, {"center": None}):
        a, g, _ = arbiter(**kw)
        assert a._shared_army_turn() is None and g.army.calls == [], kw


def test_a_question_that_orders_nothing_hands_the_turn_on():
    a, g, _ = arbiter(army=Army(result=None))
    assert a._shared_army_turn() is None and g.army.calls == [[2]]
    assert a.shared_used == -COMMIT_TICK             # (no hands used: not throttled)


def _act(a, monkey=True):
    arb.posture_mode = lambda p: "normal"            # (the posture's mode: not under test)
    return a._act()


def test_the_fight_queue_goes_first():
    a, g, calls = arbiter(queue=["fire"])
    assert _act(a) == "roles:queued" and calls == [("fight", "fire")] and g.army.calls == []


def test_the_shared_turn_goes_before_the_macro_turn_and_keeps_it_due():
    a, g, calls = arbiter()
    g.macro_turn = True
    assert _act(a) == "army" and g.army.calls == [[2]]
    assert g.macro_turn and ("macro",) not in calls  # (the macro's turn is the next one)
    g.army.next_ask = 10 ** 9                        # (the army's next question not due)
    assert _act(a) == "macro" and not g.macro_turn


def test_the_option_off_leaves_the_order_as_it_was():
    a, g, calls = arbiter(army_turn=False)
    g.macro_turn = True
    assert _act(a) == "macro" and g.army.calls == []


def test_one_shared_turn_using_the_hands_a_commit_tick():
    a, g, _ = arbiter()
    assert a._shared_army_turn() == "army" and a.shared_used == 500
    g.hi.frame = 500 + COMMIT_TICK - 1
    assert a._shared_army_turn() is None and len(g.army.calls) == 1
    g.hi.frame = 500 + COMMIT_TICK
    assert a._shared_army_turn() == "army" and len(g.army.calls) == 2


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok  ", name)

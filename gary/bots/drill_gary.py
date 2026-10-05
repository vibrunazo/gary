"""Gary's fight layer alone, for micro drills (gary/drills.py): no base, no macro model.

The same fight code as Gary v0.7 (snapshot, command model with memory, human-hands executor),
started without the parts that need a base. Unlike v0.7, every command type is the model's (no
guard rail): drills are where reinforcement learning teaches it when a move helps. Workers aren't
the model's (in v0.7 a rule pulls them); in drills they keep mining.

So that a drill isn't a world where the fight gets all of Gary's hands (a real game shares them
with macro), Gary also has:
  - a chore: when the Command Center is idle and minerals allow, Gary checks it (its hotkey, which
    replaces the selection) and trains an SCV if supply allows, in the turn production gets after
    each fight command, as in v0.7 (drills have no depots, so it's mostly the check)
  - interruptions: every 5-12 s the camera goes elsewhere for 1-3 s (as if macroing far away)
"""

from __future__ import annotations

import random

import numpy as np

from gary import terran as T
from gary.bots.terran_v01 import Task
from gary.bots.terran_v07 import TerranGaryV7
from gary.interface import HumanInterface

HK_CC = 4
AWAY_EVERY = (5 * 24, 12 * 24)       # frames between interruptions
AWAY_FOR = (24, 72)                  # frames each lasts


class DrillGary(TerranGaryV7):
    version = "drill"

    def __init__(self, hi: HumanInterface, fight_model, flip: tuple[bool, bool], seed: int = 0, verbose: bool = False,
                 interruptions: bool = True):
        # only what the fight layer uses (TerranGaryV4/V5/V6); no map, base, macro or army models
        self.hi, self.slot = hi, hi.slot
        self.fight_model = fight_model
        self.flip = flip
        self.verbose = verbose
        self.task = None
        self.next_fight = 0
        self.fight_center = None
        self.told = {}
        self.rng = np.random.default_rng(seed)
        self.rl_log = None
        self.macro_turn = False
        self.loaded, self.next_load = {}, 0
        self.production_types = (T.CC,)
        self.attention = random.Random(seed * 7919 + 1)
        self.interruptions = interruptions
        self.next_away = hi.frame + self.attention.randint(*AWAY_EVERY)
        cc = next((u for u in hi.observe()["units"] if u["owner"] == self.slot and u["type"] == T.CC), None)
        self.cc = cc["tag"] if cc else None
        if self.cc:
            hi.hotkeys[HK_CC] = [self.cc]        # as a player has their Command Center on a key

    def act(self) -> None:
        hi = self.hi
        if hi.pending:
            return
        obs = hi.observe()
        mine = [u for u in obs["units"] if u["owner"] == self.slot]
        if self.task:
            return self._run_task(obs, mine)
        if self.interruptions and hi.frame >= self.next_away:
            self.next_away = hi.frame + self.attention.randint(*AWAY_EVERY)
            w, h = hi.map_size
            self.task = Task("away", data={"until": hi.frame + self.attention.randint(*AWAY_FOR),
                                           "to": (self.attention.randint(64, w - 64), self.attention.randint(64, h - 64))},
                             started=hi.frame)
            return self._run_task(obs, mine)
        if self.macro_turn:
            self.macro_turn = False
            if self._chore(obs, mine):
                return
        self._fight(obs, mine)

    def _chore(self, obs: dict, mine: list[dict]) -> bool:
        cc = next((u for u in mine if u["tag"] == self.cc), None)
        if cc and cc["completed"] and not cc.get("queue") and obs["me"]["minerals"] >= 50:
            self.task = Task("chore", started=self.hi.frame)
            self._run_task(obs, mine)
            return True
        return False

    def _run_task(self, obs: dict, mine: list[dict]) -> None:
        t, hi = self.task, self.hi
        if t.kind == "away":                     # the camera elsewhere, as if macroing far away
            if t.stage == "start":
                hi.camera_minimap(*t.data["to"])
                t.stage = "there"
            elif hi.frame >= t.data["until"]:
                self.task = None
            return
        if t.kind == "chore":                    # hotkey the Command Center, train an SCV if supply allows
            me = obs["me"]
            if hi.frame - t.started > 24 * 3:
                self.task = None
            elif obs["selection"] != [self.cc]:
                hi.hotkey_recall(HK_CC)
            else:
                if me["supply_used"] < me["supply_max"]:
                    hi.train(T.SCV)
                self.task = None
            return
        return super()._run_task(obs, mine)

    def _may_issue(self, action: str) -> bool:
        return True

    def _may_command(self, unit: dict) -> bool:
        return unit["type"] != T.SCV                 # as in v0.7: workers are a rule's, not the model's

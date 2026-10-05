"""Gary's fight layer alone, for micro drills (gary/drills.py): no base, no macro.

The same fight code as Gary v0.7 (snapshot, command model with memory, human-hands executor),
started without the parts that need a base. Unlike v0.7, every command type and every unit is
the model's (no guard rails): drills are where reinforcement learning teaches it when a move helps.
"""

from __future__ import annotations

import numpy as np

from gary.bots.terran_v07 import TerranGaryV7
from gary.interface import HumanInterface


class DrillGary(TerranGaryV7):
    version = "drill"

    def __init__(self, hi: HumanInterface, fight_model, flip: tuple[bool, bool], seed: int = 0, verbose: bool = False):
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

    def act(self) -> None:
        hi = self.hi
        if hi.pending:
            return
        obs = hi.observe()
        mine = [u for u in obs["units"] if u["owner"] == self.slot]
        if self.task:
            return self._run_task(obs, mine)
        self._fight(obs, mine)

    def _may_issue(self, action: str) -> bool:
        return True

    def _may_command(self, unit: dict) -> bool:
        return True

"""Gary v0.3, Terran: learned macro (v0.2) and a learned army.

The army model (gary/policy/army.py, trained on pro TvZ army orders) decides where each army
group goes and whether to move or attack-move there: out to attack, back to defend a base, away
from a bigger army, or nowhere (a pro's army stands still about as often as it moves).

With human hands: new army units gather at the rally point, Gary drag-boxes them and adds them to
control groups 1-3 (12 units each, like the real game). Every 2 s it asks the model about each
group; when the model's best destination is at least 2 grid cells (1/8 of the map) from the group
and it says so twice in a row, Gary recalls the group and gives the order on the minimap.

Still scripted: mining, gas, hotkeys and rallies, building placement. Not yet: micro (spreading,
stutter-step, stim, sieging), scouting, drops.

    python -m gary.bots.terran_v03 --map path/to/map.scx --minutes 12
    python -m gary.bots.terran_v03 --live
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from gary import commands as C
from gary import terran as T
from gary.bots import terran_v01 as v01
from gary.bots.terran_v01 import Task
from gary.bots.terran_v02 import TerranGaryV2, latest_model
from gary.env import LIVE_COMMAND_DELAY
from gary.interface import HumanInterface, screen_of
from gary.mapinfo import MapInfo
from gary.policy.army import GRID, ArmyModel, ArmyTracker, is_building, is_worker, supply_x2
from gary.policy.macro import MacroModel

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GROUPS = [1, 2, 3]                  # army control groups
GROUP_SIZE = 12                     # the game's selection limit
MIN_GATHER = 4                      # new units join a group in batches of at least this many
ASK_EVERY = 24 * 2                  # how often Gary asks the model about its army
MOVE_CELLS = 2                      # destinations closer than this are "stay"
REORDER_AFTER = 24 * 8              # don't repeat the same order to a group within 8 s
SCOUT_AT = 24 * 75                  # send a scouting worker at 1:15 (pros: around 10-12 supply)
SCOUT_KEY = 0


def latest_army_model(matchup: str = "TvZ", race: str = "T") -> Path:
    found = sorted((REPO_ROOT / "runs" / "army").glob(f"{matchup}_{race}_*/model.pt"))
    if not found:
        raise SystemExit(f"no trained army model in runs/army (python -m train.army --race {race})")
    return found[-1]


def cell_dist(a: int, b: int) -> int:
    return max(abs(a // GRID - b // GRID), abs(a % GRID - b % GRID))


class TerranGaryV3(TerranGaryV2):
    def __init__(self, hi: HumanInterface, mapinfo: MapInfo, model: MacroModel, army_model: ArmyModel,
                 style: int | None = None, verbose: bool = True):
        super().__init__(hi, mapinfo, model, style, verbose)
        self.army_model = army_model
        self.army_tracker = ArmyTracker(army_model.spec, self.slot, mapinfo.size, self.main.center)
        self.next_ask = 0
        self.ask_turn = 0
        self.member: dict[int, int] = {}              # army unit tag -> its control group
        self.proposed: dict[int, int] = {}            # group -> cell the model proposed last time
        self.ordered: dict[int, tuple[int, int, int]] = {}   # group -> (cell, kind, frame) of last order
        self.scout: int | None = None                 # the scouting worker's tag
        self.scout_targets: list[tuple[int, int]] = []
        self.scout_done = False

    # --- army ------------------------------------------------------------------------------

    def _groups(self, mine: list[dict]) -> dict[int, list[dict]]:
        """Each army unit belongs to one group (the last it was put in); alive units only."""
        out = {k: [] for k in GROUPS}
        for u in mine:
            k = self.member.get(u["tag"])
            if k is not None:
                out[k].append(u)
        return out

    def _army(self, obs: dict, mine: list[dict], done: list[dict]) -> bool:
        hi = self.hi
        if self._scouting(obs, mine):
            return True
        groups = self._groups(mine)
        grouped = {u["tag"] for us in groups.values() for u in us}
        new = [u for u in done if u["type"] in self.army_types and u["tag"] not in grouped]
        room = [k for k in GROUPS if len(groups[k]) + MIN_GATHER <= GROUP_SIZE]
        if room and (len(new) >= MIN_GATHER or (new and not grouped)):
            self.task = Task("gather", data={"tags": [u["tag"] for u in new[:GROUP_SIZE]], "group": room[0]},
                             started=hi.frame)
            return True
        if hi.frame < self.next_ask:
            return False
        live = [k for k in GROUPS if groups[k]]
        if not live:
            return False
        self.next_ask = hi.frame + ASK_EVERY // len(live)        # one group per question, in turn
        k = live[self.ask_turn % len(live)]
        self.ask_turn += 1
        group = groups[k]
        grid, glob = self.army_tracker.inputs(obs, group, supply_x2, is_worker, is_building)
        where, kind = self.army_model.predict(grid, glob)
        best = int(where[0].argmax())
        attack = int(kind[0].argmax()) == 1
        cx = sum(u["x"] for u in group) / len(group)
        cy = sum(u["y"] for u in group) / len(group)
        here = self.army_tracker.cell(cx, cy)
        proposed, self.proposed[k] = self.proposed.get(k), best
        if cell_dist(best, here) < MOVE_CELLS:
            return False                                          # stay
        if proposed is None or cell_dist(proposed, best) > 1:
            return False                                          # wait until it says so twice
        last = self.ordered.get(k)
        if last and cell_dist(last[0], best) <= 1 and last[1] == attack and hi.frame - last[2] < REORDER_AFTER:
            return False
        x, y = self.army_tracker.center(best)
        self.task = Task("army_order", data={"group": k, "x": x, "y": y, "attack": attack, "cell": best,
                                             "p": float(where[0, best])}, started=hi.frame)
        return True

    # --- scouting (scripted for now) -----------------------------------------------------------

    def _scouting(self, obs: dict, mine: list[dict]) -> bool:
        """Like a pro, send a worker to find the enemy base early (the army model needs to know
        where the enemy is): the enemy start locations in turn, then home once it has seen an
        enemy building. True if Gary acted."""
        if self.scout_done:
            return False
        hi = self.hi
        if self.scout is None:
            workers = sum(1 for u in mine if u["type"] == T.SCV)
            if hi.frame >= SCOUT_AT and workers >= 10:
                self.scout_targets = sorted(self.enemy_starts, key=lambda p: math.dist(p, self.main.center))
                self.task = Task("scout", data={"to": self.scout_targets[0]}, started=hi.frame)
                return True
            return False
        scout = next((u for u in mine if u["tag"] == self.scout), None)
        if scout is None:                                  # the scout died
            self.scout_done = True
            return False
        if any(u["owner"] not in (self.slot, 11) and is_building(u["type"]) for u in obs["units"]):
            self.task = Task("scout", data={"to": self.main.minerals[0], "home": True}, started=hi.frame)
            return True                                    # found them: home again
        if self.scout_targets and math.dist((scout["x"], scout["y"]), self.scout_targets[0]) < 6 * 32:
            self.scout_targets.pop(0)                      # nobody here: try the next start
            if self.scout_targets:
                self.task = Task("scout", data={"to": self.scout_targets[0]}, started=hi.frame)
                return True
            self.scout_done = True
        return False

    def _task_scout(self, obs: dict, mine: list[dict], t: Task) -> None:
        hi, d = self.hi, t.data
        if self.scout is None:                             # pick a worker, give it a hotkey
            if t.stage == "start":
                if not self._look_at(obs, "main"):
                    return
                w = self._pick_worker(obs, mine)
                if w is None:
                    self.task = None
                    return
                x, y = screen_of(obs, w["x"], w["y"])
                hi.box(max(0, x - 5), max(0, y - 5), min(hi.p.viewport[0] - 1, x + 5), min(hi.p.viewport[1] - 1, y + 5))
                t.stage = "picked"
                return
            sel = [u for u in mine if u["tag"] in obs["selection"] and u["type"] == T.SCV]
            if len(sel) != 1:
                self.task = None                           # try again later
                return
            self.scout = sel[0]["tag"]
            hi.hotkey_set(SCOUT_KEY)
            t.stage = "go"
            return
        if obs["selection"] != [self.scout]:
            if t.stage == "recalled":
                self.task = None
                return
            hi.hotkey_recall(SCOUT_KEY)
            t.stage = "recalled"
            return
        hi.minimap_right_click(*d["to"])
        if d.get("home"):
            self.scout_done = True
            self._say("scout found the enemy base, heading home")
        else:
            self._say(f"scouting {d['to']}")
        self.task = None

    def _run_task(self, obs: dict, mine: list[dict]) -> None:
        t = self.task
        if t.kind == "scout":
            if self.hi.frame - t.started > 24 * 10:
                self.task = None
                return
            return self._task_scout(obs, mine, t)
        if t.kind in ("gather", "army_order"):
            if self.hi.frame - t.started > 24 * 10:
                self.task = None
                return
            return self._task_gather(obs, mine, t) if t.kind == "gather" else self._task_army_order(obs, t)
        return super()._run_task(obs, mine)

    def _task_gather(self, obs: dict, mine: list[dict], t: Task) -> None:
        """Drag-box the new units (where they stand, normally the rally point) into a group."""
        hi = self.hi
        tags = set(t.data["tags"])
        units = [u for u in mine if u["tag"] in tags]
        if not units:
            self.task = None
            return
        if t.stage == "start":
            cx = sorted(u["x"] for u in units)[len(units) // 2]
            cy = sorted(u["y"] for u in units)[len(units) // 2]
            here = [u for u in units if screen_of(obs, u["x"], u["y"])]
            if len(here) < max(1, len(units) // 2):
                hi.camera_minimap(cx, cy)
                return
            pts = [screen_of(obs, u["x"], u["y"]) for u in here]
            hi.box(max(0, min(p[0] for p in pts) - 10), max(0, min(p[1] for p in pts) - 10),
                   min(hi.p.viewport[0] - 1, max(p[0] for p in pts) + 10),
                   min(hi.p.viewport[1] - 1, max(p[1] for p in pts) + 10))
            t.stage = "add"
            return
        # only fighting units go into the group (the box may have caught a worker passing by); the
        # box can also catch units already in a group: then the box becomes that group
        sel = obs["selection"]
        if sel and len(sel) <= GROUP_SIZE and all(u["type"] in self.army_types for u in mine if u["tag"] in sel):
            old = [self.member[s] for s in sel if s in self.member]
            k = max(set(old), key=old.count) if old else t.data["group"]
            hi.hotkey_set(k)
            for s in sel:
                self.member[s] = k
        self.task = None

    def _task_army_order(self, obs: dict, t: Task) -> None:
        hi, d = self.hi, t.data
        k = d["group"]
        if sorted(obs["selection"]) != sorted(hi.hotkeys.get(k, [])) or not obs["selection"]:
            if t.stage == "recalled":                 # the group is gone (all dead)
                self.task = None
                return
            hi.hotkey_recall(k)
            t.stage = "recalled"
            return
        if d["attack"]:
            hi.minimap_command(C.ORDER_ATTACK_MOVE, d["x"], d["y"])
        else:
            hi.minimap_right_click(d["x"], d["y"])
        self.ordered[k] = (d["cell"], d["attack"], hi.frame)
        self._say(f"group {k} ({len(obs['selection'])} units): {'attack' if d['attack'] else 'move'} "
                  f"to ({d['x']}, {d['y']}) ({d['p']:.0%})")
        self.task = None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", help="a .scm/.scx map (or a pre-1.18 replay) for headless play")
    ap.add_argument("--minutes", type=float, default=12)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--save", default="gary_v03.rep")
    ap.add_argument("--command-delay", type=int, default=LIVE_COMMAND_DELAY)
    ap.add_argument("--macro-model", help="default: the latest TvZ Terran one in runs/macro")
    ap.add_argument("--army-model", help="default: the latest TvZ Terran one in runs/army")
    ap.add_argument("--style", type=int, help="build-style cluster to steer the macro toward")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--live", action="store_true", help="play in a live SC:R client via the bridge")
    ap.add_argument("--pipe", default=r"\\.\pipe\gary_scr")
    ap.add_argument("--profile", default="b_rank", choices=sorted(v01.PROFILES))
    ap.add_argument("--pov", help="where to save the point-of-view log (live)")
    args = ap.parse_args()
    macro = MacroModel.load(args.macro_model or latest_model())
    army = ArmyModel.load(args.army_model or latest_army_model())
    make = lambda hi, mapinfo: TerranGaryV3(hi, mapinfo, macro, army, args.style, verbose=not args.quiet)
    if args.live:
        v01.play_live(args.pipe, args.minutes, args.profile, args.pov or "gary_v03_live.pov.jsonl", make_bot=make)
    else:
        if not args.map:
            ap.error("--map is required unless --live")
        v01.play(args.map, args.minutes, args.seed, args.save, command_delay=args.command_delay,
                 make_bot=make, name="Gary v0.3 (T)")


if __name__ == "__main__":
    main()

"""Gary v0.3, Terran: learned macro (v0.2) and a learned army.

The army model (gary/policy/army.py, trained on pro TvZ army orders) decides where each army
group goes and whether to move or attack-move there: out to attack, back to defend a base, away
from a bigger army, or nowhere (a pro's army stands still about as often as it moves).

With human hands: Gary sees its army as up to 3 clusters by where they stand (the main army,
reinforcements on their way). Every 2 s it asks the model about one cluster; when the model puts
most of its belief on the cluster going somewhere at least 2 grid cells (1/8 of the map) away, and
says so twice in a row, and its fight estimate doesn't expect the move to cost army share (vs
staying), Gary drag-boxes the cluster's units (12 per box, like the real game) and gives the
order on the minimap.

Still scripted: mining, gas, hotkeys and rallies, building placement, one early scouting worker
(at 9 SCVs; the army model needs to know where the enemy is), and a reflex: pulling workers to
fight when enemy units at a base outnumber the army there. Not yet: micro (spreading,
stutter-step, stim, sieging), later scouting, drops.

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
from gary.policy.army import GRID, ArmyModel, ArmyTracker, is_building, supply_x2
from gary.policy.macro import MacroModel

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ASK_EVERY = 24 * 2                  # how often Gary asks the model about its army
MOVE_CELLS = 2                      # destinations closer than this are "stay"
MOVE_P = 0.5                        # move when the model puts more belief than this away from here
FIGHT_MIN = -0.02                   # don't go if the fight estimate says we'd lose 2+ points of army share
FIGHT_MARGIN = 0.01                 # ...or if going looks worse than staying by more than 1 point
REORDER_AFTER = 24 * 8              # don't repeat the same order to a group within 8 s
SCOUT_AT = 24 * 45                  # send a scouting worker from 0:45, at 9 SCVs (like pros)
SCOUT_WORKERS = 9
THREAT_PX = 10 * 32                 # enemy fighters this close to a Command Center threaten its workers
CALM_FRAMES = 24 * 5                # pulled workers go back to mining after 5 s without a threat
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
        self.proposed: dict[int, int] = {}            # cluster cell -> destination the model proposed
        self.ordered: dict[int, tuple[int, bool, int]] = {}   # cluster cell -> (cell, attack, frame)
        self.held: dict[int, int] = {}                # cluster cell -> destination Gary decided against
        self.scout: int | None = None                 # the scouting worker's tag
        self.scout_targets: list[tuple[int, int]] = []
        self.scout_done = False
        self.pulled: set[int] = set()                 # workers pulled off the minerals to fight
        self.next_pull = 0
        self.calm_since = 0

    def act(self) -> None:
        if not self.hi.pending:                   # whatever Gary looks at, it remembers
            self.army_tracker.remember(self.hi.observe())
        super().act()

    # --- army ------------------------------------------------------------------------------

    def _clusters(self, army: list[dict]) -> list[list[dict]]:
        """The army split by where it stands: up to 3 clusters (the main army, reinforcements on
        their way, ...), biggest first. Units within 2 grid cells of a cluster's center join it."""
        left, out = list(army), []
        while left and len(out) < 3:
            cells = [self.army_tracker.cell(u["x"], u["y"]) for u in left]
            center = max(set(cells), key=cells.count)
            near = [u for u, c in zip(left, cells) if cell_dist(c, center) <= 2]
            out.append(near)
            left = [u for u in left if u not in near]
        return out

    def _army(self, obs: dict, mine: list[dict], done: list[dict]) -> bool:
        hi = self.hi
        if self._worker_defense(obs, mine):
            return True
        if self._scouting(obs, mine):
            return True
        if hi.frame < self.next_ask:
            return False
        army = [u for u in done if u["type"] in self.army_types]
        clusters = self._clusters(army)
        if not clusters:
            return False
        self.next_ask = hi.frame + ASK_EVERY // len(clusters)       # one cluster per question
        group = clusters[self.ask_turn % len(clusters)]
        self.ask_turn += 1
        grid, glob = self.army_tracker.inputs(obs, group)
        where, kind = self.army_model.predict(grid, glob)
        attack = int(kind[0].argmax()) == 1
        cx = sum(u["x"] for u in group) / len(group)
        cy = sum(u["y"] for u in group) / len(group)
        here = self.army_tracker.cell(cx, cy)
        # move or stay: by how much of the model's belief lies away from here (spread over many
        # cells, "elsewhere" can be likelier than "here" even when "here" is the likeliest cell)
        away = np.array([cell_dist(c, here) >= MOVE_CELLS for c in range(GRID * GRID)])
        p_away = float(where[0, away].sum())
        if p_away < MOVE_P:
            self.proposed.pop(here, None)
            return False                                          # stay
        best = int(np.where(away, where[0], -1).argmax())          # where, if moving
        proposed, self.proposed[here] = self.proposed.get(here), best
        if proposed is None or cell_dist(proposed, best) > 1:
            return False                                          # wait until it says so twice
        last = self.ordered.get(here)
        if last and cell_dist(last[0], best) <= 1 and last[1] == attack and hi.frame - last[2] < REORDER_AFTER:
            return False
        # never walk (rather than fight) into where enemy buildings were seen
        near_enemy = self.army_tracker.seen_buildings.reshape(GRID, GRID)[
            max(0, best // GRID - 2):best // GRID + 3, max(0, best % GRID - 2):best % GRID + 3].any()
        attack = attack or bool(near_enemy)
        # will it go well? the model's fight estimate for going there vs staying put
        go = self.army_model.fight(grid, glob, best, attack)
        stay = self.army_model.fight(grid, glob, here, False)
        if go < max(FIGHT_MIN, stay - FIGHT_MARGIN):
            if self.held.get(here, -1) != best:
                self._say(f"army ({len(group)} units) holds: going to {self.army_tracker.center(best)} "
                          f"looks like {go:+.0%} army share, staying {stay:+.0%}")
            self.held[here] = best
            return False
        self.held.pop(here, None)
        x, y = self.army_tracker.center(best)
        self.ordered[here] = (best, attack, hi.frame)
        self.task = Task("army_order", data={"tags": [u["tag"] for u in group], "x": x, "y": y,
                                             "attack": attack, "p": p_away, "fight": go, "done": [], "boxes": 0},
                         started=hi.frame)
        return True

    # --- worker defense (a reflex, scripted for now) -------------------------------------------

    def _worker_defense(self, obs: dict, mine: list[dict]) -> bool:
        """When enemy fighters at a base outnumber Gary's army there, pull a box of workers off the
        minerals to fight them (what players do against an early zergling attack); send them back
        to mining once the base has been calm for 5 s. True if Gary acted."""
        hi = self.hi
        enemy = [u for u in obs["units"] if u["owner"] not in (self.slot, 11) and supply_x2(u["type"]) > 0]
        for cc in (u for u in mine if u["type"] == T.CC and u["completed"]):
            near = [u for u in enemy if math.dist((u["x"], u["y"]), (cc["x"], cc["y"])) < THREAT_PX]
            if not near:
                continue
            ours = sum(supply_x2(u["type"]) for u in mine if u["type"] in self.army_types and u["completed"]
                       and math.dist((u["x"], u["y"]), (cc["x"], cc["y"])) < THREAT_PX + 4 * 32)
            self.calm_since = hi.frame
            theirs = sum(supply_x2(u["type"]) for u in near)
            alive = {u["tag"] for u in mine}
            self.pulled &= alive
            if theirs > ours + 2 and len(self.pulled) < 8 and hi.frame >= self.next_pull:
                self.next_pull = hi.frame + 24 * 3              # one pull at a time
                tx = sum(u["x"] for u in near) // len(near)
                ty = sum(u["y"] for u in near) // len(near)
                self.task = Task("pull", data={"cc": (cc["x"], cc["y"]), "to": (tx, ty)}, started=hi.frame)
                self._say(f"pulls workers: {len(near)} enemy units at the base, outnumbering the army there")
                return True
            return False
        if self.pulled and hi.frame - self.calm_since > CALM_FRAMES:
            self.task = Task("unpull", started=hi.frame)
            return True
        return False

    def _task_pull(self, obs: dict, mine: list[dict], t: Task) -> None:
        hi, d = self.hi, t.data
        if t.stage == "selected":
            workers = [u["tag"] for u in mine if u["tag"] in obs["selection"] and u["type"] == T.SCV]
            if workers:
                hi.minimap_command(C.ORDER_ATTACK_MOVE, *d["to"])
                self.pulled.update(workers)
            self.task = None
            return
        cx, cy = d["cc"]
        if not screen_of(obs, cx, cy):
            hi.camera_minimap(cx, cy)
            return
        miners = [u for u in mine if u["type"] == T.SCV and u["tag"] not in self.pulled
                  and math.dist((u["x"], u["y"]), (cx, cy)) < 8 * 32 and screen_of(obs, u["x"], u["y"])]
        if not miners:
            self.task = None
            return
        pts = [screen_of(obs, u["x"], u["y"]) for u in miners[:10]]
        hi.box(max(0, min(p[0] for p in pts) - 6), max(0, min(p[1] for p in pts) - 6),
               min(hi.p.viewport[0] - 1, max(p[0] for p in pts) + 6),
               min(hi.p.viewport[1] - 1, max(p[1] for p in pts) + 6))
        t.stage = "selected"

    def _task_unpull(self, obs: dict, mine: list[dict], t: Task) -> None:
        """Pulled workers back to the minerals of the nearest base."""
        hi = self.hi
        back = [u for u in mine if u["tag"] in self.pulled]
        if not back:
            self.pulled.clear()
            self.task = None
            return
        if t.stage == "selected":
            sel = [u for u in back if u["tag"] in obs["selection"]]
            if sel:
                w = sel[0]
                base = min(self.map.bases, key=lambda b: math.dist(b.center, (w["x"], w["y"])))
                fields = [m for m in base.minerals if screen_of(obs, *m)]
                if fields:
                    hi.right_click(*screen_of(obs, *fields[0]))
                else:
                    hi.minimap_right_click(*base.minerals[0])
                self.pulled -= {u["tag"] for u in sel}
            t.stage = "start"
            t.data["boxes"] = t.data.get("boxes", 0) + 1
            if t.data["boxes"] >= 3:
                self.pulled.clear()
                self.task = None
            return
        cx = sorted(u["x"] for u in back)[len(back) // 2]
        cy = sorted(u["y"] for u in back)[len(back) // 2]
        here = [u for u in back if screen_of(obs, u["x"], u["y"])]
        if not here:
            hi.camera_minimap(cx, cy)
            return
        pts = [screen_of(obs, u["x"], u["y"]) for u in here]
        hi.box(max(0, min(p[0] for p in pts) - 6), max(0, min(p[1] for p in pts) - 6),
               min(hi.p.viewport[0] - 1, max(p[0] for p in pts) + 6),
               min(hi.p.viewport[1] - 1, max(p[1] for p in pts) + 6))
        t.stage = "selected"

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
            if hi.frame >= SCOUT_AT and workers >= SCOUT_WORKERS:
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
        if t.kind in ("pull", "unpull"):
            if self.hi.frame - t.started > 24 * 8:
                self.task = None
                return
            return (self._task_pull if t.kind == "pull" else self._task_unpull)(obs, mine, t)
        if t.kind == "scout":
            if self.hi.frame - t.started > 24 * 10:
                self.task = None
                return
            return self._task_scout(obs, mine, t)
        if t.kind == "army_order":
            if self.hi.frame - t.started > 24 * 10:
                self.task = None
                return
            return self._task_army_order(obs, mine, t)
        return super()._run_task(obs, mine)

    def _task_army_order(self, obs: dict, mine: list[dict], t: Task) -> None:
        """Drag-box the cluster's units (12 at most per box, like the real game) and give each box
        the order on the minimap, until all of them have it."""
        hi, d = self.hi, t.data
        if t.stage == "selected":
            sel = [s for s in obs["selection"] if s in set(d["tags"])]
            if sel:
                if d["attack"]:
                    hi.minimap_command(C.ORDER_ATTACK_MOVE, d["x"], d["y"])
                else:
                    hi.minimap_right_click(d["x"], d["y"])
                d["done"] += sel
            t.stage = "start"
            return
        left = [u for u in mine if u["tag"] in set(d["tags"]) - set(d["done"])]
        if not left or d["boxes"] >= 4:
            if d["done"]:
                self._say(f"army ({len(d['done'])} units): {'attack' if d['attack'] else 'move'} "
                          f"to ({d['x']}, {d['y']}) ({d['p']:.0%} sure it should move; fight estimate {d['fight']:+.0%})")
            self.task = None
            return
        cx = sorted(u["x"] for u in left)[len(left) // 2]
        cy = sorted(u["y"] for u in left)[len(left) // 2]
        here = [u for u in left if screen_of(obs, u["x"], u["y"])]
        if not here:
            hi.camera_minimap(cx, cy)
            return
        pts = [screen_of(obs, u["x"], u["y"]) for u in here]
        hi.box(max(0, min(p[0] for p in pts) - 10), max(0, min(p[1] for p in pts) - 10),
               min(hi.p.viewport[0] - 1, max(p[0] for p in pts) + 10),
               min(hi.p.viewport[1] - 1, max(p[1] for p in pts) + 10))
        d["boxes"] += 1
        t.stage = "selected"

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

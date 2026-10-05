"""Gary v0 ("hello world"): mines with every worker and keeps making workers. Nothing else.

It plays through the human interface (gary/interface.py): it only sees its own units and what
they can see, a bit late; it has to click workers and mineral fields on its screen, with mouse
travel and scatter; and everything it does costs APM. It exists to prove that loop works end
to end and to show what the human limits look like in a replay.

    python -m gary.bots.hello --map tests/fixtures/replays/stardata_tvz_standard_ozp3w.rep --races T Z --minutes 4
"""

from __future__ import annotations

import argparse
import math

from gary import commands as C
from gary.env import Game
from gary.interface import PROFILES, HumanInterface, screen_of

WORKERS = {C.SCV, C.DRONE, C.PROBE}
MAIN_BUILDINGS = {C.COMMAND_CENTER: C.SCV, C.NEXUS: C.PROBE, C.HATCHERY: C.DRONE}
BASE_HOTKEY = 4


class HelloGary:
    def __init__(self, hi: HumanInterface):
        self.hi = hi
        self.sent_to_mine: set[int] = set()
        self.base_hotkey_set = False

    def act(self) -> None:
        hi = self.hi
        if hi.pending:          # one thing at a time: wait for the last click to land
            return
        obs = hi.observe()
        me = obs["me"]
        mine = [u for u in obs["units"] if u["owner"] == hi.slot and u["completed"]]
        base = next((u for u in mine if u["type"] in MAIN_BUILDINGS), None)
        if not base:
            return
        minerals = [u for u in obs["units"] if u["type"] in C.MINERAL_FIELDS and screen_of(obs, u["x"], u["y"])]

        # 1. put the main building on a hotkey once, so training doesn't need the mouse
        if not self.base_hotkey_set:
            if obs["selection"] != [base["tag"]]:
                p = screen_of(obs, base["x"], base["y"])
                if p:
                    hi.click(*p)
                return
            hi.hotkey_set(BASE_HOTKEY)
            self.base_hotkey_set = True
            return

        # 2. a new worker: click it, then right-click the closest visible mineral field
        idle = [w for w in mine if w["type"] in WORKERS and w["tag"] not in self.sent_to_mine]
        if idle and minerals:
            w = idle[0]
            if obs["selection"] != [w["tag"]]:
                p = screen_of(obs, w["x"], w["y"])
                if p:
                    hi.click(*p)
                else:
                    self.sent_to_mine.add(w["tag"])   # off screen: v0 doesn't chase it
                return
            field = min(minerals, key=lambda m: math.dist((m["x"], m["y"]), (base["x"], base["y"])))
            p = screen_of(obs, field["x"], field["y"])
            if hi.right_click(*p).accepted:
                self.sent_to_mine.add(w["tag"])
            return

        # 3. one more worker whenever affordable
        if me["minerals"] >= 50 and me["supply_used"] < me["supply_max"]:
            worker = MAIN_BUILDINGS[base["type"]]
            if worker == C.DRONE:
                larva = [u for u in obs["units"] if u["owner"] == hi.slot and u["type"] == C.LARVA]
                if larva:
                    if obs["selection"] != [larva[0]["tag"]]:
                        p = screen_of(obs, larva[0]["x"], larva[0]["y"])
                        if p:
                            hi.click(*p)
                        return
                    hi.morph(C.DRONE)
            elif obs["selection"] != [base["tag"]]:
                hi.hotkey_recall(BASE_HOTKEY)
            else:
                hi.train(worker)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", required=True, help="a .scm/.scx map, or a pre-1.18 replay (its embedded map)")
    ap.add_argument("--races", nargs="+", default=["T", "Z"], help="one race per player, e.g. T Z")
    ap.add_argument("--seed", type=int, help="random start locations; default: current time")
    ap.add_argument("--minutes", type=float, default=4)
    ap.add_argument("--profile", default="pro", choices=sorted(PROFILES))
    ap.add_argument("--save", default="gary_hello.rep", help="where to save the resulting replay")
    args = ap.parse_args()

    names = [f"Gary v0 ({r.upper()})" for r in args.races]
    with Game.new(args.map, args.races, names, seed=args.seed) as game:
        players = game.observe()["players"]
        his = [HumanInterface(game, p["slot"], PROFILES[args.profile], seed=p["slot"]) for p in players]
        bots = [HelloGary(hi) for hi in his]
        end = int(args.minutes * 60 * 24)
        frame = 0
        while frame < end:
            for bot in bots:
                bot.act()
            # all interfaces share one game: advance it once, landing every player's clicks
            step_together(his, 2)
            frame = his[0].frame
            if frame % (24 * 60) < 2:
                obs = game.observe()
                summary = []
                for hi in his:
                    me = next(p for p in obs["players"] if p["slot"] == hi.slot)
                    workers = sum(1 for u in obs["units"] if u["owner"] == hi.slot and u["type"] in WORKERS)
                    summary.append(f"slot {hi.slot}: {workers} workers, {me['minerals']} min, "
                                   f"{hi.stats['actions']} actions ({hi.stats['rejected_by_interface']} refused "
                                   f"by the interface, {hi.stats['rejected_by_game']} by the game)")
                print(f"{frame // 24 // 60}:00  " + " | ".join(summary), flush=True)
        game.save_replay(args.save)
        print(f"saved {args.save}")


def step_together(his: list[HumanInterface], frames: int) -> None:
    """Advance a game shared by several interfaces, one frame at a time."""
    for _ in range(frames):
        for i, hi in enumerate(his):
            hi.step(1, advance_game=(i == 0))


if __name__ == "__main__":
    main()

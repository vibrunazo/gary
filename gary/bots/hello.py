"""Gary v0 ("hello world"): mines with every worker and keeps making workers. Nothing else.

It exists to prove the loop works end to end: observe the game, decide, send commands, step,
save a replay you can watch. It ignores fog of war and human limits (no human interface yet).

    python -m gary.bots.hello --replay-map tests/fixtures/replays/stardata_tvz_standard_ozp3w.rep --minutes 4
"""

from __future__ import annotations

import argparse
import math

from gary import commands as C
from gary.env import Game

WORKERS = {C.SCV, C.DRONE, C.PROBE}
MAIN_BUILDINGS = {C.COMMAND_CENTER: C.SCV, C.NEXUS: C.PROBE, C.HATCHERY: C.DRONE}


class HelloGary:
    def __init__(self, slot: int):
        self.slot = slot
        self.sent_to_mine: set[int] = set()

    def act(self, game: Game, obs: dict) -> None:
        me = next(p for p in obs["players"] if p["slot"] == self.slot)
        mine = [u for u in obs["units"] if u["owner"] == self.slot and u["completed"]]
        minerals = [u for u in obs["units"] if u["type"] in C.MINERAL_FIELDS]
        base = next((u for u in mine if u["type"] in MAIN_BUILDINGS), None)
        if not base:
            return
        # every new worker goes to the mineral field closest to the main building
        for w in (u for u in mine if u["type"] in WORKERS and u["tag"] not in self.sent_to_mine):
            field = min(minerals, key=lambda m: math.dist((m["x"], m["y"]), (base["x"], base["y"])))
            game.act(self.slot, C.select([w["tag"]]))
            game.act(self.slot, C.right_click(field["x"], field["y"], field["tag"], field["type"]))
            self.sent_to_mine.add(w["tag"])
        # one more worker whenever affordable
        if me["minerals"] >= 50 and me["supply_used"] < me["supply_max"]:
            worker = MAIN_BUILDINGS[base["type"]]
            if worker == C.DRONE:
                larva = [u for u in obs["units"] if u["owner"] == self.slot and u["type"] == C.LARVA]
                if larva:
                    game.act(self.slot, C.select([larva[0]["tag"]]))
                    game.act(self.slot, C.morph(C.DRONE))
            else:
                game.act(self.slot, C.select([base["tag"]]))
                game.act(self.slot, C.train(worker))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--replay-map", required=True, help="pre-1.18 replay whose map and players to use")
    ap.add_argument("--minutes", type=float, default=4)
    ap.add_argument("--save", default="gary_hello.rep", help="where to save the resulting replay")
    args = ap.parse_args()

    with Game.from_replay_map(args.replay_map) as game:
        obs = game.observe()
        bots = [HelloGary(p["slot"]) for p in obs["players"]]
        end = int(args.minutes * 60 * 24)
        while obs["frame"] < end:
            for bot in bots:
                bot.act(game, obs)
            game.step(8)  # decide three times per game second
            obs = game.observe()
            if obs["frame"] % (24 * 60) < 8:
                summary = []
                for p in obs["players"]:
                    workers = sum(1 for u in obs["units"] if u["owner"] == p["slot"] and u["type"] in WORKERS)
                    summary.append(f"slot {p['slot']}: {workers} workers, {p['minerals']} minerals, "
                                   f"supply {p['supply_used']:.0f}/{p['supply_max']:.0f}")
                print(f"{obs['frame'] // 24 // 60}:00  " + " | ".join(summary), flush=True)
        game.save_replay(args.save)
        print(f"saved {args.save}")


if __name__ == "__main__":
    main()

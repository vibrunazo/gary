"""Gary v0.5, Terran: v0.4 with the fight command model (#2).

v0.4's fight model says what each unit should do, and Gary regroups the units by order. v0.5's
command model (gary/policy/fight_cmd.py) says what a player does: one command at a time, to a
selection. Every half second in a fight it draws the next command: its type, which of Gary's
units it goes to (up to 12), and its target unit or point, or "nothing". Gary carries it out with
human hands as before (camera on the fight, drag box, right-click / A-click / hotkey), leaving out
units already doing it.

    python -m gary.bots.terran_v05 --map path/to/map.scx --minutes 12 --style 1
    python -m gary.bots.terran_v05 --live --style 1
"""

from __future__ import annotations

import argparse
from pathlib import Path

from gary.bots import terran_v01 as v01
from gary.bots.terran_v01 import Task
from gary.bots.terran_v02 import latest_model
from gary.bots.terran_v03 import latest_army_model
from gary.bots.terran_v04 import RESOURCES, TerranGaryV4
from gary.env import LIVE_COMMAND_DELAY
from gary.policy.army import ArmyModel
from gary.policy.fight import ACTIONS
from gary.policy.fight_cmd import MOVES, POINTER, CommandModel
from gary.policy.macro import MacroModel

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def latest_command_model(matchup: str = "TvZ", race: str = "T") -> Path:
    found = sorted((REPO_ROOT / "runs" / "fight_cmd").glob(f"{matchup}_{race}_*/model.pt"))
    if not found:
        raise SystemExit(f"no trained command model in runs/fight_cmd (python -m train.fight_cmd --race {race})")
    return found[-1]


class TerranGaryV5(TerranGaryV4):
    version = "v0.5"

    def _fight(self, obs: dict, mine: list[dict]) -> bool:
        snap = self._snapshot(obs)
        if snap is None:
            return False
        rows, tags, center, by_tag = snap
        cmd = self.fight_model.decide(rows, obs["frame"] * 42 / 1000, self.rng)
        if cmd is None:
            return False
        a = ACTIONS[cmd["type"]]
        if a == "other":
            return False
        if a in POINTER and cmd["target"] < 0:
            return False
        if cmd["type"] in POINTER:
            t = tags[cmd["target"]]
            if a == "gather" and rows[cmd["target"]][0] not in RESOURCES:
                return False                     # gathering means minerals, a geyser or a refinery
            key = (a, t)
        elif cmd["type"] in MOVES:
            dx, dy = cmd["dest"]
            dx, dy = (-dx if self.flip[0] else dx), (-dy if self.flip[1] else dy)
            key = (a, int(center[0] + dx), int(center[1] + dy))
        else:
            key = (a,)
        chosen = [tags[i] for i in cmd["select"]]
        chosen = [t for t in chosen if not self._already(a, by_tag[t]) and not self._just_told(t, key)
                  and not (len(key) == 2 and by_tag[t].get("order_target") == key[1])]
        if not chosen:
            return False
        for t in chosen:
            self.told[t] = (key, self.hi.frame)
        self.task = Task("fight_cmd", data={"key": key, "tags": chosen, "center": center}, started=self.hi.frame)
        return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", help="a .scm/.scx map (or a pre-1.18 replay) for headless play")
    ap.add_argument("--minutes", type=float, default=12)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--save", default="gary_v05.rep")
    ap.add_argument("--command-delay", type=int, default=LIVE_COMMAND_DELAY)
    ap.add_argument("--style", type=int, help="build-style cluster to steer the macro toward")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--live", action="store_true", help="play in a live SC:R client via the bridge")
    ap.add_argument("--pipe", default=r"\\.\pipe\gary_scr")
    ap.add_argument("--profile", default="b_rank", choices=sorted(v01.PROFILES))
    ap.add_argument("--pov", help="where to save the point-of-view log (live)")
    args = ap.parse_args()
    macro, army = MacroModel.load(latest_model()), ArmyModel.load(latest_army_model())
    command = CommandModel.load(latest_command_model())
    make = lambda hi, mapinfo: TerranGaryV5(hi, mapinfo, macro, army, command, args.style, verbose=not args.quiet)
    if args.live:
        v01.play_live(args.pipe, args.minutes, args.profile, args.pov or "gary_v05_live.pov.jsonl", make_bot=make)
    else:
        if not args.map:
            ap.error("--map is required unless --live")
        v01.play(args.map, args.minutes, args.seed, args.save, command_delay=args.command_delay,
                 make_bot=make, name="Gary v0.5 (T)")


if __name__ == "__main__":
    main()

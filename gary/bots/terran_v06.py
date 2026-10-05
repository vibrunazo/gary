"""Gary v0.6, Terran: v0.5 with a fight command model that remembers its own recent commands (#2).

v0.5 decides each fight command from the current snapshot alone and switches plans every second
or two. v0.6's command model also sees what Gary's hands ordered in the last 8 seconds (which
units, what, where: gary/policy/fight_memory.py, from the human interface's command log), as the
pros' own preceding commands in training, so it can hold a plan the way a player does.

    python -m gary.bots.terran_v06 --map path/to/map.scx --minutes 12 --style 1
    python -m gary.bots.terran_v06 --live --style 1
"""

from __future__ import annotations

import argparse

from gary.bots import terran_v01 as v01
from gary.bots.terran_v02 import latest_model
from gary.bots.terran_v03 import latest_army_model
from gary.bots.terran_v05 import TerranGaryV5, latest_command_model
from gary.env import LIVE_COMMAND_DELAY
from gary.policy.army import ArmyModel
from gary.policy.fight_cmd import CommandModel
from gary.policy.macro import MacroModel


class TerranGaryV6(TerranGaryV5):
    version = "v0.6"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", help="a .scm/.scx map (or a pre-1.18 replay) for headless play")
    ap.add_argument("--minutes", type=float, default=12)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--save", default="gary_v06.rep")
    ap.add_argument("--command-delay", type=int, default=LIVE_COMMAND_DELAY)
    ap.add_argument("--style", type=int, help="build-style cluster to steer the macro toward")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--live", action="store_true", help="play in a live SC:R client via the bridge")
    ap.add_argument("--pipe", default=r"\\.\pipe\gary_scr")
    ap.add_argument("--profile", default="b_rank", choices=sorted(v01.PROFILES))
    ap.add_argument("--pov", help="where to save the point-of-view log (live)")
    args = ap.parse_args()
    macro, army = MacroModel.load(latest_model()), ArmyModel.load(latest_army_model())
    command = CommandModel.load(latest_command_model(memory=True))
    make = lambda hi, mapinfo: TerranGaryV6(hi, mapinfo, macro, army, command, args.style, verbose=not args.quiet)
    if args.live:
        v01.play_live(args.pipe, args.minutes, args.profile, args.pov or "gary_v06_live.pov.jsonl", make_bot=make)
    else:
        if not args.map:
            ap.error("--map is required unless --live")
        v01.play(args.map, args.minutes, args.seed, args.save, command_delay=args.command_delay,
                 make_bot=make, name="Gary v0.6 (T)")


if __name__ == "__main__":
    main()

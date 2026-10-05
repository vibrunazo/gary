"""Gary v0.7, Terran: v0.6 with workers pulled by rule (#2).

On the home-defense scenarios, v0.3's simple worker pull did better than every learned fight
model, which pulled SCVs more often and fought with them badly. v0.7 keeps v0.6's command model
for everything else but gives the workers to v0.3's rule: when enemy fighters at a base outnumber
Gary's army there, about two SCVs per attacker attack-move to them, and go back to mining after
5 s of calm. The rule runs first in a fight, before the command model, and the model no longer
gives SCVs orders.

    python -m gary.bots.terran_v07 --map path/to/map.scx --minutes 12 --style 1
    python -m gary.bots.terran_v07 --live --style 1
"""

from __future__ import annotations

import argparse

from gary import terran as T
from gary.bots import terran_v01 as v01
from gary.bots.terran_v02 import latest_model
from gary.bots.terran_v03 import TerranGaryV3, latest_army_model
from gary.bots.terran_v05 import latest_command_model
from gary.bots.terran_v06 import TerranGaryV6
from gary.env import LIVE_COMMAND_DELAY
from gary.policy.army import ArmyModel
from gary.policy.fight_cmd import CommandModel
from gary.policy.macro import MacroModel


class TerranGaryV7(TerranGaryV6):
    version = "v0.7"

    def _pull_workers(self, obs: dict, mine: list[dict]) -> bool:
        return TerranGaryV3._worker_defense(self, obs, mine)

    def _may_command(self, unit: dict) -> bool:
        return unit["type"] != T.SCV


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", help="a .scm/.scx map (or a pre-1.18 replay) for headless play")
    ap.add_argument("--minutes", type=float, default=12)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--save", default="gary_v07.rep")
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
    make = lambda hi, mapinfo: TerranGaryV7(hi, mapinfo, macro, army, command, args.style, verbose=not args.quiet)
    if args.live:
        v01.play_live(args.pipe, args.minutes, args.profile, args.pov or "gary_v07_live.pov.jsonl", make_bot=make)
    else:
        if not args.map:
            ap.error("--map is required unless --live")
        v01.play(args.map, args.minutes, args.seed, args.save, command_delay=args.command_delay,
                 make_bot=make, name="Gary v0.7 (T)")


if __name__ == "__main__":
    main()

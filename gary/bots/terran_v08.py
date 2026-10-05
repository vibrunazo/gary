"""Gary v0.8, Terran: v0.7 with a fight model trained by reinforcement learning, and no guard rail (#2).

v0.7's command model learned from pro replays (imitation) made moves that took marines out of
fights, so v0.7 didn't carry out its plain moves and stops. v0.8's command model starts from the
same imitation model and was then trained by reinforcement learning (train/fight_cmd_rl.py) on
real home defenses from training games (pro positions, the pro Zerg's attack; Gary playing as
v0.7 otherwise) and on home-defense drills, keeping close to the imitation model; validation
home defenses picked the checkpoint. With it, Gary carries out every command type again.
Everything else is v0.7: workers pulled by rule, bunker loads, production during fights.

    python -m gary.bots.terran_v08 --map path/to/map.scx --minutes 12 --style 1
    python -m gary.bots.terran_v08 --live --style 1
"""

from __future__ import annotations

import argparse
from pathlib import Path

from gary.bots import terran_v01 as v01
from gary.bots.terran_v02 import latest_model
from gary.bots.terran_v03 import latest_army_model
from gary.bots.terran_v07 import TerranGaryV7
from gary.env import LIVE_COMMAND_DELAY
from gary.policy.army import ArmyModel
from gary.policy.fight_cmd import CommandModel
from gary.policy.macro import MacroModel

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def latest_rl_fight_model() -> Path:
    """The newest fight command model trained by reinforcement learning (runs/fight_cmd_rl)."""
    found = sorted((REPO_ROOT / "runs" / "fight_cmd_rl").glob("*/model.pt"), key=lambda p: p.stat().st_mtime)
    if not found:
        raise SystemExit("no RL-trained fight model in runs/fight_cmd_rl (python -m train.fight_cmd_rl)")
    return found[-1]


class TerranGaryV8(TerranGaryV7):
    version = "v0.8"

    def _may_issue(self, action: str) -> bool:
        return True                              # no guard rail: RL taught the model its moves


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", help="a .scm/.scx map (or a pre-1.18 replay) for headless play")
    ap.add_argument("--minutes", type=float, default=12)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--save", default="gary_v08.rep")
    ap.add_argument("--command-delay", type=int, default=LIVE_COMMAND_DELAY)
    ap.add_argument("--style", type=int, help="build-style cluster to steer the macro toward")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--live", action="store_true", help="play in a live SC:R client via the bridge")
    ap.add_argument("--pipe", default=r"\\.\pipe\gary_scr")
    ap.add_argument("--profile", default="pro", choices=sorted(v01.PROFILES))
    ap.add_argument("--pov", help="where to save the point-of-view log (live)")
    ap.add_argument("--fight-model", help="fight command model (default: the newest RL-trained one)")
    args = ap.parse_args()
    macro, army = MacroModel.load(latest_model()), ArmyModel.load(latest_army_model())
    command = CommandModel.load(args.fight_model or latest_rl_fight_model())
    make = lambda hi, mapinfo: TerranGaryV8(hi, mapinfo, macro, army, command, args.style, verbose=not args.quiet)
    if args.live:
        v01.play_live(args.pipe, args.minutes, args.profile, args.pov or "gary_v08_live.pov.jsonl", make_bot=make)
    else:
        if not args.map:
            ap.error("--map is required unless --live")
        v01.play(args.map, args.minutes, args.seed, args.save, command_delay=args.command_delay,
                 make_bot=make, name="Gary v0.8 (T)")


if __name__ == "__main__":
    main()

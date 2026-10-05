"""Micro drills: small fights made up on real maps (#2; ARCHITECTURE.md §7.8, T0 micro curriculum).

A drill is a real map with a few units added for each side as preplaced units (a "use map
settings" game, as players build micro maps in the map editor), so saved drill replays play back
like any game. The Terran side is played by Gary's fight layer alone (no base, no macro) through
the human interface; the Zerg side by a script (zerglings attack-move at the Terran units). Drills
are drawn at random from a family (unit counts, place on the map, approach direction), so a model
can be trained on many variations of one problem and judged on real scenarios (eval/scenarios.py).

Families:
  mm_vs_lings   4-12 marines and 0-3 medics against 8-24 zerglings, on open ground

    python -m gary.drills --family mm_vs_lings --n 20 --controllers gary amove nothing
    python -m gary.drills --family mm_vs_lings --n 1 --save drill.rep     # a replay to watch
"""

from __future__ import annotations

import argparse
import json
import math
import random
import struct
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from gary import commands as C
from gary import terran as T
from gary.env import LIVE_COMMAND_DELAY, Game, map_chk

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAP = REPO_ROOT / "tests" / "fixtures" / "replays" / "stardata_tvz_standard_ozp3w.rep"
TERRAN_SLOT, ZERG_SLOT = 0, 1
MEDIC, ZERGLING = 34, 37
VALUE = {T.MARINE: 50, MEDIC: 75, ZERGLING: 25, T.SCV: 50}
SPACING = 20                     # pixels between units in a starting clump
ZERG_EVERY = 24                  # the zerg script re-targets every second


@dataclass
class Drill:
    family: str
    seed: int
    terran: list[tuple[int, int, int]]          # (unit type, x, y)
    zerg: list[tuple[int, int, int]]
    seconds: float = 30.0
    map_path: str = str(DEFAULT_MAP)
    info: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return f"{self.family}_{self.seed}"


# --- making drills ----------------------------------------------------------------------------

_chk: dict[str, bytes] = {}
_probe: dict[str, Game] = {}


def _map(path: str) -> tuple[bytes, Game]:
    """The map's scenario data and a game on it to ask about terrain (cached per process)."""
    if path not in _chk:
        _chk[path] = map_chk(path)
        _probe[path] = Game.new(path, ["T", "Z"], seed=0)
    return _chk[path], _probe[path]


def _open(probe: Game, x: int, y: int, r: int) -> bool:
    """Ground units can stand everywhere within r pixels of (x, y)."""
    return all(probe.walkable(int(x + dx), int(y + dy))
               for dx in range(-r, r + 1, 16) for dy in range(-r, r + 1, 16) if dx * dx + dy * dy <= r * r)


def _clump(probe: Game, x: int, y: int, types: list[int]) -> list[tuple[int, int, int]]:
    """Units in a square clump around (x, y), each on walkable ground."""
    side = max(1, math.ceil(math.sqrt(len(types))))
    out = []
    for i, t in enumerate(types):
        px = x + (i % side - (side - 1) / 2) * SPACING
        py = y + (i // side - (side - 1) / 2) * SPACING
        if probe.walkable(int(px), int(py)):
            out.append((t, int(px), int(py)))
    return out


def make_drill(family: str, seed: int, map_path: str = str(DEFAULT_MAP)) -> Drill:
    rng = random.Random(seed)
    _, probe = _map(map_path)
    w, h = probe.observe()["map"]["w"], probe.observe()["map"]["h"]
    if family != "mm_vs_lings":
        raise ValueError(f"unknown drill family {family}")
    marines, medics, lings = rng.randint(4, 12), rng.randint(0, 3), rng.randint(8, 24)
    for _ in range(500):                         # open ground for both sides
        x, y = rng.randint(256, w - 256), rng.randint(256, h - 256)
        a = rng.uniform(0, 2 * math.pi)
        d = rng.randint(320, 480)
        zx, zy = int(x + d * math.cos(a)), int(y + d * math.sin(a))
        if _open(probe, x, y, 96) and 0 < zx < w and 0 < zy < h and _open(probe, zx, zy, 96):
            break
    else:
        raise RuntimeError("no open ground found")
    terran = _clump(probe, x, y, [T.MARINE] * marines + [MEDIC] * medics)
    zerg = _clump(probe, zx, zy, [ZERGLING] * lings)
    return Drill(family, seed, terran, zerg, info={"marines": marines, "medics": medics, "lings": lings})


def drill_chk(drill: Drill) -> bytes:
    """The map with the drill's units as preplaced units: a UNIT section put in front of the map's
    own (every UNIT section is read, in order, and junk at the end of protected maps stays out of
    the way)."""
    base, _ = _map(drill.map_path)
    entries = b""
    for serial, (t, x, y, owner) in enumerate([(*u, TERRAN_SLOT) for u in drill.terran] +
                                              [(*u, ZERG_SLOT) for u in drill.zerg]):
        # serial, x, y, type, relation, valid flags, valid properties, owner, hp %, shields %,
        # energy %, resources, units in hangar, state flags, unused, related unit
        entries += struct.pack("<IHHHHHHBBBBIHHII", 9000 + serial, x, y, t, 0, 0, 0, owner, 100, 100, 100, 0, 0, 0, 0, 0)
    return b"UNIT" + struct.pack("<I", len(entries)) + entries + base


# --- playing drills ---------------------------------------------------------------------------

def zerg_script(game: Game, obs: dict) -> None:
    """Every zergling attack-moves at the nearest Terran unit it can... in groups of 12."""
    lings = [u for u in obs["units"] if u["owner"] == ZERG_SLOT]
    terran = [u for u in obs["units"] if u["owner"] == TERRAN_SLOT]
    if not lings or not terran:
        return
    cx = sum(u["x"] for u in lings) / len(lings)
    cy = sum(u["y"] for u in lings) / len(lings)
    t = min(terran, key=lambda u: (u["x"] - cx) ** 2 + (u["y"] - cy) ** 2)
    for i in range(0, len(lings), 12):
        game.act(ZERG_SLOT, C.select([u["tag"] for u in lings[i:i + 12]]))
        game.act(ZERG_SLOT, C.targeted_order(C.ORDER_ATTACK_MOVE, t["x"], t["y"]))


def drill_gary(game: Game, drill: Drill, fight_model, seed: int, verbose: bool = False):
    """Gary's fight layer alone, with human hands and the camera on its units."""
    from gary.bots.drill_gary import DrillGary
    from gary.bots.terran_v01 import PROFILES
    from gary.interface import HumanInterface
    hi = HumanInterface(game, TERRAN_SLOT, PROFILES["pro"], seed=1)
    x = sum(u[1] for u in drill.terran) / len(drill.terran)
    y = sum(u[2] for u in drill.terran) / len(drill.terran)
    vw, vh = hi.p.viewport
    hi.camera = (max(0, int(x - vw / 2)), max(0, int(y - vh / 2)))
    w, h = hi.map_size
    bot = DrillGary(hi, fight_model, flip=(x > w / 2, y > h / 2), seed=seed, verbose=verbose)
    return bot, hi


def run_drill(drill: Drill, controller: str = "gary", fight_path: str | None = None, sample_seed: int = 0,
              save: str | None = None, verbose: bool = False, log: bool = False) -> dict:
    """Play a drill: Terran by "gary" (the fight layer), "amove" (one attack-move at the zerglings,
    then nothing: the baseline a player beats with micro) or "nothing" (units only fight back).
    Returns value lost by each side and the units left."""
    row = {"drill": drill.name, "controller": controller}
    game = Game.custom(drill_chk(drill), drill.name, [TERRAN_SLOT, ZERG_SLOT], ["T", "Z"],
                       ["Gary", "Zerglings"], seed=drill.seed, command_delay=LIVE_COMMAND_DELAY)
    try:
        bot = hi = None
        if controller == "gary":
            bot, hi = drill_gary(game, drill, _fight_model(fight_path), sample_seed, verbose)
            if log:
                bot.rl_log = []
        obs = game.observe()
        start = {u["tag"]: (u["owner"], u["type"]) for u in obs["units"] if u["owner"] in (TERRAN_SLOT, ZERG_SLOT)}
        if controller == "amove":
            zerg = [u for u in obs["units"] if u["owner"] == ZERG_SLOT]
            mine = [u["tag"] for u in obs["units"] if u["owner"] == TERRAN_SLOT]
            zx, zy = sum(u["x"] for u in zerg) / len(zerg), sum(u["y"] for u in zerg) / len(zerg)
            for i in range(0, len(mine), 12):
                game.act(TERRAN_SLOT, C.select(mine[i:i + 12]))
                game.act(TERRAN_SLOT, C.targeted_order(C.ORDER_ATTACK_MOVE, int(zx), int(zy)))
        end = game.frame + int(drill.seconds * 1000 / 42)
        deaths, alive = [], set(start)
        while game.frame < end:
            if game.frame % ZERG_EVERY == 0:
                zerg_script(game, game.observe())
            if bot:
                bot.act()
                hi.step(2)
            else:
                game.step(2)
            if game.frame % 12 < 2:              # when units die (credit for decisions: RL)
                for tag in [t for t in alive if game.unit_type_of(t) == -1]:
                    alive.discard(tag)
                    owner, kind = start[tag]
                    deaths.append((game.frame, VALUE.get(kind, 50) * (1 if owner == ZERG_SLOT else -1)))
        lost = {TERRAN_SLOT: 0, ZERG_SLOT: 0}
        left = {TERRAN_SLOT: 0, ZERG_SLOT: 0}
        for tag, (owner, kind) in start.items():
            if game.unit_type_of(tag) == -1:
                lost[owner] += VALUE.get(kind, 50)
            else:
                left[owner] += 1
        row.update(T_lost=lost[TERRAN_SLOT], Z_lost=lost[ZERG_SLOT], T_left=left[TERRAN_SLOT], Z_left=left[ZERG_SLOT],
                   net=lost[ZERG_SLOT] - lost[TERRAN_SLOT], deaths=deaths, **drill.info)
        if bot and log:
            row["log"] = bot.rl_log
        if hi:
            row["acts"] = sum(1 for e in hi.pov if "act" in e)
        if save:
            game.save_replay(save)
            if hi:
                hi.save_pov(save[:-4] + ".pov.jsonl")
    except Exception as e:  # noqa: BLE001 - one broken drill must not stop a batch
        row["error"] = f"{type(e).__name__}: {e}"[:200]
    finally:
        game.close()
    return row


_models: dict = {}


def _fight_model(path: str | None):
    if path not in _models:
        import torch
        torch.set_num_threads(1)
        from gary.bots.terran_v05 import latest_command_model
        from gary.policy.fight_cmd import load_fight_policy
        _models.clear()
        _models[path] = load_fight_policy(path or latest_command_model(memory=True))
    return _models[path]


def _job(args: tuple) -> dict:
    family, seed, controller, fight_path, sample_seed = args
    return run_drill(make_drill(family, seed), controller, fight_path, sample_seed)


def main() -> None:
    import os
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", default="mm_vs_lings")
    ap.add_argument("--n", type=int, default=20, help="drills (seeds 0..n-1)")
    ap.add_argument("--first-seed", type=int, default=0)
    ap.add_argument("--controllers", nargs="+", default=["gary", "amove", "nothing"])
    ap.add_argument("--fight-model", help="Gary's fight model (default: the latest command model with memory)")
    ap.add_argument("--parallel", type=int, default=max(1, (os.cpu_count() or 6) * 2 // 3))
    ap.add_argument("--save", help="with --n 1: save the drill's replay (and Gary's POV) here")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    seeds = range(args.first_seed, args.first_seed + args.n)
    if args.save:
        d = make_drill(args.family, seeds[0])
        print(json.dumps(d.info), len(d.terran), "terran,", len(d.zerg), "zerg")
        for c in args.controllers:
            path = args.save if len(args.controllers) == 1 else args.save.replace(".rep", f"_{c}.rep")
            r = run_drill(d, c, args.fight_model, save=path, verbose=args.verbose)
            print(c, {k: v for k, v in r.items() if k != "log"}, "->", path)
        return
    jobs = [(args.family, s, c, args.fight_model, 0) for s in seeds for c in args.controllers]
    with ProcessPoolExecutor(args.parallel) as pool:
        rows = list(pool.map(_job, jobs, chunksize=len(args.controllers)))
    print(f"{args.n} {args.family} drills, {make_drill(args.family, seeds[0]).seconds:g} s each; mean per drill:")
    for c in args.controllers:
        rs = [r for r in rows if r["controller"] == c and "error" not in r]
        errs = [r["error"] for r in rows if r["controller"] == c and "error" in r]
        if rs:
            print(f"  {c:8s} net {np.mean([r['net'] for r in rs]):6.0f}  terran lost {np.mean([r['T_lost'] for r in rs]):5.0f}  "
                  f"zerg lost {np.mean([r['Z_lost'] for r in rs]):5.0f}  terran units left {np.mean([r['T_left'] for r in rs]):4.1f}"
                  + (f"  ({len(errs)} errors: {errs[0]})" if errs else ""))
        else:
            print(f"  {c:8s} all {len(errs)} failed: {errs[:1]}")


if __name__ == "__main__":
    main()

"""Scenario tests from real pro positions (#2, step 4).

A held-out pro TvZ replay plays in OpenBW up to an early skirmish at the Terran's buildings
(zerg fighters around them before 6:00). There the Terran is handed to a controller while the Zerg
keeps replaying what the pro Zerg did, and the next seconds are scored by the value (minerals +
gas) each side loses. Controllers:

  pro       the Terran pro's own commands keep playing (what really happened)
  gary      Gary (v0.4 by default) takes over the Terran with human hands
  nothing   nobody touches the Terran: units keep their last orders (the floor)

    python -m eval.scenarios --pick 200 --screen      # find scenarios in held-out games
    python -m eval.scenarios --run 30 --parallel 8    # score them under each controller

--screen plays each picked scenario under the pro and under nothing and keeps the decisive
ones: where the pro's control was worth at least --min-gap (net value: zerg lost - terran lost)
over leaving the units alone. Elsewhere the zerglings weren't a threat and every controller ties.

The Zerg replays commands, not intentions: once the Terran plays differently, a zerg command may
target a unit that isn't there any more, and units the Zerg makes after the takeover can get
different unit IDs than in the real game, so the Zerg's later commands to them may miss. Keep the
window short (the default is 45 s).
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "ingest"))

from inventory import data_root  # noqa: E402

from gary import terran as T  # noqa: E402
from gary.policy.army import is_building  # noqa: E402

BEFORE_S = 360                  # skirmishes before 6:00
LEAD_FRAMES = 24                # take over one second before the skirmish snapshot
ZERG_FIGHTERS = {37, 38, 39, 43, 47, 50, 103}   # zergling, hydra, ultra, muta, scourge, infested, lurker
MIN_FIGHTERS = 3
ZERG_COST = {37: (25, 0), 38: (75, 25), 39: (200, 200), 41: (50, 0), 42: (100, 0), 43: (100, 100),
             45: (100, 100), 46: (50, 150), 47: (12, 38), 103: (125, 125),
             131: (300, 0), 142: (200, 0), 149: (75, 0), 143: (125, 0), 146: (175, 0), 141: (200, 150),
             132: (450, 100), 135: (150, 0), 136: (150, 100), 137: (100, 100), 138: (200, 150)}
CONTROLLERS = ["pro", "gary", "nothing"]


def scenarios_path(split: str = "test") -> Path:
    """test: from games held out of training (for scoring); train: from training games (for
    reinforcement learning, train/fight_rl.py)."""
    return data_root() / "interim" / "scenarios" / ("tvz_early.jsonl" if split == "test" else "tvz_early_train.jsonl")


def value(unit_type: int) -> int:
    m, g = T.COST.get(unit_type) or ZERG_COST.get(unit_type) or (0, 0)
    return m + g


# --- picking -----------------------------------------------------------------------------------

def pick(n: int, split: str = "test") -> list[dict]:
    """The first early skirmish at the Terran's buildings in each TvZ game of the split (held-out
    games for "test"), from the fight dataset (ingest/fight_dataset.py)."""
    from train.macro import is_test
    fight_dir = data_root() / "interim" / "fight" / "v1"
    rows = {}
    with open(fight_dir / "index.jsonl", encoding="utf-8") as f:
        for r in map(json.loads, f):
            rows[r["sha1"]] = r
    out = []
    for r in sorted(rows.values(), key=lambda r: r["sha1"]):
        if not r.get("ok") or r["matchup"] != "TvZ" or is_test(r["sha1"]) != (split == "test"):
            continue
        ti = next((i for i, p in enumerate(r["players"]) if p["race"] == "T" and p["snapshots"] > 0), None)
        if ti is None:
            continue
        z = np.load(fight_dir / r["sha1"][:2] / f"{r['sha1']}.npz")
        frames, players, starts, units = z["snap_frame"], z["snap_player"], z["snap_start"], z["units"]
        for i in range(len(frames)):
            if players[i] != ti or frames[i] * 42 / 1000 > BEFORE_S:
                continue
            u = units[starts[i]:starts[i + 1]]
            own_buildings = int(sum(1 for k, side in u[:, :2] if side == 1 and is_building(int(k))))
            fighters = int(sum(1 for k, side in u[:, :2] if side == 0 and int(k) in ZERG_FIGHTERS))
            if own_buildings and fighters >= MIN_FIGHTERS:
                out.append({"sha1": r["sha1"], "rel_path": r["rel_path"], "map": r.get("map"),
                            "terran_slot": r["players"][ti]["slot"], "terran": r["players"][ti]["name"],
                            "frame": max(0, int(frames[i]) - LEAD_FRAMES), "zerg_fighters": fighters,
                            "own_units": int((u[:, 1] == 1).sum())})
                break
        if len(out) >= n:
            break
    return out


# --- running -----------------------------------------------------------------------------------

class Losses:
    """Every unit either side had during the window, and when the ones that died died."""

    def __init__(self, slots: dict[int, str]):
        self.slots = slots
        self.seen: dict[int, tuple[int, int]] = {}        # tag -> (owner, first type)
        self.died: dict[int, int] = {}                    # tag -> frame it was found dead

    def note(self, obs: dict, game) -> None:
        here = set()
        for u in obs["units"]:
            here.add(u["tag"])
            if u["owner"] in self.slots and u["tag"] not in self.seen:
                self.seen[u["tag"]] = (u["owner"], u["type"])
        for tag in self.seen:                # gone from view: dead, or inside a bunker / refinery
            if tag not in here and tag not in self.died and game.unit_type_of(tag) == -1:
                self.died[tag] = obs["frame"]

    def result(self, game) -> dict:
        out = {f"{race}_lost": 0 for race in self.slots.values()}
        out.update({f"{race}_workers_lost": 0 for race in self.slots.values()})
        deaths = []                          # (frame, value: + a zerg loss, - a terran loss)
        for tag, (owner, kind) in self.seen.items():
            if game.unit_type_of(tag) == -1:
                race = self.slots[owner]
                out[f"{race}_lost"] += value(kind)
                out[f"{race}_workers_lost"] += kind in (T.SCV, 41)
                deaths.append((self.died.get(tag, game.frame), value(kind) * (1 if race == "Z" else -1)))
        out["deaths"] = sorted(deaths)
        return out


def run_one(sc: dict, controller: str, seconds: float, version: str, style: int | None,
            save: str | None = None, verbose: bool = False, fight_path: str | None = None,
            sample_seed: int | None = None) -> dict:
    """One scenario under one controller. Gary: fight_path picks the fight model (default the
    latest trained); sample_seed seeds its sampled fight decisions and the row gets them
    ("log")."""
    from gary.env import LIVE_COMMAND_DELAY, Game
    replay = data_root() / "raw" / sc["rel_path"]
    row = {"sha1": sc["sha1"][:8], "controller": controller}
    try:
        with Game.scenario(replay, command_delay=LIVE_COMMAND_DELAY) as game:
            game.step(sc["frame"])
            obs = game.observe()
            slot = sc["terran_slot"]
            zerg = next(p["slot"] for p in obs["players"] if p["slot"] != slot and p["race"] == 0)
            losses = Losses({slot: "T", zerg: "Z"})
            losses.note(obs, game)
            end = game.frame + int(seconds * 1000 / 42)
            bot, hi = None, None
            if controller != "pro":
                game.take_over(slot)
            if controller == "gary":
                bot, hi = make_gary(game, slot, version, style, verbose, fight_path)
                if sample_seed is not None:
                    bot.rng, bot.rl_log = np.random.default_rng(sample_seed), []
            while game.frame < end:
                if bot:
                    bot.act()
                    hi.step(2)
                else:
                    game.step(2)
                if game.frame % 12 < 2:
                    losses.note(game.observe(), game)
            row.update(losses.result(game))
            if bot and bot.rl_log is not None:
                row["log"] = bot.rl_log
            if hi:
                acts = [e["act"] for e in hi.pov if "act" in e]
                row["acts"] = len(acts)
                row["fight_orders"] = sum(1 for a in acts if a.startswith(("right-click", "A-click", "minimap right-click", "minimap attack", "S ", "H ", "T ", "C ")))
            if save:
                game.save_replay(save)
                if hi:
                    hi.save_pov(save[:-4] + ".pov.jsonl")
    except Exception as e:  # noqa: BLE001 - one broken scenario must not stop the table
        row["error"] = f"{type(e).__name__}: {e}"[:200]
    return row


_models: dict = {}                       # per process: loaded once


def _model(kind: str, path: str):
    if (kind, path) not in _models:
        import torch
        torch.set_num_threads(1)             # many scenarios run side by side
        from gary.policy.army import ArmyModel
        from gary.policy.fight import FightModel
        from gary.policy.macro import MacroModel
        for k in [k for k in _models if k[0] == kind == "fight"]:
            del _models[k]                   # reinforcement learning: a new fight model each round
        _models[(kind, path)] = {"macro": MacroModel, "army": ArmyModel, "fight": FightModel}[kind].load(path)
    return _models[(kind, path)]


def make_gary(game, slot: int, version: str, style: int | None, verbose: bool = False,
              fight_path: str | None = None):
    from gary.bots import terran_v01 as v01
    from gary.bots.terran_v02 import latest_model
    from gary.bots.terran_v03 import TerranGaryV3, latest_army_model
    from gary.interface import HumanInterface
    from gary.mapinfo import MapInfo
    hi = HumanInterface(game, slot, v01.PROFILES["b_rank"], seed=1)
    macro, army = _model("macro", str(latest_model())), _model("army", str(latest_army_model()))
    if version == "v04":
        from gary.bots.terran_v04 import TerranGaryV4, latest_fight_model
        bot = TerranGaryV4(hi, MapInfo.from_game(game), macro, army,
                           _model("fight", str(fight_path or latest_fight_model())), style, verbose=verbose)
    else:
        bot = TerranGaryV3(hi, MapInfo.from_game(game), macro, army, style, verbose=verbose)
    bot.announce = []                # mid-game: no hello in the chat
    return bot, hi


def _job(args: tuple) -> dict:
    return run_one(*args)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pick", type=int, help="find this many scenarios in held-out games (saved for --run)")
    ap.add_argument("--screen", action="store_true", help="keep only the picked scenarios where control mattered")
    ap.add_argument("--min-gap", type=int, default=100, help="--screen: net value the pro gained over nothing")
    ap.add_argument("--run", type=int, help="score the first N saved scenarios")
    ap.add_argument("--controllers", nargs="+", default=CONTROLLERS, choices=CONTROLLERS)
    ap.add_argument("--seconds", type=float, default=45)
    ap.add_argument("--version", default="v04", choices=["v03", "v04"], help="which Gary takes over")
    ap.add_argument("--style", type=int, default=1)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--save", help="folder: save each scenario's replay (as played) there")
    ap.add_argument("--only", help="run just this scenario (sha1 prefix), Gary narrating what it does")
    ap.add_argument("--split", default="test", choices=["test", "train"],
                    help="scenarios from held-out games (test) or from training games (train, for RL)")
    ap.add_argument("--fight-model", help="Gary's fight model (default: the latest in runs/fight)")
    ap.add_argument("--samples", type=int, default=0,
                    help="Gary samples its fight decisions; score the mean over this many draws")
    args = ap.parse_args()
    if args.pick:
        found = pick(args.pick, args.split)
        if args.screen:
            jobs = [(sc, c, args.seconds, args.version, args.style) for sc in found for c in ("pro", "nothing")]
            with ProcessPoolExecutor(args.parallel) as pool:
                res = list(pool.map(_job, jobs))
            net = lambda r: r["Z_lost"] - r["T_lost"] if "error" not in r else None
            kept = []
            for sc, pro, nothing in zip(found, res[0::2], res[1::2]):
                if net(pro) is not None and net(nothing) is not None:
                    sc["gap"] = net(pro) - net(nothing)
                    if sc["gap"] >= args.min_gap:
                        kept.append(sc)
            print(f"screened {len(found)}: {len(kept)} where the pro's control was worth {args.min_gap}+")
            found = kept
        path = scenarios_path(args.split)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in found), encoding="utf-8")
        print(f"{len(found)} scenarios -> {path}")
    if args.run:
        scs = [json.loads(line) for line in scenarios_path(args.split).read_text(encoding="utf-8").splitlines()][:args.run]
        if args.only:
            scs = [sc for sc in scs if sc["sha1"].startswith(args.only)]
            for c in args.controllers:
                print(c, run_one(scs[0], c, args.seconds, args.version, args.style, verbose=c == "gary",
                                 fight_path=args.fight_model))
            return
        if args.save:
            Path(args.save).mkdir(parents=True, exist_ok=True)
        jobs = []
        for sc in scs:
            for c in args.controllers:
                draws = args.samples if c == "gary" and args.samples else 0
                for k in range(max(1, draws)):
                    name = f"{sc['sha1'][:8]}_{c}" + (f"_{k}" if k else "")
                    save = str(Path(args.save) / f"{name}.rep") if args.save else None
                    jobs.append((sc, c, args.seconds, args.version, args.style, save, False, args.fight_model,
                                 k if draws else None))
        with ProcessPoolExecutor(args.parallel) as pool:
            rows = mean_rows(list(pool.map(_job, jobs)))
        report(scs, rows, args)


def mean_rows(rows: list[dict]) -> list[dict]:
    """Rows of the same scenario and controller (sampled draws) averaged into one."""
    by: dict[tuple, list[dict]] = {}
    for r in rows:
        by.setdefault((r["sha1"], r["controller"]), []).append(r)
    out = []
    for (sha, c), rs in by.items():
        ok = [r for r in rs if "error" not in r]
        if not ok:
            out.append(rs[0])
            continue
        out.append({"sha1": sha, "controller": c, **{k: int(round(np.mean([r[k] for r in ok])))
                                                      for k in ok[0] if k not in ("sha1", "controller", "log", "deaths")}})
    return out


def report(scs: list[dict], rows: list[dict], args: argparse.Namespace) -> None:
    by = {(r["sha1"], r["controller"]): r for r in rows}
    cs = args.controllers
    print(f"{len(scs)} scenarios, {args.seconds:g} s after the takeover; value lost (minerals + gas) T / Z, "
          f"SCVs lost; Gary = {args.version} style {args.style}"
          + (f", fight decisions sampled, mean of {args.samples} draws" if args.samples else ""))
    print(f"{'game':9s} {'at':>5s} " + " ".join(f"{c:>18s}" for c in cs))
    tot = {c: [0, 0, 0, 0] for c in cs}
    nets = {c: [] for c in cs}
    for sc in scs:
        cells = []
        for c in cs:
            r = by[(sc["sha1"][:8], c)]
            if "error" in r:
                cells.append(f"{'error':>18s}")
                continue
            t = tot[c]
            t[0] += r["T_lost"]; t[1] += r["Z_lost"]; t[2] += r["T_workers_lost"]; t[3] += 1
            nets[c].append(r["Z_lost"] - r["T_lost"])
            cells.append(f"{r['T_lost']:>6d} /{r['Z_lost']:>5d} ({r['T_workers_lost']:>2d})")
        s = sc["frame"] * 42 // 1000
        print(f"{sc['sha1'][:8]:9s} {s // 60:>2d}:{s % 60:02d} " + " ".join(cells))
    print(f"{'mean':15s} " + " ".join(
        f"{t[0] / max(1, t[3]):>6.0f} /{t[1] / max(1, t[3]):>5.0f} ({t[2] / max(1, t[3]):>4.1f})" for t in tot.values()))
    print(f"{'net (Z - T)':15s} " + " ".join(f"{np.mean(v) if v else 0:>18.0f}" for v in nets.values()))
    errs = [r for r in rows if "error" in r]
    for r in errs[:5]:
        print("error", r["sha1"], r["controller"], r["error"])
    acts = [r for r in rows if "acts" in r]
    if acts:
        print(f"Gary's actions per scenario: {np.mean([r['acts'] for r in acts]):.0f} "
              f"(orders - right-clicks, A-clicks, minimap orders, S/H/T/C: {np.mean([r['fight_orders'] for r in acts]):.0f})")


if __name__ == "__main__":
    main()

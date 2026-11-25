"""A headless game between two Garys (docs/REFACTOR.md Phase 3): each side a manifest (gary/agent/manifests.py),
its race the manifest's, on a map, from a seed, for some minutes. The one launcher: the league (eval/league.py),
mirrors (--a gz1 --b gz1), the tests and the tools that step a game (Match) all play through it.

Every 30 s a line with both sides' buildings, army and economy; at the end the result line ("A won", "B won" or
"time") and the replay, both sides' screens (.pov.jsonl for A, .bpov.jsonl for B), traces (.trace.jsonl,
.btrace.jsonl) and the shared decision records (.records.jsonl) beside it. Paired fight episodes (GARY_PAIRS:
eval/pairs.py) as before.

Usage:
  python -m eval.match --a gt1 --b gz1 --map <map> --seed 4004 --minutes 30
  python -m eval.match --a gz1 --b gz1 --map <map> --seed 6001 --minutes 30 --save runs/mirror/m.rep
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from gary.agent.manifests import build_gary, manifest_name, manifest_of  # noqa: E402
from gary.decision_log import LOG  # noqa: E402
from gary.env import LIVE_COMMAND_DELAY, Game  # noqa: E402
from gary.interface import PROFILES, HumanInterface  # noqa: E402
from gary.mapinfo import MapInfo  # noqa: E402
from gary.race import Race  # noqa: E402

def _fighter(unit_type: int) -> bool:
    """The status line's army: every race's units with supply that aren't workers (it counted infantry, Zerg and
    Protoss ground units only, and a TvT's mech army read 0-4 all game, round MT140a)."""
    from gary.policy.army import is_building, is_worker, supply_x2
    return supply_x2(unit_type) > 0 and not is_worker(unit_type) and not is_building(unit_type)


def _slots(game, races: list[str]) -> list[int]:
    """Each side's slot: the owner of a town hall of its race (in a mirror, in slot order)."""
    obs = game.observe()
    halls = [u for u in obs["units"] if any(u["type"] in Race.of(r).town_halls for r in races)]
    out: list[int] = []
    for r in races:
        s = next(u["owner"] for u in sorted(halls, key=lambda u: u["owner"])
                 if u["type"] in Race.of(r).town_halls and u["owner"] not in out)
        out.append(s)
    return out


class Match:
    """A game to step by hand (the tools that branch, probe or record games): side A, Gary (a Terran manifest by
    default), against side B (gz1 by default), with pro hands. m.gary, m.zerg: the two Garys; m.slot, m.his:
    their slots and hands by race letter."""

    def __init__(self, seed: int, version: str, map_path, opponent: str = "gz1", style: int | None = None):
        races = [manifest_of(version).get("race", "T"), manifest_of(opponent).get("race", "T")]
        self.game = Game.new(map_path, races, ["Gary", "Gary B"], seed=seed, command_delay=LIVE_COMMAND_DELAY)
        self.map = MapInfo.from_game(self.game)
        slots = _slots(self.game, races)
        self.slot = dict(zip(races, slots))
        self.his = {r: HumanInterface(self.game, s, PROFILES["pro"], seed=s) for r, s in self.slot.items()}
        for r, hi in self.his.items():
            hi.side = r
        self.gary = build_gary(self.his[races[0]], self.map, version, style, verbose=False, seed=seed)
        self.zerg = build_gary(self.his[races[1]], self.map, opponent, seed=seed)
        self.done = False

    def over(self) -> bool:
        players = {p["slot"] for p in self.game.observe()["players"]}
        return not set(self.slot.values()) <= players

    def step(self) -> None:
        if self.done or (self.game.frame % 24 < 2 and self.over()):
            self.done = True                          # a side is gone: nothing more to play
            self.game.step(2)
            return
        try:
            self.gary.act()
            self.zerg.act()
        except StopIteration:                         # a player was just eliminated (its view has no "me")
            self.done = True
            return
        for i, hi in enumerate(self.his.values()):
            hi.step(2, advance_game=(i == 0))


GG_EVERY = 24 * 5                # frames between the critic's reads for a gg
GG_HOLD = 24 * 60                # the win odds at or under the threshold this long: the side types gg and leaves


class Resign:
    """Issue #62's rule, as the referee plays it: each side's critic (gary/policy/value.py, its matchup and race) reads
    the game from that side's own view; a side whose win odds stay at or under the threshold for GG_HOLD types gg and
    leaves, as the pros do. Checked before it played (eval/critic_gg.py, 2026-11-18): of the held-out decided games read
    at 10% or less for a minute, the side won 0-3 in each matchup after (8 of about 330), and most such games went to
    30:00 unfinished. A side with no critic plays on."""

    def __init__(self, garys: dict, races: list[str], threshold: float, slots: list[int] | None = None):
        from gary.agent.manifests import model_for
        from gary.policy.belief import BeliefModel
        from gary.policy.value import ValueModel, ValueView
        self.threshold, self.reads, self.since, self.slots = threshold, {}, {}, slots
        for k, g in garys.items():
            try:
                critic = ValueModel.load(model_for("value", g.matchup, races[k]))
                view = ValueView(g, BeliefModel.load(model_for("belief", g.matchup, races[k])))
            except (FileNotFoundError, SystemExit) as e:
                print(f"gg: no critic for {races[k]} in {g.matchup} ({e}): plays on", flush=True)
                continue
            from gary.policy.macro import FeatureSpec
            from gary.policy.value import EXTRAS
            spec = getattr(getattr(g.macro, "tracker", None), "spec", None)
            if spec is None or critic.ckpt["n_in"] != spec.size + len(EXTRAS) \
                    or FeatureSpec(**critic.ckpt["spec"]).to_dict() != spec.to_dict():
                print(f"gg: {races[k]}'s critic ({critic.path}) reads another build's view (the dev build's, "
                      f"tests/test_value.py): plays on", flush=True)
                continue
            self.reads[k] = (g, critic, view)

    def look(self, frame: int) -> int | None:
        """Each side's view kept every second; every GG_EVERY its win odds read: the side that resigns now, or None."""
        import math
        out = None
        for k, (g, critic, view) in self.reads.items():
            obs = g.hi.observe()
            view.look(obs)
            if frame % GG_EVERY >= 24:
                continue
            p = 1 / (1 + math.exp(-float(critic.predict(view.features(obs))["win"][0])))
            if p > self.threshold:
                self.since.pop(k, None)
                continue
            start = self.since.setdefault(k, frame)
            if frame - start >= GG_HOLD and out is None:
                from gary.decision_log import LOG
                LOG.slot = self.slots[k] if self.slots else None
                LOG.decision(g.hi.side, "gg", frame, "gg", p, by=f"rule: the critic's win odds at or under "
                             f"{self.threshold:.0%} for {GG_HOLD // 24} s (issue #62)")
                out = k
        return out


def play(map_path: str, minutes: float, seed: int, save: str, a: str, b: str, style: int | str | None = None,
         style_b: int | str | None = None, gg: float | None = None, spec=None) -> str:
    """One game, A against B; its result ("A won", "B won", "time"). gg: the critic's win odds at which a side
    resigns (Resign), None to play to the end."""
    races = [manifest_of(a).get("race", "T"), manifest_of(b).get("race", "T")]
    mirror = races[0] == races[1]
    with Game.new(map_path, races, [f"Gary {a}", f"Gary {b}"], seed=seed, command_delay=LIVE_COMMAND_DELAY) as game:
        mapinfo = MapInfo.from_game(game)
        mapinfo.name = Path(map_path).stem             # (the map's name, for what keys on it: gary/agent/shadow.py)
        slots = _slots(game, races)
        obs = game.observe()
        # (the hands in the order the town halls come in the game's units, A's first on a tie, as the old
        # launcher made them: which hands step the game is part of a game's seed)
        first = {}
        for u in obs["units"]:
            for k in (0, 1):
                if u["owner"] == slots[k] and u["type"] in Race.of(races[k]).town_halls and slots[k] not in first:
                    first[slots[k]] = len(first)
        order = sorted(range(2), key=lambda k: first.get(slots[k], k))
        his = {k: HumanInterface(game, slots[k], PROFILES[manifest_of((a, b)[k]).get("hands", "pro")], seed=slots[k])
               for k in order}
        LOG.clear_records()
        for k, hi in his.items():
            hi.side = races[k]
        if mirror:
            LOG.slot = slots[0]
        garys = {0: build_gary(his[0], mapinfo, a, style, seed=seed, strategy=spec)}
        if mirror:
            LOG.slot = slots[1]
        garys[1] = build_gary(his[1], mapinfo, b, style_b, seed=seed)
        LOG.slot = None
        end = int(minutes * 60 * 24)
        result = "time"
        from eval.pairs import Brancher                    # (paired fight episodes, when GARY_PAIRS is set)
        slot_of = {"T": slots[races.index("T")] if "T" in races else slots[0],
                   "Z": slots[races.index("Z")] if "Z" in races else slots[1]}
        brancher = Brancher(game, slot_of, seed or 0)
        ctx = {"gary": garys[0], "zerg": garys[1], "his": {races[k]: his[k] for k in his}, "slot_of": slot_of}
        lead = order[0]
        resign = Resign(garys, races, gg, slots if mirror else None) if gg else None
        resigned = None
        while his[lead].frame < end:
            players = {p["slot"] for p in game.observe()["players"]}
            if not set(slots) <= players:                     # someone was eliminated
                result = "A won" if slots[0] in players else "B won"
                break
            for k in (0, 1):
                if mirror:
                    LOG.slot = slots[k]                       # (the records say whose they are: eval/why.py --slot)
                garys[k].act()
            for i, k in enumerate(order):
                if mirror:
                    LOG.slot = slots[k]
                his[k].step(2, advance_game=(i == 0))
            LOG.slot = None
            if brancher.on:
                brancher.maybe(game, ctx)
            if resign is not None and his[lead].frame % 24 < 2:
                k = resign.look(his[lead].frame)
                LOG.slot = None
                if k is not None:
                    resigned = k
                    result = "B won" if k == 0 else "A won"
                    break
            if his[lead].frame % (24 * 30) < 2:
                o = game.observe()
                t = his[lead].frame // 24
                parts = {}
                for k, label in ((0, "A" if mirror else races[0]), (1, "B" if mirror else races[1])):
                    mine = [u for u in o["units"] if u["owner"] == slots[k]]
                    race = Race.of(races[k])
                    p = next((q for q in o["players"] if q["slot"] == slots[k]), {"minerals": 0, "gas": 0})
                    parts[label] = (sum(1 for u in mine if 106 <= u["type"] <= 175),
                                    sum(1 for u in mine if _fighter(u["type"])),
                                    sum(1 for u in mine if u["type"] == race.worker),
                                    sum(1 for u in mine if u["type"] in race.town_halls), p["minerals"], p["gas"])
                (la, pa), (lb, pb) = parts.items()
                print(f"{t // 60}:{t % 60:02d}  buildings {la} {pa[0]} {lb} {pb[0]}  army {la} {pa[1]} {lb} {pb[1]}  "
                      f"workers {la} {pa[2]} {lb} {pb[2]}  halls {la} {pa[3]} {lb} {pb[3]}  "
                      f"bank {la} {pa[4]}/{pa[5]} {lb} {pb[4]}/{pb[5]}", flush=True)
                if not pa[0] or not pb[0]:
                    result = "B won" if not pa[0] else "A won"
                    break
        game.save_replay(save)
        brancher.save()
        base = save[:-4] if save.endswith(".rep") else save
        his[0].save_pov(base + ".pov.jsonl")
        his[1].save_pov(base + ".bpov.jsonl")
        garys[0].save_trace(base + ".trace.jsonl")
        garys[1].save_trace(base + ".btrace.jsonl")
        LOG.save_records(base + ".records.jsonl")
        gone = f" ({'A' if resigned == 0 else 'B'} typed gg)" if resigned is not None else ""
        print(f"{result}; saved {save} (screens, traces and records beside it){gone}")
        return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True, type=manifest_name, help="side A's manifest")
    ap.add_argument("--b", required=True, type=manifest_name, help="side B's manifest")
    ap.add_argument("--map", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--style", help="A's build style, by id or name (gary/styles.py; --list-styles), over its manifest's")
    ap.add_argument("--style-b", help="B's build style, the same")
    ap.add_argument("--list-styles", action="store_true", help="print the build styles of A's and B's races and exit")
    ap.add_argument("--strategy", help="A's strategy as text, compiled before the game (gary/agent/strategy.py): its "
                    "style and card (Arm B), the opponent's style if named; ambiguous or unsupported: printed, no game")
    ap.add_argument("--from-replay", help="A's card from this replay's player (gary/agent/strategy.py from_replay)")
    ap.add_argument("--from-player", help="the replay's player (default: the one of A's race)")
    ap.add_argument("--card", help="A's StrategySpec, a JSON file (python -m gary.agent.strategy ... --out)")
    ap.add_argument("--save", default="match.rep")
    ap.add_argument("--gg", type=float, help="a side resigns when its critic's win odds stay at or under this for a "
                    "minute (issue #62; eval/league.py plays at 0.1); unset: to the end")
    args = ap.parse_args()
    if args.list_styles:
        from gary.styles import describe
        races = [manifest_of(args.a).get("race", "T"), manifest_of(args.b).get("race", "T")]
        mu = "".join(sorted(races, key="TZP".index)) if races[0] != races[1] else races[0] * 2
        mu = f"{mu[0]}v{mu[1]}"
        for r in dict.fromkeys(races):
            print(describe(mu, r))
        return
    spec = None
    if args.strategy or args.from_replay or args.card:
        from gary.agent.strategy import describe, matchup_of, resolve
        race = manifest_of(args.a).get("race", "T")
        rb = manifest_of(args.b).get("race", "T")
        spec = resolve(race, matchup_of(race, rb), args.strategy, args.from_replay, args.from_player, args.card)
        print(describe(spec))
        if spec.status != "ok" or not spec.card:
            raise SystemExit(f"strategy {spec.status}: no game (see the notes above)")
        spec.save((args.save[:-4] if args.save.endswith(".rep") else args.save) + ".spec.json")
        if args.style_b is None and spec.opponent_style is not None:
            args.style_b = spec.opponent_style
    play(args.map, args.minutes, args.seed, args.save, args.a, args.b, args.style, args.style_b, args.gg, spec)


if __name__ == "__main__":
    main()

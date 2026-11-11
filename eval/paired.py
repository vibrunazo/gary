"""Two versions compared game against game: the paired score of rounds B against rounds A, by map and seed.

A game's score for a side is 1 won, 0 lost, and at the time limit (most league games) its grade:

  supply   who is ahead in supply used at the end (eval/league.py grade: ahead 0.75, even 0.5, behind 0.25)
  critic   the side's critic's win odds over the last minute (runs/value/<matchup>_<race>_*, the newest: issue #63)
  critics  both sides' critics: the mean of the side's odds and one minus the other side's (in a mirror the one
           critic reading each side)

The paired score is the mean of B - A over the games both played, with its 90% interval (the games resampled BOOT
times), the spread of the differences and what 96 paired games resolve with it: the interval's half width (1.645 sd /
sqrt 96) and the smallest effect found four times in five (2.49 sd / sqrt 96, the minimum detectable effect AGENTS.md
asks for before a round). A grade is the better judge where a real difference stands further from zero in its own
spread (t: the mean over its standard error), not where its spread alone is smaller: odds near a half shrink both.

The critic's reads are taken from each replay re-simulated as its training games are (train/value.py league_game) and
kept beside the round (critic_<run>.json): a round and its baseline are graded by the same critic, named in the output.

    python -m eval.paired --a HB172a TS170b --b HO172a HO172b --side B         # the Zerg's score, by supply
    python -m eval.paired --a HB172a TS170b --b HO172a HO172b --side B --grade all
    python -m eval.paired --a BT179a --b FT179a --grade all --differ 0.4       # and the games the grades part on
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

from eval import monitor, priority  # noqa: E402

BOOT = 4000
LAST_S = 60                    # the critic's grade: its odds over this much of the game's end
SUPPLY = {"won": 1.0, "lost": 0.0, "time, T ahead": 0.75, "time, even": 0.5, "time, Z ahead": 0.25, "time": 0.5}
GRADES = ("supply", "critic", "critics")
GAMES = 96


def load_round(name: str) -> dict:
    return json.loads((REPO / "runs" / "league" / name / "round.json").read_text(encoding="utf-8"))


def races_of(rnd: dict) -> tuple[str, str]:
    """(side A's race, side B's) of a round."""
    from gary.agent.manifests import MANIFESTS
    side = lambda m: MANIFESTS[str(m).split("+")[0]].get("race", "T")
    return side(rnd["terran"]), side(rnd.get("b") or rnd.get("zerg") or "gz1")


def replay_of(name: str, g: dict) -> Path:
    """A game's replay: where the round recorded it, or in the round's own folder (a round played in a worktree and
    copied here keeps the worktree's paths)."""
    given = Path(g["replay"])
    return given if given.exists() else REPO / "runs" / "league" / name / g["map"] / given.name


def newest_critic(matchup: str, race: str) -> Path | None:
    runs = sorted(p for p in (REPO / "runs" / "value").glob(f"{matchup}_{race}_*") if (p / "model.pt").exists())
    return runs[-1] if runs else None


def read_game(args: tuple) -> tuple[str, float | None]:
    """One game's read by a critic: its win odds for the race's nth player over the last LAST_S seconds."""
    job, critic, race, matchup, nth = args
    from gary.policy.value import ValueModel
    from train.value import GARY_EVERY_S, league_game
    model = ValueModel.load(Path(critic) / "model.pt")
    g = league_game((job, model.ckpt["spec"], race, matchup, nth))
    if not len(g["x"]) or g["x"].shape[1] != model.ckpt["n_in"]:
        return job[2], None
    p = 1 / (1 + np.exp(-model.predict(np.asarray(g["x"], np.float32))["win"]))
    return job[2], float(p[-max(1, LAST_S // GARY_EVERY_S):].mean())


def critic_reads(name: str, rnd: dict, race: str, nth: int, workers: int) -> tuple[dict, str | None]:
    """{(map, seed): the critic's odds for the race's nth player at the end} of a round's games, and the critic's
    name; read once and kept beside the round."""
    critic = newest_critic(rnd.get("matchup", "TvZ"), race)
    if critic is None:
        return {}, None
    cache = REPO / "runs" / "league" / name / f"critic_{critic.name}_{nth}.json"
    known = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    a_race = races_of(rnd)[0]
    jobs = [((str(replay_of(name, g)), g["result"], f"{g['map']}/{g['seed']}", a_race), str(critic), race,
             rnd.get("matchup", "TvZ"), nth)
            for g in rnd["games"] if f"{g['map']}/{g['seed']}" not in known and replay_of(name, g).exists()]
    if jobs:
        with ProcessPoolExecutor(workers) as pool:
            for key, p in monitor.track(pool.map(read_game, jobs), len(jobs), f"{name}: {critic.name} reads"):
                known[key] = p
        cache.write_text(json.dumps(known), encoding="utf-8")
    return {tuple(k.rsplit("/", 1)): v for k, v in known.items()}, critic.name


def scores(names: list[str], side: str, grades: tuple, workers: int) -> tuple[dict, dict]:
    """{grade: {(map, seed): the side's score}} over the rounds' games, and the critics that read them."""
    out = {g: {} for g in grades}
    critics = {}
    for name in names:
        rnd = load_round(name)
        ra, rb = races_of(rnd)
        mirror = ra == rb
        mine, theirs = ((ra, 0), (rb, 1 if mirror else 0)) if side == "A" else ((rb, 1 if mirror else 0), (ra, 0))
        reads = {}
        if "critic" in grades or "critics" in grades:
            reads["own"], critics["own"] = critic_reads(name, rnd, *mine, workers)
        if "critics" in grades:
            reads["other"], critics["other"] = critic_reads(name, rnd, *theirs, workers)
        for g in rnd["games"]:
            key = (g["map"], str(g["seed"]))
            s = SUPPLY[g.get("graded", g["result"])]
            s = s if side == "A" else 1 - s
            decided = g["result"] in ("won", "lost")
            if "supply" in grades:
                out["supply"][key] = s
            own = reads.get("own", {}).get(key)
            other = reads.get("other", {}).get(key)
            if "critic" in grades and (decided or own is not None):
                out["critic"][key] = s if decided else own
            if "critics" in grades and (decided or (own is not None and other is not None)):
                out["critics"][key] = s if decided else (own + 1 - other) / 2
    return out, critics


def compare(a: dict, b: dict) -> dict | None:
    """The paired score of B against A over the games both have."""
    keys = sorted(set(a) & set(b))
    if len(keys) < 2:
        return None
    d = np.array([b[k] - a[k] for k in keys])
    rng = np.random.default_rng(0)
    means = d[rng.integers(0, len(d), (BOOT, len(d)))].mean(1)
    sd = float(d.std(ddof=1))
    return {"n": len(keys), "a": float(np.mean([a[k] for k in keys])), "b": float(np.mean([b[k] for k in keys])),
            "mean": float(d.mean()), "lo": float(np.quantile(means, 0.05)), "hi": float(np.quantile(means, 0.95)), "sd": sd,
            "t": float(d.mean() / (sd / math.sqrt(len(d)))) if sd else 0.0,
            "half": 1.645 * sd / math.sqrt(GAMES), "mde": 2.49 * sd / math.sqrt(GAMES), "keys": keys, "d": d}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", nargs="+", required=True, help="the baseline's rounds (runs/league names)")
    ap.add_argument("--b", nargs="+", required=True, help="the candidate's rounds, on the same maps and seeds")
    ap.add_argument("--side", default="A", choices=["A", "B"], help="whose score: side A (--vs) or side B (--zerg)")
    ap.add_argument("--grade", default="supply", choices=GRADES + ("all",))
    ap.add_argument("--differ", type=float, help="list the games whose difference parts by this much between grades")
    ap.add_argument("--workers", type=int, default=6)
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    grades = GRADES if args.grade == "all" else (args.grade,)
    sa, ca = scores(args.a, args.side, grades, args.workers)
    sb, cb = scores(args.b, args.side, grades, args.workers)
    print(f"side {args.side}: B {' '.join(args.b)} against A {' '.join(args.a)}"
          + (f"; critics {', '.join(sorted({v for v in list(ca.values()) + list(cb.values()) if v}))}" if ca or cb else ""))
    got = {}
    for g in grades:
        r = got[g] = compare(sa[g], sb[g])
        if r is None:
            print(f"  {g:8s} no paired games (no critic for this matchup and race, or no replays)")
            continue
        print(f"  {g:8s} {r['n']} paired games: A {r['a']:.3f}, B {r['b']:.3f}, B - A {r['mean']:+.3f} [{r['lo']:+.3f}, "
              f"{r['hi']:+.3f}], t {r['t']:+.2f}; spread {r['sd']:.3f}: {GAMES} games resolve +-{r['half']:.3f}, "
              f"detect {r['mde']:.3f}")
    if args.differ and got.get("supply") and got.get(grades[-1]) and grades[-1] != "supply":
        s, c = got["supply"], got[grades[-1]]
        ds, dc = dict(zip(s["keys"], s["d"])), dict(zip(c["keys"], c["d"]))
        for k in sorted(set(ds) & set(dc), key=lambda k: -abs(ds[k] - dc[k])):
            if abs(ds[k] - dc[k]) >= args.differ:
                print(f"    {k[0]} seed {k[1]}: supply {ds[k]:+.2f}, {grades[-1]} {dc[k]:+.2f} "
                      f"(A {sa['supply'][k]:.2f} / {sa[grades[-1]][k]:.2f}, B {sb['supply'][k]:.2f} / {sb[grades[-1]][k]:.2f})")


if __name__ == "__main__":
    main()

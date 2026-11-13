"""How often a unit enters and leaves a mode, per half second of a fight, by the judge's odds that a pro's unit is
in the mode in that situation: the pros against Gary's rounds.

The judge (eval/judge.py) says whether Gary's units are in a mode where a pro's would be. This says how they get
there: of the units out of the mode, the share that is in it half a second later, and of those in it, the share
that has left, each by the judge's odds for the situation. A pro's tank sieges sooner the likelier the situation
(0.6% of its half seconds where the judge says under 20%, 6.2% where it says over 80%, against a Protoss) and
leaves Siege Mode more rarely (1.2% to 0.2%); a Gary whose line is flat, or that leaves the mode several times as
often, flips in and out of it whatever its share of moments in the mode.

    python -m eval.judge --race T --matchup PvT --state siege --rounds PT258a RD264a     (the judge and the moments)
    python -m eval.mode_hazard --race T --matchup PvT --state siege --rounds PT258a RD264a

The pros' rows are all their games (the judge's own held-out fifth among them: its odds only sort the situations
here). A round's moments are those eval.judge built for it (runs/league/<round>/judge_<race>_v2.npz).
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from eval import judge as J  # noqa: E402

BINS = (0, 0.2, 0.4, 0.6, 0.8, 1.0001)
NEXT = 0.6                           # seconds: the unit's next moment this soon is its next half second


def hazards(m: dict, what: tuple, jd: dict) -> dict:
    """Per bin of the judge's odds: the unit-moments with a next half second, the share in the mode, of those out of
    it the share that entered, of those in it the share that left; and the same over every bin ("all")."""
    X, y, s, tag = J.features(m["rows"], m["extra"], m["count"], m["time"], m["tags"], {what[0], what[1]}, jd["kinds"],
                              what[1])
    game, time = m["game"][s], m["time"][s]
    if jd.get("history"):
        X = np.concatenate([X, J.history(X, J.names(jd["kinds"]), game, tag, time)], 1)
    odds = jd["model"].predict_proba(X)[:, 1]
    order = np.lexsort((time, tag, game))
    g, t, tm, yy, pp = game[order], tag[order], time[order], y[order].astype(int), odds[order]
    nxt = (g[1:] == g[:-1]) & (t[1:] == t[:-1]) & (tm[1:] - tm[:-1] <= NEXT)
    now, then, p = yy[:-1][nxt], yy[1:][nxt], pp[:-1][nxt]
    games = len(np.unique(game))

    def row(sel):
        out, into = sel & (now == 0), sel & (now == 1)
        return {"moments": int(sel.sum()), "in": float(now[sel].mean()) if sel.any() else None,
                "enters": float(then[out].mean()) if out.any() else None, "out": int(out.sum()),
                "leaves": float(1 - then[into].mean()) if into.any() else None, "into": int(into.sum())}
    table = {f"{lo:.0%}-{min(hi, 1):.0%}": row((p >= lo) & (p < hi)) for lo, hi in zip(BINS, BINS[1:])}
    table["all"] = row(np.ones(len(p), bool))
    table["games"] = games
    return table


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--race", default="T")
    ap.add_argument("--matchup", default="TvZ")
    ap.add_argument("--state", default="siege", help="a state of eval/judge.py STATES")
    ap.add_argument("--rounds", nargs="*", default=[])
    args = ap.parse_args()
    from ingest.inventory import data_root
    what = J.STATES[args.race][args.state]
    path = REPO / "runs" / "judge" / f"{args.race}_{args.matchup}_{args.state}.pkl"
    if not path.exists():
        sys.exit(f"no judge at {path}: python -m eval.judge --race {args.race} --matchup {args.matchup} --state {args.state}")
    with open(path, "rb") as f:
        jd = pickle.load(f)
    sets = [("pros", data_root() / "interim" / "roles" / J.PROS[(args.race, args.matchup)])]
    for r in args.rounds:
        p = REPO / "runs" / "league" / r / f"judge_{args.race}_v2.npz"
        if not p.exists():
            sys.exit(f"no moments for {r}: python -m eval.judge --race {args.race} --matchup {args.matchup} "
                     f"--state {args.state} --rounds {r}")
        sets.append((r, p))
    pct = lambda v: "      " if v is None else f"{v:6.2%}"
    print(f"{args.race} in {args.matchup}, {args.state}: per half second of a fight, by the judge's odds of the mode")
    for label, p in sets:
        t = hazards(dict(np.load(p, allow_pickle=True)), what, jd)
        a = t["all"]
        print(f"  {label}: {t['games']} games, {a['moments']:,} unit-moments with a next; in the mode {a['in']:.1%}; "
              f"enters it in {pct(a['enters']).strip()} of its half seconds out of it ({a['out'] * (a['enters'] or 0) / t['games']:.1f} a game), "
              f"leaves it in {pct(a['leaves']).strip()} ({a['into'] * (a['leaves'] or 0) / t['games']:.1f} a game)")
        print("      the judge says   moments  in the mode   out of it   enters    in it   leaves")
        for k, r in t.items():
            if k in ("all", "games"):
                continue
            print(f"      {k:>14s}  {r['moments']:8,d}  {pct(r['in'])}       {r['out']:8,d}  {pct(r['enters'])}  {r['into']:7,d}  {pct(r['leaves'])}")


if __name__ == "__main__":
    main()

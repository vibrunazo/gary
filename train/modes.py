"""The mode models: of a unit out of a mode, the odds a pro's is in it half a second later; of one in it, the odds
it has left (gary/policy/modes.py). From the pros' own transitions in a response dataset: the same unit's next
moment, by its situation (the judge's inputs with the unit's recent past; every own unit's mode hidden).

    python -m train.modes --race T --matchup PvT --state siege        -> runs/modes/PvT_T_siege_<time>.pkl

A fifth of the games is held out (game index % 5 == 0): the models' ranking of the pros' transitions there, and
their line: by fifths of the entry model's own odds, the share of the pros' units that entered. Gary's fight layer
draws a mode at these odds (option modemodel, gary/agent/roles.py), in place of the role model's.
"""
from __future__ import annotations

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from eval import priority  # noqa: E402
from gary.policy.modes import HISTORY, STATES, enemy_kinds, names, transitions  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--race", default="T")
    ap.add_argument("--matchup", default="TvZ")
    ap.add_argument("--state", default="siege", help="a state of gary/policy/modes.py STATES")
    ap.add_argument("--data", help="default: the pros' response dataset the judge reads for this race and matchup")
    ap.add_argument("--out", default="runs/modes")
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from eval.judge import PROS
    from ingest.inventory import data_root
    state = STATES[args.race][args.state]
    path = Path(args.data) if args.data else data_root() / "interim" / "roles" / PROS[(args.race, args.matchup)]
    m = dict(np.load(path, allow_pickle=True))
    kinds = enemy_kinds(m["rows"], m["count"])
    X, now, then, game = transitions(m, state, kinds)
    test = game % 5 == 0
    print(f"{path.name}: {len(X):,} unit-moments with a next half second from {len(np.unique(game))} games; in the mode "
          f"{now.mean():.1%}; held out {len(np.unique(game[test]))} games")
    models = {}
    for name, was in (("enter", 0), ("leave", 1)):
        sel = now == was
        y = (then != was).astype(np.int8)
        t0 = time.time()
        # (small trees on many rows a leaf: a transition is rare, 0.4% to 2.5% of half seconds, and bigger trees were
        # sure of themselves on the held-out games: 1.8% where the pros left in 0.7%)
        clf = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.03, max_leaf_nodes=15, min_samples_leaf=500,
                                             l2_regularization=1.0, random_state=0)
        clf.fit(X[sel & ~test], y[sel & ~test])
        p, yt = clf.predict_proba(X[sel & test])[:, 1], y[sel & test]
        top = p >= np.quantile(p, 1 - yt.mean())
        print(f"  {name}: trained in {time.time() - t0:.0f} s on {int((sel & ~test).sum()):,}; held out {len(yt):,}: the pros "
              f"{yt.mean():.2%} a half second, the model {p.mean():.2%}; AUC {roc_auc_score(yt, p):.3f}; of its top "
              f"{yt.mean():.1%} of moments {yt[top].mean():.0%} are the pros'")
        edges = np.quantile(p, [0.2, 0.4, 0.6, 0.8])
        fifth = np.digitize(p, edges)
        print("    by fifths of its odds, the model and the pros: "
              + ", ".join(f"{p[fifth == k].mean():.2%} {yt[fifth == k].mean():.2%}" for k in range(5)))
        models[name] = clf
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    to = out / f"{args.matchup}_{args.race}_{args.state}_{time.strftime('%Y%m%d-%H%M%S')}.pkl"
    with open(to, "wb") as f:
        pickle.dump({**models, "kinds": kinds, "names": names(kinds) + HISTORY, "state": args.state, "race": args.race,
                     "matchup": args.matchup, "pros": path.name}, f)
    print(f"saved {to}")


if __name__ == "__main__":
    main()

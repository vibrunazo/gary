"""Train the placement model (gary/policy/placement.py) on ingest/placement_dataset.py's samples (#65).

Gradient-boosted trees on what the player knew when a building was decided -> P(its base and side): six classes,
the main, the natural or a newer base, each by the front or the minerals. Split by game (train/macro.py's is_test).
Judged on the held-out games: log-loss against the classes' prior, the base's accuracy, and the answer to air (PvZ: a
Protoss cannon's mineral side with a Spire or Mutalisks seen and without, by minute). The pros' table it replaced
(gp0.21dev) scored 1.103, 1.059 and 0.954 in PvZ, PvT and PvP (the model 0.782, 0.889, 0.779; docs/PROGRESS.md).

    python -m train.placement --matchup PvZ --race P
Output: runs/placement/<matchup>_<race>_<time>/model.pkl and report.json
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

from gary.policy.placement import BASE_FEATURES, CLASSES, categorical, encode, enemy_types  # noqa: E402
from ingest.placement_dataset import out_dir  # noqa: E402
from train.macro import is_test  # noqa: E402

AIR = (43, 141, 137)            # Mutalisk, Spire, Greater Spire


def load(matchup: str, race: str) -> dict:
    """Every player-game's samples of the matchup's race, concatenated, with its game's split."""
    parts = []
    for line in open(out_dir() / "index.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if not r.get("ok") or r["matchup"] != matchup or r.get("race") != race:
            continue
        z = np.load(out_dir() / r["sha1"][:2] / f"{r['sha1']}.npz")
        for k, p in enumerate(r["players"]):
            n = len(z[f"p{k}_type"])
            if n:
                parts.append({"bases": z[f"p{k}_bases"], "glob": z[f"p{k}_glob"], "type": z[f"p{k}_type"],
                              "seen": z[f"p{k}_seen"], "seen_max": z[f"p{k}_seen_max"], "base": z[f"p{k}_base"],
                              "side": z[f"p{k}_side"], "style": np.full(n, p["style"], np.int16),
                              "test": np.full(n, is_test(r["sha1"])), "game": np.full(n, len(parts))})
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def logloss(p: np.ndarray, y: np.ndarray) -> float:
    return float(-np.log(np.clip(p[np.arange(len(y)), y], 1e-4, 1)).mean())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--matchup", default="PvZ")
    ap.add_argument("--race", default="P")
    ap.add_argument("--out", default="runs/placement")
    args = ap.parse_args()
    from sklearn.ensemble import HistGradientBoostingClassifier
    d = load(args.matchup, args.race)
    types = enemy_types(args.matchup, args.race)
    X = encode(d["bases"], d["glob"], d["type"], d["style"], d["seen"], d["seen_max"], types)
    y = (d["base"].astype(int) * 2 + d["side"].astype(int))
    test = d["test"]
    print(f"{len(y)} samples from {len(set(d['game']))} player-games, test {test.sum()}; classes",
          {f"{b}/{s}": f"{(y == k).mean():.0%}" for k, (b, s) in enumerate(CLASSES)})
    cat = np.zeros(X.shape[1], bool)
    cat[categorical(len(BASE_FEATURES))] = True
    clf = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=1.0,
                                         categorical_features=cat, early_stopping=False,
                                         random_state=0)
    t0 = time.time()
    clf.fit(X[~test], y[~test])
    p = np.zeros((test.sum(), 6), np.float32)
    p[:, clf.classes_] = clf.predict_proba(X[test])
    yt = y[test]
    report = {"samples": int(len(y)), "test": int(test.sum()), "seconds": round(time.time() - t0), "iterations": int(clf.n_iter_),
              "logloss": {"model": logloss(p, yt),
                          "prior": logloss(np.tile(np.bincount(y[~test], minlength=6) / (~test).sum(), (len(yt), 1)), yt)},
              "base_acc": float((p.reshape(-1, 3, 2).sum(2).argmax(1) == yt // 2).mean())}
    if args.race == "P" and args.matchup == "PvZ":
        from gary import protoss as P
        dt = {k: v[test] for k, v in d.items()}
        air = np.isin(np.arange(228), AIR)
        seen_air = (dt["seen_max"][:, air] > 0).any(1)
        cannon = dt["type"] == P.CANNON
        rows = {}
        for lo, hi in ((4, 7), (7, 9), (9, 12)):
            for a in (False, True):
                m = cannon & (dt["glob"][:, 0] >= lo) & (dt["glob"][:, 0] < hi) & (seen_air == a)
                if m.sum() >= 10:
                    rows[f"{lo}-{hi} {'air' if a else 'no air'}"] = {
                        "n": int(m.sum()), "pros": float((yt[m] % 2).mean()),
                        "model": float(p[m][:, 1::2].sum(1).mean())}
        report["cannons_by_the_minerals"] = rows
    print(json.dumps(report, indent=1))
    out = Path(args.out) / f"{args.matchup}_{args.race}_{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "model.pkl", "wb") as f:
        pickle.dump({"model": clf, "types": types, "styles": sorted({int(s) for s in d["style"]})}, f)
    (out / "report.json").write_text(json.dumps(report, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    main()

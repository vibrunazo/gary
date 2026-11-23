"""The enemy-plan belief, P(enemy plan | what the player has seen), offline (docs/REFOCUS.md §3.1, Phase 1's first
piece): how well the enemy's plan (taxonomy/plans.py: opening, hatcheries, first tech) can be told from a player's view
of it at a game minute, against what tells it without sightings.

Data: the macro training set (ingest/macro_dataset.py: every second of each pro game, what each player could see of the
other), from the player of --race against the matchup's other race, every SAMPLE seconds from FIRST to LAST; the
inputs are the belief model's (gary/policy/belief.py features_series: game time, each enemy type in sight now and the
most in sight over 30 s, 90 s, 3 min and ever, seconds since an enemy army unit, own supply and workers) and the map;
the label is the enemy player's plan (data/interim/taxonomy/v2/<matchup>_<enemy race>.json). Both eras, the modern games
weighted MODERN_WEIGHT to one (docs/DATA_ERAS.md), no era input.

Scored as written before the first fit (docs/PROGRESS.md 2026-11-23): grouped FOLDS-fold over the modern games (every
modern game scored once, by a model that never saw it), at MINUTES, on the games still running then, the plan "other"
(rare plans and games ended undecided, a label of the game's length) left out of scoring. Per minute: the Brier score
and log-loss of the joint plan and of its three parts (opening, hatcheries, tech), each with a bootstrap interval by
game for the difference from the floor. Beside the model:
  floor    the modern plans' shares on the map among the training folds' games still running at that minute (all maps
           below FLOOR_MIN games)
  answers  (the tech part) answers.py's read of the same view (mutalisks: a Spire or a Mutalisk seen; lurkers: a Lurker
           or its egg seen, or a Hydralisk Den with a Lair and no Spire), its tech shares per read and minute
  ceiling  the same model fed the enemy's true units at that minute: what a perfect scout would read

    python -m train.plan_belief --race T --matchup TvZ
Output: runs/plan_belief/<matchup>_<race>_<time>/report.json (and model.pkl, the model on every game, with --save).
"""
from __future__ import annotations

import argparse
import ast
import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

from eval import monitor, priority  # noqa: E402

SAMPLE = 30                    # seconds between samples
FIRST, LAST = 150, 600         # seconds: the samples' span
MINUTES = (4, 6, 8)            # where it is scored
FOLDS = 5
MODERN_WEIGHT = 10.0
MAP_MIN = 100                  # games on a map for it to be its own category (434 map names over both eras)
FLOOR_MIN = 25                 # modern games on a map (running at the minute) for its own shares
BOOT = 1000
# the trees regularized: a game gives 16 samples of one label, so unregularized trees learn the games (a 400-game try:
# 0.99-1.00 accuracy on the training games, 0.53-0.67 held out, the odds overconfident: log-loss 5-8)
HGB = dict(max_iter=150, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0,
           random_state=0)
# answers.py's read (gary/agent/answers.py), on the raw sighting columns
LAIR, HIVE, SPIRE, GREATER_SPIRE, DEN = 132, 133, 141, 137, 135
MUTALISK, LURKER, LURKER_EGG = 43, 103, 97
TECH_BUILDINGS = [132, 133, 135, 136, 137, 138, 140, 141]   # Lair, Hive, Den, Defiler Mound, Greater Spire, Queen's
                                                            # Nest, Ultralisk Cavern, Spire: a sight of the enemy's tech


def parts(name: str) -> tuple[str, str, str]:
    """A plan's (opening, hatcheries, tech); "other" is other in each."""
    if name == "other":
        return "other", "other", "other"
    o, h, t = [p.strip() for p in name.split(",")]
    return o, h, t


def answers_read(seen_ever: np.ndarray) -> str:
    """answers.py's plan from what was ever seen (one row of the 228 types)."""
    if seen_ever[SPIRE] or seen_ever[GREATER_SPIRE] or seen_ever[MUTALISK]:
        return "mutas"
    if seen_ever[LURKER] or seen_ever[LURKER_EGG] or (seen_ever[DEN] and (seen_ever[LAIR] or seen_ever[HIVE])):
        return "lurkers"
    return "none"


def load(job: tuple):
    """One game: (X seen, X true, times, read per sample, game end second) or None."""
    from gary.policy.belief import features_series
    path, i, enemy, own = job
    try:
        d = np.load(path)
    except Exception:
        return None
    frames = d["frames"]
    n = len(frames)
    if n <= FIRST:
        return None
    seen = d["seen"][:, i]
    true = d["units"][:, 1 - i, :, 0]
    own_units, eco = d["units"][:, i, :, 0], d["eco"][:, i]
    Xs = features_series(seen, own_units, eco, frames, enemy, own)
    Xt = features_series(true, own_units, eco, frames, enemy, own)
    idx = np.arange(FIRST, min(n, LAST + 1), SAMPLE)
    ever = np.maximum.accumulate(seen.astype(np.int32), axis=0)
    reads = [answers_read(ever[t]) for t in idx]
    tech_seen = ever[idx][:, TECH_BUILDINGS].sum(1) > 0
    return Xs[idx], Xt[idx], idx, reads, n, tech_seen


def gary_game(job: tuple):
    """One of Gary's league games re-simulated (eval/league.py's replays, as train/value.py league_game reads them):
    the player of race's view at the samples, as load(), and the enemy's plan from its true units (taxonomy/plans.py's
    rule on the first time each building or unit is there, started or done; the first Lurker for Lurker Aspect, which no
    unit count shows). (Xs, idx, reads, tech_seen, plan parts, map) or None."""
    sys.path.insert(0, str(REPO / "taxonomy"))
    from gary.policy.belief import features_series
    from macro_dataset import RACES, game_arrays, run_resim
    from plans import HATCH_BY, PRESSURE_BY, plan_of
    replay, race, enemy, map_name = job
    try:
        lines = run_resim(str(Path(replay).resolve()))
    except Exception:  # noqa: BLE001 - one bad replay must not stop the batch
        return None
    header = next((r for r in lines if r["type"] == "header"), None)
    d = game_arrays(lines) if header else None
    if d is None:
        return None
    races = {p["slot"]: RACES.get(p["race"]) for p in header["players"]}
    mine = [k for k, sl in enumerate(d["slots"]) if races.get(sl) == race]
    if len(mine) != 1 or races.get(d["slots"][1 - mine[0]]) != enemy:
        return None
    i = mine[0]
    frames, n = d["frames"], len(d["frames"])
    if n <= FIRST:
        return None
    seen = d["seen"][:, i]
    Xs = features_series(seen, d["units"][:, i, :, 0], d["eco"][:, i], frames, enemy, race)
    idx = np.arange(FIRST, min(n, LAST + 1), SAMPLE)
    ever = np.maximum.accumulate(seen.astype(np.int32), axis=0)
    reads = [answers_read(ever[t]) for t in idx]
    tech_seen = ever[idx][:, TECH_BUILDINGS].sum(1) > 0
    zu = d["units"][:, 1 - i].sum(-1) if d["units"].ndim == 4 else d["units"][:, 1 - i]
    first = lambda types, k=1: next((t for t in range(n) if zu[t, types].sum() >= k), None)
    t = {key: v for key, v in (("pool", first([142])), ("hatch2", first([131, 132, 133], 2)),
                               ("hatch3", first([131, 132, 133], 3)), ("spire", first([141, 137])),
                               ("lurker_aspect", first([103, 97])), ("den", first([135]))) if v is not None}
    lings = int(zu[min(PRESSURE_BY, n - 1), 37])
    return Xs[idx], idx, reads, tech_seen, plan_of(t, lings, n), map_name


def score_gary(model_dir: Path, rounds: list[str], race: str, matchup: str, workers: int) -> None:
    """The saved model (--save) on Gary's own games: how often the enemy's tech was seen by each minute (Gary against
    the pros), and the model's Brier against the pros' floor and against Gary's own games' plan shares."""
    from ladder_maps import clean_name
    saved = pickle.load(open(model_dir / "model.pkl", "rb"))
    clf, maps, names, floors, pro_tech = saved["model"], saved["maps"], saved["names"], saved["floors"], saved["tech_seen"]
    enemy = [r for r in matchup.split("v") if r != race][0]
    ids = {tuple(parts(v)): k for k, v in names.items()}
    jobs = [(str(p), race, enemy, p.parent.name) for r in rounds for p in sorted((REPO / "runs" / "league" / r).rglob("*.rep"))]
    with ProcessPoolExecutor(workers) as pool:
        games = [g for g in monitor.track(pool.map(gary_game, jobs), len(jobs), "Gary's games") if g is not None]
    other = next(k for k, v in names.items() if v == "other")
    ys = [ids.get(tuple(g[4]), other) for g in games]
    print(f"{len(games)} of Gary's games; the enemy's plans: {Counter(names[y] for y in ys).most_common(6)}")
    own = np.bincount(ys, minlength=len(names)) + 0.5
    own = own / own.sum()
    for minute in MINUTES:
        X, y, seen_tech, fl = [], [], [], []
        for g, yy in zip(games, ys):
            k = np.where(g[1] == minute * 60)[0]
            if not len(k):
                continue
            m = clean_name(g[5])
            X.append(np.concatenate([g[0][k[0]], [maps.index(m) if m in maps else 0]]))
            y.append(yy); seen_tech.append(g[3][k[0]]); fl.append(floors[str(minute)].get(m, floors[str(minute)]["all"]))
        if not X:
            continue
        X, y, fl = np.array(X), np.array(y), np.array(fl)
        P = np.zeros((len(y), len(names)))
        P[:, clf.classes_] = clf.predict_proba(X)
        keep = y != other
        own_p = np.tile(own, (len(y), 1))
        print(f"{minute}:00  {len(y)} games running; the enemy's tech building seen by then: Gary {np.mean(seen_tech):.0%}, "
              f"the pros {pro_tech[str(minute)]:.0%}; Brier (other left out, {keep.sum()} games): model "
              f"{brier(P[keep], y[keep]).mean():.3f}, the pros' floor {brier(fl[keep], y[keep]).mean():.3f}, Gary's "
              f"games' own shares {brier(own_p[keep], y[keep]).mean():.3f}")


def jobs_for(race: str, matchup: str):
    """(job, sha1, rel_path, map, plan id) for every game of the matchup whose enemy has a plan label."""
    from inventory import data_root
    races = matchup.split("v")
    enemy = races[1] if races[0] == race else races[0]
    labels = json.load(open(REPO / "data" / "interim" / "taxonomy" / "v2" / f"{matchup}_{enemy}.json", encoding="utf-8"))
    assign = labels["assignments"]
    root = data_root() / "interim" / "macro" / "v1"
    out, seen_paths = [], set()
    for line in open(root / "index.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if not r.get("ok") or r.get("matchup") != matchup or r["rel_path"] in seen_paths:
            continue
        players = r["players"] if isinstance(r["players"], list) else ast.literal_eval(r["players"])   # (kept as text)
        if len(players) != 2:
            continue
        for i, p in enumerate(players):
            e = players[1 - i]
            if p["race"] == race and e["race"] == enemy and f"{r['rel_path']}|{e['name']}" in assign:
                seen_paths.add(r["rel_path"])
                out.append(((str(root / r["sha1"][:2] / f"{r['sha1']}.npz"), i, enemy, race), r["sha1"], r["rel_path"],
                            r.get("map", ""), int(assign[f"{r['rel_path']}|{e['name']}"])))
    names = {int(k): v for k, v in labels["names"].items()}
    return out, names


def brier(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Per-sample multiclass Brier (sum over classes)."""
    Y = np.zeros_like(P)
    Y[np.arange(len(y)), y] = 1
    return ((P - Y) ** 2).sum(1)


def logloss(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    return -np.log(np.clip(P[np.arange(len(y)), y], 1e-6, 1))


def to_parts(P: np.ndarray, names: dict[int, str]) -> dict[str, tuple[np.ndarray, list[str]]]:
    """The joint's probabilities summed into each part's values."""
    out = {}
    for k, part in enumerate(("opening", "hatcheries", "tech")):
        vals = sorted({parts(names[c])[k] for c in names})
        M = np.zeros((len(names), len(vals)))
        for c in names:
            M[c, vals.index(parts(names[c])[k])] = 1
        out[part] = (P @ M, vals)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--race", default="T")
    ap.add_argument("--matchup", default="TvZ")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, help="only this many games (a try)")
    ap.add_argument("--save", action="store_true", help="also fit on every game and save model.pkl")
    ap.add_argument("--out")
    ap.add_argument("--gary", nargs="+", metavar="ROUND",
                    help="no training: score the model in --model on these league rounds (Gary's own games)")
    ap.add_argument("--model", help="with --gary: the run folder with model.pkl")
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    from sklearn.ensemble import HistGradientBoostingClassifier
    from ladder_maps import clean_name
    if args.gary:
        score_gary(Path(args.model), args.gary, args.race, args.matchup, args.workers)
        return
    jobs, names = jobs_for(args.race, args.matchup)
    if args.limit:
        rng = np.random.default_rng(0)
        jobs = [jobs[k] for k in sorted(rng.choice(len(jobs), args.limit, replace=False))]
    K = len(names)
    other = next((c for c, n in names.items() if n == "other"), None)
    with ProcessPoolExecutor(args.workers) as pool:
        loaded = list(monitor.track(pool.map(load, [j[0] for j in jobs], chunksize=8), len(jobs), "games"))
    counts = Counter(clean_name(j[3]) for j in jobs)        # (a map with MAP_MIN games its own category, the rest one:
    maps = ["other map"] + sorted(m for m, c in counts.items() if c >= MAP_MIN)[:250]   # the trees take 255 at most)
    rows = defaultdict(list)
    for g, (job, res) in enumerate(zip(jobs, loaded)):
        if res is None:
            continue
        Xs, Xt, idx, reads, n, tech_seen = res
        modern = job[2].startswith("cwal/")
        m = maps.index(clean_name(job[3])) if clean_name(job[3]) in maps else 0
        for k in range(len(idx)):
            rows["Xs"].append(np.concatenate([Xs[k], [m]]))
            rows["Xt"].append(np.concatenate([Xt[k], [m]]))
            rows["t"].append(idx[k]); rows["g"].append(g); rows["y"].append(job[4]); rows["modern"].append(modern)
            rows["map"].append(m); rows["read"].append(reads[k]); rows["tech_seen"].append(tech_seen[k])
    A = {k: np.array(v) for k, v in rows.items()}
    games = np.unique(A["g"])
    modern_games = np.unique(A["g"][A["modern"]])
    rng = np.random.default_rng(0)
    fold_of = dict(zip(rng.permutation(modern_games), np.arange(len(modern_games)) % FOLDS))
    fold = np.array([fold_of.get(g, -1) for g in A["g"]])           # (-1: an old-era game, training only)
    w = np.where(A["modern"], MODERN_WEIGHT, 1.0)
    cat = np.zeros(A["Xs"].shape[1], bool)
    cat[-1] = True                                                   # (the map, a category)
    preds = {k: np.zeros((len(A["y"]), K)) for k in ("model", "ceiling", "floor")}
    scored = A["modern"] & np.isin(A["t"], [m * 60 for m in MINUTES])
    part_names = {k: v[1] for k, v in to_parts(np.eye(K), names).items()}
    tech_vals = part_names["tech"]
    read_tech = np.zeros((len(A["y"]), len(tech_vals)))
    for f in range(FOLDS):
        tr, te = fold != f, (fold == f) & scored
        for key, X in (("model", A["Xs"]), ("ceiling", A["Xt"])):
            clf = HistGradientBoostingClassifier(categorical_features=cat, **HGB)
            clf.fit(X[tr], A["y"][tr], sample_weight=w[tr])
            P = np.zeros((te.sum(), K))
            P[:, clf.classes_] = clf.predict_proba(X[te])
            preds[key][te] = P
        # the floor: modern shares on the map (else all maps) among the training folds' games running at that minute
        mtr = tr & A["modern"]
        for minute in MINUTES:
            at = A["t"] == minute * 60
            base = np.bincount(A["y"][mtr & at], minlength=K) + 0.5
            for m in np.unique(A["map"][te & at]):
                sel = mtr & at & (A["map"] == m)
                share = np.bincount(A["y"][sel], minlength=K) + 0.5 if sel.sum() >= FLOOR_MIN else base
                preds["floor"][te & at & (A["map"] == m)] = share / share.sum()
            # answers.py's read: the tech part's shares per read
            tech_of = np.array([tech_vals.index(parts(names[c])[2]) for c in A["y"]])
            for rd in ("none", "mutas", "lurkers"):
                sel = mtr & at & (A["read"] == rd)
                share = np.bincount(tech_of[sel], minlength=len(tech_vals)) + 0.5
                read_tech[te & at & (A["read"] == rd)] = share / share.sum()
    report = {"games": int(len(games)), "modern_games": int(len(modern_games)), "names": names, "minutes": {}}
    keep = scored & (A["y"] != other) if other is not None else scored
    for minute in MINUTES:
        sel = keep & (A["t"] == minute * 60)
        y, gsel = A["y"][sel], A["g"][sel]
        res = {"samples": int(sel.sum()), "games_running": int(len(np.unique(gsel)))}
        Pp = {k: preds[k][sel] for k in preds}
        res["joint"] = {k: {"brier": float(brier(P, y).mean()), "logloss": float(logloss(P, y).mean())} for k, P in Pp.items()}
        res["joint"]["model_minus_floor"] = boot(brier(Pp["model"], y) - brier(Pp["floor"], y), gsel)
        for part in ("opening", "hatcheries", "tech"):
            yp = np.array([part_names[part].index(parts(names[c])[("opening", "hatcheries", "tech").index(part)]) for c in y])
            Q = {k: to_parts(P, names)[part][0] for k, P in Pp.items()}
            if part == "tech":
                Q["answers"] = read_tech[sel]
            res[part] = {k: {"brier": float(brier(P, yp).mean()), "logloss": float(logloss(P, yp).mean())} for k, P in Q.items()}
            res[part]["model_minus_floor"] = boot(brier(Q["model"], yp) - brier(Q["floor"], yp), gsel)
            res[part]["shares"] = {v: float(np.mean(yp == i)) for i, v in enumerate(part_names[part])}
        res["no_tech_seen_share"] = float((sel & ~A["tech_seen"]).sum() / max(1, sel.sum()))
        report["minutes"][str(minute)] = res
    out = Path(args.out) if args.out else REPO / "runs" / "plan_belief" / f"{args.matchup}_{args.race}_{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    if args.save:
        clf = HistGradientBoostingClassifier(categorical_features=cat, **HGB)
        clf.fit(A["Xs"], A["y"], sample_weight=w)
        floors, tech = {}, {}
        for minute in MINUTES:                 # (the pros' floor per map and their tech seen, for --gary)
            at = A["modern"] & (A["t"] == minute * 60)
            share = lambda sel: ((np.bincount(A["y"][sel], minlength=K) + 0.5) / (sel.sum() + 0.5 * K)).tolist()
            floors[str(minute)] = {"all": share(at)}
            for mi, mname in enumerate(maps):
                if (at & (A["map"] == mi)).sum() >= FLOOR_MIN:
                    floors[str(minute)][mname] = share(at & (A["map"] == mi))
            tech[str(minute)] = float(A["tech_seen"][at].mean())
        pickle.dump({"model": clf, "maps": maps, "names": names, "floors": floors, "tech_seen": tech},
                    open(out / "model.pkl", "wb"))
    (out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for minute, res in report["minutes"].items():
        print(f"{minute}:00  {res['samples']} modern samples (other left out), no Zerg tech building seen yet in {res['no_tech_seen_share']:.0%}")
        for part in ("joint", "opening", "hatcheries", "tech"):
            r = res[part]
            cells = ", ".join(f"{k} {v['brier']:.3f}/{v['logloss']:.2f}" for k, v in r.items() if isinstance(v, dict) and "brier" in v)
            d = r["model_minus_floor"]
            print(f"  {part:10s} Brier/log-loss: {cells}; model - floor {d['mean']:+.3f} [{d['lo']:+.3f}, {d['hi']:+.3f}]")
    print(f"-> {out}")


def boot(diff: np.ndarray, games: np.ndarray) -> dict:
    """The mean difference and its 90% interval, games resampled."""
    rng = np.random.default_rng(1)
    ug, inv = np.unique(games, return_inverse=True)
    sums = np.bincount(inv, weights=diff)
    counts = np.bincount(inv)
    means = []
    for _ in range(BOOT):
        pick = rng.integers(0, len(ug), len(ug))
        means.append(sums[pick].sum() / counts[pick].sum())
    return {"mean": float(diff.mean()), "lo": float(np.percentile(means, 5)), "hi": float(np.percentile(means, 95))}


if __name__ == "__main__":
    main()

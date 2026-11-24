"""The enemy-plan belief, P(enemy plan | what the player has seen), offline (docs/REFOCUS.md §3.1, Phase 1's first
piece): how well the enemy's plan (taxonomy/plans.py: opening, hatcheries, first tech) can be told from a player's view
of it at a game minute, against what tells it without sightings.

Data: the macro training set (ingest/macro_dataset.py: every second of each pro game, what each player could see of the
other), from the player of --race against the matchup's other race, every SAMPLE seconds from FIRST to LAST; the
inputs (plan_features) are the belief model's view of the enemy (gary/policy/belief.py: game time, each enemy type in
sight now and the most in sight over 30 s, 90 s, 3 min and ever, seconds since an enemy army unit), the Lurker egg among
the types, the seconds since each type was first seen, and the map; not the player's own supply and workers (since
2026-11-23: a belief that reads the enemy's plan off the player's own build explains nothing);
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
Each with its calibration error (ECE: the top class's odds against its hit rate, in ECE_BINS bins).

Gary's own games (--gary) are labelled by the pros' rule (taxonomy/plans.py, taxonomy/label_all.py: the enemy's build
items from the replay's commands, first times to 9:00, Lurker Aspect by its research, zerglings ordered by 4:00), and
every comparator there is fitted on other games than it scores (the pros', or Gary's other games).

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
from gary.policy.plan_belief import LURKER_EGG  # noqa: E402

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
MUTALISK, LURKER = 43, 103
TECH_BUILDINGS = [135, 137, 141]   # a Hydralisk Den, a Greater Spire or a Spire: a sight of the enemy's tech (a Lair or a
                                   # Hive tells no plan: counted as tech until 2026-11-23, docs/REFOCUS.md §3.1)
ECE_BINS = 10


from gary.policy.plan_belief import FIRST_CAP, plan_features  # noqa: E402,F401  (the inputs, the same in play)


def ece(P: np.ndarray, y: np.ndarray, bins: int = ECE_BINS) -> float:
    """Expected calibration error of the top class: |its mean odds - its hit rate| per bin, weighted by the bin's share."""
    top, hit = P.max(1), (P.argmax(1) == y)
    k = np.minimum((top * bins).astype(int), bins - 1)
    return float(sum(abs(top[k == b].mean() - hit[k == b].mean()) * (k == b).mean() for b in range(bins) if (k == b).any()))


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
    Xs = plan_features(seen, frames, enemy)
    Xt = plan_features(true, frames, enemy)
    idx = np.arange(FIRST, min(n, LAST + 1), SAMPLE)
    ever = np.maximum.accumulate(seen.astype(np.int32), axis=0)
    reads = [answers_read(ever[t]) for t in idx]
    tech_seen = ever[idx][:, TECH_BUILDINGS].sum(1) > 0
    return Xs[idx], Xt[idx], idx, reads, n, tech_seen


def enemy_plan(replay: str, enemy: str, matchup: str, name: str, duration_s: float) -> str | None:
    """The enemy's plan in one of Gary's replays by the pros' rule (taxonomy/label_all.py: its build items from the
    replay's commands, ingest/build_orders.py), the player of that name (the re-simulator's slots are start slots,
    screp's ids the players' order: they differ), or None."""
    import hashlib
    import tempfile
    sys.path.insert(0, str(REPO / "taxonomy"))
    from build_orders import extract_player
    from cmdcache import P, load_game
    from discover import first_times
    from inventory import find_screp
    from label_all import P_TECH_BY, protoss_plan, terran_plan, zerg_plan
    cache = Path(tempfile.gettempdir()) / "gary_plan_cmds"
    game = load_game(find_screp(None), Path(replay), hashlib.sha1(replay.encode()).hexdigest(), cache)
    p = next((q for q in game["players"] if not q["observer"] and q["name"] == name), None)
    if p is None or p["race"] != enemy:
        return None
    items = extract_player([c for c in game["cmds"] if c[P] == p["id"]], enemy)[0]
    row = {"items": items, "duration_s": duration_s}
    if enemy == "Z":
        return zerg_plan(row, matchup)
    if enemy == "P":
        return protoss_plan(first_times(items, "P", P_TECH_BY), duration_s)
    return terran_plan(row)


def gary_game(job: tuple):
    """One of Gary's league games re-simulated (eval/league.py's replays, as train/value.py league_game reads them):
    the player of race's view at the samples, as load(), and the enemy's plan by the pros' rule (enemy_plan). In a
    mirror Gary's side is A, the lower slot (eval/style_adherence.py). (Xs, idx, reads, tech_seen, plan, map, Gary's
    slot) or None."""
    from macro_dataset import RACES, game_arrays, run_resim
    replay, race, enemy, map_name, matchup = job
    try:
        lines = run_resim(str(Path(replay).resolve()))
    except Exception:  # noqa: BLE001 - one bad replay must not stop the batch
        return None
    header = next((r for r in lines if r["type"] == "header"), None)
    d = game_arrays(lines) if header else None
    if d is None:
        return None
    races = {p["slot"]: RACES.get(p["race"]) for p in header["players"]}
    mine = sorted((k for k, sl in enumerate(d["slots"]) if races.get(sl) == race), key=lambda k: d["slots"][k])
    if not mine or races.get(d["slots"][1 - mine[0]]) != enemy:
        return None
    i = mine[0]
    frames, n = d["frames"], len(d["frames"])
    if n <= FIRST:
        return None
    seen = d["seen"][:, i]
    Xs = plan_features(seen, frames, enemy)
    idx = np.arange(FIRST, min(n, LAST + 1), SAMPLE)
    ever = np.maximum.accumulate(seen.astype(np.int32), axis=0)
    reads = [answers_read(ever[t]) for t in idx]
    tech_seen = ever[idx][:, TECH_BUILDINGS].sum(1) > 0
    try:
        name = next(p["name"] for p in header["players"] if p["slot"] == d["slots"][1 - i])
        plan = enemy_plan(replay, enemy, matchup, name, float(n))
    except Exception:  # noqa: BLE001
        return None
    return Xs[idx], idx, reads, tech_seen, plan, map_name, int(d["slots"][i])


def sight_job(job):
    """ingest/sighting_dataset.py's states for one game, or None (its failure is the reason, a string)."""
    from ingest.sighting_dataset import _job
    r = _job(job)
    return None if r is None or isinstance(r[1], str) else r


def sight_at(sg, t: int) -> np.ndarray:
    """A game's sighting features at second t (NaN without them)."""
    from gary.policy.sightings import N
    if sg is None:
        return np.full(N, np.nan, np.float32)
    k = np.where(sg[1] == t)[0]
    return sg[2][k[0]] if len(k) else np.full(N, np.nan, np.float32)


def is_looked(f: np.ndarray) -> bool:
    """Gate 1's split (docs/REFOCUS.md): the plan's tech seen by now, or the enemy's main known and looked at within
    LOOKED_WITHIN over half its area (the last look's cover: gary/policy/sightings.py features)."""
    from gary.policy.sightings import CAP
    if np.isnan(f).any():
        return False
    return bool(f[12] > 0 or (f[0] > 0 and f[1] * CAP <= LOOKED_WITHIN and f[2] >= 0.5))


LOOKED_WITHIN = 120           # s


def score_gary(model_dir: Path, rounds: list[str], race: str, matchup: str, workers: int) -> None:
    """The saved model (--save) on Gary's own games, labelled by the pros' rule: how often the enemy's tech was seen by
    each minute (Gary against the pros), and the model's Brier and calibration error against comparators fitted on
    other games: the pros' floor, answers.py's read with the pros' shares, and Gary's other games' plan shares (each
    game left out of its own)."""
    from ladder_maps import clean_name
    saved = pickle.load(open(model_dir / "model.pkl", "rb"))
    clf, maps, names, floors, pro_tech = saved["model"], saved["maps"], saved["names"], saved["floors"], saved["tech_seen"]
    enemy = enemy_of(matchup, race)
    ids = {v: k for k, v in names.items()}
    jobs = [(str(p), race, enemy, p.parent.name, matchup) for r in rounds
            for p in sorted((REPO / "runs" / "league" / r).rglob("*.rep"))]
    with ProcessPoolExecutor(workers) as pool:
        games = list(monitor.track(pool.map(gary_game, jobs), len(jobs), "Gary's games"))
        # (the sighting states for every model: the split by looked and unlooked reads them)
        sights = list(pool.map(sight_job, [(j[0], j[0], race, enemy, g[6] if g is not None else None)
                                           for j, g in zip(jobs, games)]))
    keep_g = [k for k, g in enumerate(games) if g is not None and g[4] is not None and sights[k] is not None]
    print(f"{len(keep_g)} of {len(jobs)} of Gary's games read (the rest: no re-simulation, no plan or no sightings)")
    games, sights = [games[k] for k in keep_g], [sights[k] for k in keep_g]
    other = next(k for k, v in names.items() if v == "other")
    ys = np.array([ids.get(g[4], other) for g in games])
    print(f"the enemy's plans (the pros' rule): {Counter(names[y] for y in ys).most_common(8)}")
    K = len(names)
    counts = np.bincount(ys, minlength=K).astype(float)
    tech_vals = sorted({parts(names[c])[2] for c in names})
    for minute in MINUTES:
        X, y, seen_tech, fl, own, rd, looked = [], [], [], [], [], [], []
        for g, yy, sg in zip(games, ys, sights):
            k = np.where(g[1] == minute * 60)[0]
            if not len(k):
                continue
            m = clean_name(g[5])
            extra = sight_at(sg, minute * 60) if saved.get("sightings") else []
            X.append(np.concatenate([g[0][k[0]], extra, [maps.index(m) if m in maps else 0]]))
            y.append(yy); seen_tech.append(g[3][k[0]]); fl.append(floors[str(minute)].get(m, floors[str(minute)]["all"]))
            loo = counts.copy()
            loo[yy] -= 1                                  # (Gary's other games' shares: this one left out)
            own.append((loo + 0.5) / (loo.sum() + 0.5 * K))
            rd.append(saved["read_tech"][str(minute)][g[2][k[0]]])
            looked.append(is_looked(sight_at(sg, minute * 60)))
        if not X:
            continue
        X, y, fl, own, rd, looked = np.array(X), np.array(y), np.array(fl), np.array(own), np.array(rd), np.array(looked)
        P = np.zeros((len(y), K))
        P[:, clf.classes_] = clf.predict_proba(X)
        keep = y != other
        yt = np.array([tech_vals.index(parts(names[c])[2]) for c in y])
        tech = lambda Q: Q @ np.array([[float(parts(names[c])[2] == v) for v in tech_vals] for c in range(K)])
        cell = lambda Q, yy: f"{brier(Q, yy).mean():.3f} (ECE {ece(Q, yy):.3f})"
        print(f"{minute}:00  {len(y)} games running; a Spire, Greater Spire or Den seen by then: Gary {np.mean(seen_tech):.0%}, "
              f"the pros {pro_tech[str(minute)]:.0%}")
        print(f"  joint Brier (other left out, {keep.sum()} games): model {cell(P[keep], y[keep])}, the pros' floor "
              f"{cell(fl[keep], y[keep])}, Gary's other games' shares {cell(own[keep], y[keep])}")
        print(f"  tech Brier: model {cell(tech(P)[keep], yt[keep])}, the pros' floor {cell(tech(fl)[keep], yt[keep])}, "
              f"answers.py's read {cell(rd[keep], yt[keep])}, Gary's other games' shares {cell(tech(own)[keep], yt[keep])}")
        # the model's odds over the pros' floor as a likelihood ratio, times the suite's prior (Gary's other games'
        # shares): what is left of its error once the pros' prior (a Spire in nine games of ten) is taken out
        adj = P * own / np.clip(fl, 1e-6, None)
        adj /= adj.sum(1, keepdims=True)
        for name, m in (("looked", looked & keep), ("unlooked", ~looked & keep)):
            if not m.any():
                continue
            print(f"  {name} ({m.sum()} games): joint model {cell(P[m], y[m])}, prior-adjusted {cell(adj[m], y[m])}, "
                  f"the pros' floor {cell(fl[m], y[m])}, Gary's other games' shares {cell(own[m], y[m])}")
            print(f"  {' ' * len(name)} tech model {cell(tech(P)[m], yt[m])}, prior-adjusted {cell(tech(adj)[m], yt[m])}, "
                  f"the pros' floor {cell(tech(fl)[m], yt[m])}, Gary's other games' shares {cell(tech(own)[m], yt[m])}")


def enemy_of(matchup: str, race: str) -> str:
    """The other race of the matchup (in a mirror, the same)."""
    a, b = matchup.split("v")
    return b if a == race else a


def jobs_for(race: str, matchup: str):
    """(job, sha1, rel_path, map, plan id, the player's slot) for every game of the matchup whose enemy has a plan
    label."""
    from inventory import data_root
    enemy = enemy_of(matchup, race)
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
                            r.get("map", ""), int(assign[f"{r['rel_path']}|{e['name']}"]), p.get("slot")))
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
    ap.add_argument("--sightings", action="store_true",
                    help="with the sighting states (gary/policy/sightings.py; their dataset ingest/sighting_dataset.py "
                         "built first)")
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
    sights = None
    if args.sightings:                 # (gary/policy/sightings.py: where the player looked)
        from inventory import data_root
        sd = np.load(data_root() / "interim" / "sightings" / f"{args.matchup}_{args.race}.npz")
        sights = {(str(r), int(sl), int(t)): f for r, sl, t, f in zip(sd["rel_path"], sd["slot"], sd["t"], sd["features"])}
        # a game without its sighting states is left out, not filled with NaN: built for one era only, the missing
        # values told the trees the era (round two, docs/REFOCUS.md §3.1)
        have = {(r, sl) for r, sl, _ in sights}
        before = sum(1 for res in loaded if res is not None)
        loaded = [res if res is not None and (job[2], job[5]) in have else None for job, res in zip(jobs, loaded)]
        print(f"sighting states for {sum(1 for res in loaded if res is not None)} of {before} games")
    maps = ["other map"] + sorted(m for m, c in counts.items() if c >= MAP_MIN)[:250]   # the trees take 255 at most)
    rows = defaultdict(list)
    for g, (job, res) in enumerate(zip(jobs, loaded)):
        if res is None:
            continue
        Xs, Xt, idx, reads, n, tech_seen = res
        modern = job[2].startswith("cwal/")
        m = maps.index(clean_name(job[3])) if clean_name(job[3]) in maps else 0
        for k in range(len(idx)):
            if sights is not None and (job[2], job[5], int(idx[k])) not in sights:
                continue                   # (the game ended before this sample in the re-play)
            sx = sights[(job[2], job[5], int(idx[k]))] if sights is not None else []
            rows["Xs"].append(np.concatenate([Xs[k], sx, [m]]))
            rows["Xt"].append(np.concatenate([Xt[k], [m]]))
            rows["t"].append(idx[k]); rows["g"].append(g); rows["y"].append(job[4]); rows["modern"].append(modern)
            rows["map"].append(m); rows["read"].append(reads[k]); rows["tech_seen"].append(tech_seen[k])
    A = {k: np.array(v) for k, v in rows.items()}
    games = np.unique(A["g"])
    modern_games = np.unique(A["g"][A["modern"]])
    rng = np.random.default_rng(0)
    # folds by the replay (in a mirror both players' views of one game are two jobs, kept in one fold)
    rel_of = np.array([jobs[g][2] for g in A["g"]])
    modern_rels = np.unique(rel_of[A["modern"]])
    fold_of = dict(zip(rng.permutation(modern_rels), np.arange(len(modern_rels)) % FOLDS))
    fold = np.array([fold_of.get(r, -1) for r in rel_of])           # (-1: an old-era game, training only)
    w = np.where(A["modern"], MODERN_WEIGHT, 1.0)
    def cat(X):                                                     # (the map, a category: the last column of each)
        c = np.zeros(X.shape[1], bool)
        c[-1] = True
        return c
    preds = {k: np.zeros((len(A["y"]), K)) for k in ("model", "ceiling", "floor")}
    scored = A["modern"] & np.isin(A["t"], [m * 60 for m in MINUTES])
    part_names = {k: v[1] for k, v in to_parts(np.eye(K), names).items()}
    tech_vals = part_names["tech"]
    read_tech = np.zeros((len(A["y"]), len(tech_vals)))
    for f in range(FOLDS):
        tr, te = fold != f, (fold == f) & scored
        for key, X in (("model", A["Xs"]), ("ceiling", A["Xt"])):
            clf = HistGradientBoostingClassifier(categorical_features=cat(X), **HGB)
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
        res["joint"] = {k: {"brier": float(brier(P, y).mean()), "logloss": float(logloss(P, y).mean()), "ece": ece(P, y)}
                        for k, P in Pp.items()}
        res["joint"]["model_minus_floor"] = boot(brier(Pp["model"], y) - brier(Pp["floor"], y), gsel)
        for part in ("opening", "hatcheries", "tech"):
            yp = np.array([part_names[part].index(parts(names[c])[("opening", "hatcheries", "tech").index(part)]) for c in y])
            Q = {k: to_parts(P, names)[part][0] for k, P in Pp.items()}
            if part == "tech":
                Q["answers"] = read_tech[sel]
            res[part] = {k: {"brier": float(brier(P, yp).mean()), "logloss": float(logloss(P, yp).mean()), "ece": ece(P, yp)}
                         for k, P in Q.items()}
            res[part]["model_minus_floor"] = boot(brier(Q["model"], yp) - brier(Q["floor"], yp), gsel)
            res[part]["shares"] = {v: float(np.mean(yp == i)) for i, v in enumerate(part_names[part])}
        res["no_tech_seen_share"] = float((sel & ~A["tech_seen"]).sum() / max(1, sel.sum()))
        report["minutes"][str(minute)] = res
    out = Path(args.out) if args.out else REPO / "runs" / "plan_belief" / f"{args.matchup}_{args.race}_{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    if args.save:
        clf = HistGradientBoostingClassifier(categorical_features=cat(A["Xs"]), **HGB)
        clf.fit(A["Xs"], A["y"], sample_weight=w)
        floors, tech, read_saved = {}, {}, {}
        tech_of = np.array([tech_vals.index(parts(names[c])[2]) for c in A["y"]])
        for minute in MINUTES:                 # (the pros' floor per map, their tech seen and answers.py's read, for --gary)
            at = A["modern"] & (A["t"] == minute * 60)
            share = lambda sel: ((np.bincount(A["y"][sel], minlength=K) + 0.5) / (sel.sum() + 0.5 * K)).tolist()
            floors[str(minute)] = {"all": share(at)}
            for mi, mname in enumerate(maps):
                if (at & (A["map"] == mi)).sum() >= FLOOR_MIN:
                    floors[str(minute)][mname] = share(at & (A["map"] == mi))
            tech[str(minute)] = float(A["tech_seen"][at].mean())
            read_saved[str(minute)] = {}
            for rd in ("none", "mutas", "lurkers"):
                c = np.bincount(tech_of[at & (A["read"] == rd)], minlength=len(tech_vals)) + 0.5
                read_saved[str(minute)][rd] = (c / c.sum()).tolist()
        pickle.dump({"model": clf, "maps": maps, "names": names, "floors": floors, "tech_seen": tech,
                     "read_tech": read_saved, "sightings": bool(args.sightings)},
                    open(out / "model.pkl", "wb"))
    (out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for minute, res in report["minutes"].items():
        print(f"{minute}:00  {res['samples']} modern samples (other left out), no Zerg tech building seen yet in {res['no_tech_seen_share']:.0%}")
        for part in ("joint", "opening", "hatcheries", "tech"):
            r = res[part]
            cells = ", ".join(f"{k} {v['brier']:.3f}/{v['logloss']:.2f}/{v['ece']:.3f}" for k, v in r.items()
                              if isinstance(v, dict) and "brier" in v)
            d = r["model_minus_floor"]
            print(f"  {part:10s} Brier/log-loss/ECE: {cells}; model - floor {d['mean']:+.3f} [{d['lo']:+.3f}, {d['hi']:+.3f}]")
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

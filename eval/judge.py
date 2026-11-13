"""The judge: would a pro's unit be in this state here, and is Gary's? (An ability judged per situation, not by its
count a game: how often a tank should be sieged depends on what the enemy does, and Gary's enemies aren't the pros'.)

A model learns from the pros' fight moments (the response datasets, ingest/response_dataset.py: every half second
with a seen enemy fighter near the player's units) whether a unit that has a mode is in it: a Siege Tank sieged.
Its inputs are the situation around the unit with every own unit's mode hidden (no type in or out of the mode, no
order, cooldown or motion: a sieged tank's neighbours are sieged, and a judge that read them would agree with a Gary
that never sieges): the enemy fighters near it by distance and by kind, their buildings and static defense, its own
fighters, tanks and buildings near, its HP, the ground under it and the minute. It is not Gary's role model: other
inputs, another kind of model (boosted trees), and games held out to check it on (by game: its odds against what the
held-out pros did, bin by bin, is its calibration).

Gary's moments are built from its league games' replays by the dataset's own code, so both are counted alike. Read:
the pros' held-out games lie on the diagonal (in the bin where the judge says 70%, 70% of their tanks are sieged);
Gary's line against it is the measure, summed as "in the state x% of its unit-moments, a pro y% in the same
situations", with a 90% interval from resampling Gary's games. Coverage: a second model tells Gary's situations from
the pros'; the share it is sure are Gary's (situations the pros aren't in) is reported, and the measure again
without them.

    python -m eval.judge --race T --matchup TvZ --rounds TW253a
    python -m eval.judge --race T --matchup PvT --rounds PT245a
    python -m eval.judge --race T --matchup TvT --rounds TT246a --retrain
    python -m eval.judge --table                       # every round judged so far, matchup by ability

Each round judged appends a line to runs/judge/results.jsonl (the judge, the round, Gary's share, a pro's, the
difference with its interval, the ranking, the coverage); --table prints them, the newest line per cell.

The judge is kept in runs/judge/<race>_<matchup>_<state>.pkl; a round's moments in its folder (judge_<race>.npz).
A state is a row of STATES (the unit type out of the mode and in it); the pros' dataset per matchup is PROS.
"""
from __future__ import annotations

import argparse
import json
import pickle
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from eval import monitor, priority  # noqa: E402
from gary.policy.modes import (FAR, HISTORY, KINDS, SPELL_MAX, TILE, enemy_kinds, features, history,  # noqa: E402,F401
                               names, tables)

STATES = {"T": {"siege": (5, 30, "Siege Mode", 1200)}}    # race -> state -> (type out, type in, its research, frames)
# (a burrowed Lurker, a cloaked Wraith, a Marine in a bunker are states too, but the re-simulator's observation
# reports no burrowed or cloaked flag and no loaded units: those come once it does)
# race -> event -> (the unit types, the command as the re-simulator names it, its order id (an "order" command) or
# None, its research's tech id (None: none needed) and frames)
EVENTS = {"T": {"stim": ({0, 32}, "stim", None, 0, 1200),
                "mine": ({2}, "order", 132, 3, 1200)},      # a Vulture lays a Spider Mine (gary/commands.py)
          # a Lurker's burrow and unburrow (no research; a burrowed one is a candidate for burrow too, so the pros'
          # hazard is lower than their choice: a difference the wrong way reads as Gary's, one this way is understated)
          "Z": {"burrow": ({103}, "burrow", None, None, 0), "unburrow": ({103}, "unburrow", None, None, 0)},
          # Psionic Storm (gary/policy/cast.py's spell: order 142, tech 19): the judge doesn't read energy (the
          # observation has none), so a High Templar without 75 energy is a candidate too; "seconds since its last
          # such command" stands in for it
          "P": {"storm": ({67}, "order", 142, 19, 1800)}}
WINDOW = 3.0                    # seconds: an event judged as "a pro acts within this long"
EVENT_HISTORY = ["seconds since its last such command", "seconds since its last command"]
PROS = {("T", "TvZ"): "response_T_30min.npz", ("T", "PvT"): "response_T_PvT_modes_30min.npz",
        ("T", "TvT"): "response_T_TvT_30min.npz", ("Z", "TvZ"): "response_Z_30min.npz",
        ("P", "PvT"): "response_P_PvT_30min.npz", ("P", "PvZ"): "response_P_PvZ_30min.npz",
        ("P", "PvP"): "response_P_PvP_30min.npz"}
BINS = 10
BOOT = 200
MAX_TRAIN = 400_000             # rows: half-second neighbours say the same thing
SURE = 0.9                      # the coverage model's odds a situation is Gary's: outside the pros' above this


def situations(m: dict, what: tuple, judge: dict):
    """A dataset's judged unit-moments as the judge reads them: (X, y, snapshot index, game). what: a STATES row
    (the state's types, its y the type in the mode) or an EVENTS row (its y from the commands, with the unit's own
    command history as inputs; only units after the research, and the moments its game's commands were read)."""
    event = isinstance(what[1], str)
    types, into = (what[0], -1) if event else ({what[0], what[1]}, what[1])
    X, y, s, tag = features(m["rows"], m["extra"], m["count"], m["time"], m["tags"], types, judge["kinds"], into)
    game, time = m["game"][s], m["time"][s]
    if judge.get("history") and len(X):
        X = np.concatenate([X, history(X, names(judge["kinds"]), game, tag, time)], 1)
    if event and len(X):
        y, hist, keep = event_labels(m["commands"], what, game, tag, time)
        X, y, s, game = np.concatenate([X, hist], 1)[keep], y[keep], s[keep], game[keep]
    return X, y, s, game


def event_labels(commands: dict, what: tuple, game, tag, time):
    """(y, the unit's command history (EVENT_HISTORY), keep) per judged unit-moment: y, whether the player gave the
    unit the event's command within WINDOW seconds after the moment; keep, the moments after the research is done
    whose game's commands were read."""
    import bisect
    _, cmd, order_id, tech, frames = what
    y = np.zeros(len(tag), bool)
    hist = np.full((len(tag), len(EVENT_HISTORY)), SPELL_MAX, np.float32)
    keep = np.zeros(len(tag), bool)
    by_game = {}
    for i in np.argsort(game, kind="stable"):
        g = int(game[i])
        if g not in by_game:
            c = commands.get(g)
            if c is None:
                by_game[g] = None
                continue
            done = 0 if tech is None else min((f for f, t in c["research"] if t == tech), default=None)
            by_tag, by_tag_cmd = {}, {}
            for f, name, order, _target, units in c["ucmd"]:
                for u in units:
                    by_tag.setdefault(u, []).append(f)
                    if name == cmd and (order_id is None or order == order_id):
                        by_tag_cmd.setdefault(u, []).append(f)
            by_game[g] = (done, by_tag, by_tag_cmd)
        got = by_game[g]
        if got is None:
            continue
        done, by_tag, by_tag_cmd = got
        f = int(round(time[i] * 1000 / 42))
        if done is None or f < done + (0 if tech is None else frames):
            continue
        keep[i] = True
        t = int(tag[i])
        fs = by_tag_cmd.get(t, [])
        k = bisect.bisect_right(fs, f)
        y[i] = k < len(fs) and fs[k] <= f + WINDOW * 24
        if k:
            hist[i, 0] = min((f - fs[k - 1]) / 24, SPELL_MAX)
        fa = by_tag.get(t, [])
        ka = bisect.bisect_right(fa, f)
        if ka:
            hist[i, 1] = min((f - fa[ka - 1]) / 24, SPELL_MAX)
    return y, hist, keep


def fit(X, y, seed: int = 0):
    from sklearn.ensemble import HistGradientBoostingClassifier
    rng = np.random.default_rng(seed)
    keep = rng.choice(len(X), MAX_TRAIN, replace=False) if len(X) > MAX_TRAIN else np.arange(len(X))
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                          random_state=seed).fit(X[keep], y[keep])


def train(race: str, matchup: str, state: str, pros: str | None, with_history: bool = True, workers: int = 4) -> dict:
    """The judge of one state or event from the pros' dataset, a fifth of its games held out; its held-out odds
    kept."""
    from sklearn.metrics import roc_auc_score
    path = REPO / "data" / "interim" / "roles" / (pros or PROS[(race, matchup)])
    d = np.load(path)
    kinds = enemy_kinds(d["rows"], d["count"])
    judge = {"kinds": kinds, "history": with_history, "event": state in EVENTS.get(race, {})}
    if not judge["event"] and state not in STATES.get(race, {}):
        raise SystemExit(f"{race} has no state or event {state!r}")
    m = {k: d[k] for k in ("rows", "extra", "count", "time", "tags", "game")}
    what = EVENTS[race][state] if judge["event"] else STATES[race][state]
    if judge["event"]:
        sys.path.insert(0, str(REPO / "ingest"))
        m["commands"] = commands_of(pro_paths(d["sha1"]), m, REPO / "runs" / "judge" / f"cmds_{path.stem}.pkl",
                                    workers, path.stem)
    X, y, s, game = situations(m, what, judge)
    games = np.unique(d["game"])
    held = set(random.Random(0).sample(sorted(games.tolist()), max(1, len(games) // 5)))
    test = np.isin(game, sorted(held))
    model = fit(X[~test], y[~test])
    p = model.predict_proba(X[test])[:, 1]
    judge.update(model=model, pros=path.name,
                 names=names(kinds) + (HISTORY if with_history else []) + (EVENT_HISTORY if judge["event"] else []),
                 games=len(games), held_games=len(held), held_p=p.astype(np.float32), held_y=y[test],
                 held_X=X[test], held_game=game[test], auc=float(roc_auc_score(y[test], p)), rows=int((~test).sum()))
    out = REPO / "runs" / "judge"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{race}_{matchup}_{state}.pkl", "wb") as f:
        pickle.dump(judge, f)
    return judge


def _moments(job: tuple) -> dict:
    """One league game's fight moments for the race's side, as the pros' dataset builds them."""
    sys.path.insert(0, str(REPO / "ingest"))                 # (the dataset's builders import each other by name)
    from ingest.response_dataset import _job
    path, race = job
    got = _job((path, None, path, race, None, False))
    return {"path": path, "error": got["error"], "rows": got["rows"], "extra": got["extra"], "time": got["time"],
            "tags": got["tags"]}


def read_commands(path: str) -> dict | None:
    """One game's unit commands and research, from the re-simulator (ingest/response_dataset.py _commands, kept
    whole): {"ucmd": [(frame, slot, cmd, order, target, units)], "research": [(frame, slot, tech id)]}."""
    import subprocess
    from ingest.inventory import data_root
    from ingest.macro_dataset import resim_exe
    from ingest.response_dataset import MAX_MIN
    sys.path.insert(0, str(REPO / "resim"))
    import scr_format
    data = Path(path).read_bytes()
    args = [str(resim_exe()), "--data", str(data_root() / "gamedata" / "scr"), "--replay", "-", "--every", "0",
            "--fights", str(MAX_MIN * 60)]
    if scr_format.replay_format(data) != "legacy":
        args += ["--flat", "--unit-limit", str(scr_format.unit_limit(data))]
        data = scr_format.to_flat(data)
    try:
        proc = subprocess.run(args, input=data, capture_output=True, timeout=1800)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    out = {"ucmd": [], "research": []}
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        if '"ucmd"' in line:
            r = json.loads(line)
            out["ucmd"].append((r["frame"], r["slot"], r["cmd"], r["order"], r["target"], r["units"]))
        elif '"research"' in line and '"cmd"' in line:
            r = json.loads(line)
            out["research"].append((r["frame"], r["slot"], r["id"]))
    return out


def _commands_job(job: tuple) -> tuple:
    sys.path.insert(0, str(REPO / "ingest"))
    key, path = job
    return key, read_commands(path)


def side_commands(got: dict | None, own_tags: set) -> dict | None:
    """One side's commands: the slot whose commands name the side's own units."""
    if got is None:
        return None
    hits = {}
    for f, slot, cmd, order, target, units in got["ucmd"]:
        hits[slot] = hits.get(slot, 0) + sum(1 for u in units if u in own_tags)
    if not hits:
        return {"ucmd": [], "research": []}
    slot = max(hits, key=hits.get)
    return {"ucmd": [(f, c, o, t, u) for f, sl, c, o, t, u in got["ucmd"] if sl == slot],
            "research": [(f, t) for f, sl, t in got["research"] if sl == slot]}


def commands_of(paths: dict, m: dict, cache: Path, workers: int, label: str) -> dict:
    """{game index: the side's commands} for a dataset's games (paths: game index -> replay path), built once."""
    if cache.exists():
        with open(cache, "rb") as f:
            return pickle.load(f)
    own = {}
    valid = np.arange(m["rows"].shape[1])[None, :] < m["count"][:, None]
    for g in np.unique(m["game"]):
        at = m["game"] == g
        own[int(g)] = set(np.asarray(m["tags"])[at][valid[at] & (m["rows"][at][:, :, 1] == 1)].tolist())
    out = {}
    jobs = [(g, p) for g, p in paths.items() if g in own]
    with ProcessPoolExecutor(workers, initializer=priority.apply, initargs=("low",)) as pool:
        for g, got in monitor.track(pool.map(_commands_job, jobs), len(jobs), f"{label}: commands"):
            out[g] = side_commands(got, own[g])
    with open(cache, "wb") as f:
        pickle.dump(out, f)
    return out


def pro_paths(sha1s) -> dict:
    """game index -> replay path, for a pros' dataset (its sha1 per game, the re-simulation index's paths)."""
    from ingest.inventory import data_root
    rel = {}
    for line in open(data_root() / "interim" / "resim_index.jsonl", encoding="utf-8"):
        r = json.loads(line)
        rel[r["sha1"]] = r["rel_path"]
    return {i: str(data_root() / "raw" / rel[s]) for i, s in enumerate(sha1s) if s in rel}


def research_done(replay: str, what: str, frames: int) -> float | None:
    """When (seconds) the side has the research, from the game's records: its macro decision and the time it takes
    (in a mirror both sides' records carry the race: the later one, so both have it)."""
    rec = Path(replay).with_suffix(".records.jsonl")
    if not rec.exists():
        return None
    at = []
    for line in open(rec, encoding="utf-8"):
        if f'"{what}"' not in line:
            continue
        r = json.loads(line)
        if r.get("kind") == "decision" and r.get("choice") == what:
            at.append(r["f"])
    return (max(at) + frames) * 42 / 1000 if at else None


def round_moments(name: str, race: str, workers: int) -> dict:
    """A round's fight moments (rows, extra, count, time, game: the index into its replays), built once and kept in
    its folder."""
    from gary.policy.roles import MAX_UNITS
    out = REPO / "runs" / "league" / name
    cache = out / f"judge_{race}_v2.npz"            # (v2: the unit tags, for the history)
    if cache.exists():
        d = np.load(cache, allow_pickle=True)
        return {k: d[k] for k in d.files}
    table = json.loads((out / "round.json").read_text(encoding="utf-8"))
    replays = [g["replay"] for g in table["games"] if g["result"] != "error"]
    rows, extra, time, tags, game, failed = [], [], [], [], [], 0
    with ProcessPoolExecutor(workers, initializer=priority.apply, initargs=("low",)) as pool:
        for i, got in enumerate(monitor.track(pool.map(_moments, [(p, race) for p in replays]), len(replays),
                                              f"{name}: fight moments")):
            if got["error"]:
                print(f"  {Path(got['path']).parent.name}/{Path(got['path']).name}: {got['error']}", file=sys.stderr)
                failed += 1
                continue
            rows += got["rows"]
            extra += got["extra"]
            time += got["time"]
            tags += got["tags"]
            game += [i] * len(got["rows"])

    def pad(a, width, dtype):
        z = np.zeros((MAX_UNITS, width), dtype)
        a = np.asarray(a)[:MAX_UNITS]
        if a.size:
            z[:len(a), :min(width, a.shape[1])] = a[:, :width]
        return z

    got = {"rows": np.stack([pad(r, 11, np.int16) for r in rows]) if rows else np.zeros((0, MAX_UNITS, 11), np.int16),
           "extra": (np.stack([pad(e, 14, np.float32) for e in extra]) if rows
                     else np.zeros((0, MAX_UNITS, 14), np.float32)),
           "count": np.array([min(len(r), MAX_UNITS) for r in rows], np.int32),
           "time": np.array(time, np.float32), "game": np.array(game, np.int32), "replays": np.array(replays),
           "tags": (np.stack([np.pad(np.asarray(t, np.int64)[:MAX_UNITS], (0, MAX_UNITS - min(len(t), MAX_UNITS)))
                              for t in tags]) if rows else np.zeros((0, MAX_UNITS), np.int64))}
    if failed:                                               # (not kept: a rerun builds them all)
        print(f"  {name}: {failed} of {len(replays)} replays couldn't be read", file=sys.stderr)
    else:
        np.savez_compressed(cache, **got)
    return got


def table(p, y, edges):
    """Per bin of the judge's odds: how many, and the share in the state."""
    b = np.clip(np.digitize(p, edges) - 1, 0, len(edges) - 2)
    return [(int((b == i).sum()), float(y[b == i].mean()) if (b == i).any() else float("nan"))
            for i in range(len(edges) - 1)]


def spread(p, y, game, rng) -> tuple[float, float]:
    """The 90% interval of (the share in the state) - (the judge's mean odds), games resampled."""
    ids = np.unique(game)
    by = {g: (y[game == g].sum(), p[game == g].sum(), (game == g).sum()) for g in ids}
    d = []
    for _ in range(BOOT):
        pick = [by[g] for g in rng.choice(ids, len(ids))]
        d.append((sum(x[0] for x in pick) - sum(x[1] for x in pick)) / max(sum(x[2] for x in pick), 1))
    lo, hi = np.percentile(d, [5, 95])
    return float(lo), float(hi)


def shape(p, y, pros: list, edges, pros_auc: float) -> str:
    """Whether Gary is in the state where the pros are, not only as often: how far its share stands from the pros'
    in the bins of the judge's odds (points, weighted by Gary's moments), and how well the judge's odds rank Gary's
    own moments (the pros': the judge's held-out AUC; 0.5: Gary's state has nothing to do with the situation)."""
    from sklearn.metrics import roc_auc_score
    mine = table(p, y, edges)
    off = sum(n * abs(share - pros[i][1]) for i, (n, share) in enumerate(mine) if n and pros[i][0]) / max(len(y), 1)
    rank = f"{roc_auc_score(y, p):.3f}" if 0 < y.mean() < 1 else "none (never, or always, in the state)"
    return (f"where: off the pros' line by {off:.1%} a moment over the judge's bins; the judge's odds rank its "
            f"moments with AUC {rank} (the pros' {pros_auc:.3f})")


def line(label: str, k, p, y, game, rng) -> str:
    if not k.any():
        return f"    {label}: none"
    lo, hi = spread(p[k], y[k], game[k], rng)
    return (f"    {label}: in the state {y[k].mean():.1%} of {int(k.sum()):,} unit-moments "
            f"({len(np.unique(game[k]))} games), a pro {p[k].mean():.1%} in the same situations "
            f"(difference {y[k].mean() - p[k].mean():+.1%} [{lo:+.1%}, {hi:+.1%}])")


def coverage(judge: dict, X, game, rng):
    """Gary's situations told from the pros' held-out ones: (AUC, the mask of Gary's rows read and not surely
    Gary's, the share surely Gary's, the inputs that differ most). Half of each side's games fit, the other half is
    read (by game: half-second neighbours on both sides let it know the games, and tell them apart perfectly)."""
    from sklearn.metrics import roc_auc_score
    hx, hg = judge["held_X"], judge["held_game"]

    def halves(ids):
        ids = rng.permutation(np.unique(ids))
        return ids[:len(ids) // 2], ids[len(ids) // 2:]

    (pf, pr), (gf, gr) = halves(hg), halves(game)
    if not len(gf) or not len(pf):
        return float("nan"), np.zeros(len(X), bool), float("nan"), []
    a_fit, a_read = hx[np.isin(hg, pf)], hx[np.isin(hg, pr)]
    fit_g, read_g = np.flatnonzero(np.isin(game, gf)), np.flatnonzero(np.isin(game, gr))
    n = min(len(a_fit), len(fit_g))                               # (as many of each: its odds read as a share)
    cov = fit(np.concatenate([a_fit[rng.choice(len(a_fit), n, replace=False)], X[rng.choice(fit_g, n, replace=False)]]),
              np.concatenate([np.zeros(n), np.ones(n)]))
    q, qa = cov.predict_proba(X[read_g])[:, 1], cov.predict_proba(a_read)[:, 1]
    auc = roc_auc_score(np.concatenate([np.zeros(len(qa)), np.ones(len(q))]), np.concatenate([qa, q]))
    inside = np.zeros(len(X), bool)
    inside[read_g[q <= SURE]] = True
    apart = sorted(zip(np.abs(X[read_g].mean(0) - a_read.mean(0)) / (a_read.std(0) + 1e-6), judge["names"]),
                   reverse=True)[:4]
    return float(auc), inside, float(np.mean(q > SURE)), apart


RESULTS = REPO / "runs" / "judge" / "results.jsonl"


def record(row: dict) -> None:
    import time as clock
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": clock.strftime("%Y-%m-%d %H:%M"), **row}) + "\n")


def print_table() -> None:
    """Every (race, matchup, state) judged: its newest round's line."""
    if not RESULTS.exists():
        print("nothing judged yet"); return
    rows = {}
    for line in open(RESULTS, encoding="utf-8"):
        r = json.loads(line)
        rows[(r["race"], r["matchup"], r["state"])] = r
    print(f"{'race':>4} {'matchup':>7} {'ability':>9} {'round':>8} {'games':>5} {'moments':>8} {'Gary':>6} {'a pro':>6} "
          f"{'difference [90%]':>22} {'rank (pros)':>12} {'outside':>7}   where")
    for k in sorted(rows):
        r = rows[k]
        rank = f"{r['rank']:.2f}" if r.get("rank") is not None else "never"
        print(f"{r['race']:>4} {r['matchup']:>7} {r['state']:>9} {r['round']:>8} {r['games']:>5} {r['moments']:>8,} "
              f"{r['gary']:>6.1%} {r['pro']:>6.1%} {r['diff']:>+7.1%} [{r['lo']:+.1%}, {r['hi']:+.1%}] "
              f"{rank:>5} ({r['pros_auc']:.2f}) {r['outside']:>7.0%}   {r['apart']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--race", choices=sorted(set(STATES) | set(EVENTS)), help="whose units are judged")
    ap.add_argument("--matchup", help="the pros it is judged against (TvZ, PvT, TvT...)")
    ap.add_argument("--table", action="store_true", help="print every round judged so far and exit")
    ap.add_argument("--state", help="a state or an event (STATES, EVENTS); default: every one the race has")
    ap.add_argument("--rounds", nargs="*", default=[], help="Gary's league rounds (none: the judge's own check only)")
    ap.add_argument("--pros", help="the pros' dataset in data/interim/roles (default: PROS)")
    ap.add_argument("--retrain", action="store_true")
    ap.add_argument("--no-history", action="store_true", help="the judge without the unit's recent past (HISTORY)")
    ap.add_argument("--workers", type=int, default=4)
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    if args.table:
        print_table(); return
    if not args.race or not args.matchup:
        ap.error("--race and --matchup are required (or --table)")
    edges = np.linspace(0, 1, BINS + 1)
    rng = np.random.default_rng(0)
    for state in ([args.state] if args.state else sorted(STATES.get(args.race, {})) + sorted(EVENTS.get(args.race, {}))):
        event = state in EVENTS.get(args.race, {})
        pair = EVENTS[args.race][state] if event else STATES[args.race].get(state)
        if pair is None:
            raise SystemExit(f"{args.race} has no state or event {state!r}")
        kept = REPO / "runs" / "judge" / f"{args.race}_{args.matchup}_{state}.pkl"
        if kept.exists() and not args.retrain and not args.no_history:
            with open(kept, "rb") as f:
                judge = pickle.load(f)
        else:
            judge = train(args.race, args.matchup, state, args.pros, not args.no_history, args.workers)
        hp, hy = judge["held_p"], judge["held_y"]
        lo, hi = spread(hp, hy, judge["held_game"], rng)
        print(f"{state}, {args.race} in {args.matchup}: the judge from {judge['games'] - judge['held_games']} pro games "
              f"({judge['rows']:,} unit-moments, {judge['pros']}), {len(judge['names'])} inputs; held out "
              f"{judge['held_games']} games: AUC {judge['auc']:.3f}")
        print(f"  the pros held out: in the state {hy.mean():.1%} of {len(hy):,} unit-moments, the judge expects "
              f"{hp.mean():.1%} (difference {hy.mean() - hp.mean():+.1%} [{lo:+.1%}, {hi:+.1%}])")
        arms = []
        for name in args.rounds:
            m = round_moments(name, args.race, args.workers)
            if event:
                sys.path.insert(0, str(REPO / "ingest"))
                m["commands"] = commands_of({i: str(r) for i, r in enumerate(m["replays"])}, m,
                                            REPO / "runs" / "league" / name / f"judge_cmds_{args.race}.pkl",
                                            args.workers, name)
            X, y, s, game = situations(m, pair, judge)
            if not len(X):
                print(f"  {name}: no unit of the state's types in a fight moment")
                continue
            p = judge["model"].predict_proba(X)[:, 1]
            if event:
                has = np.ones(len(y), bool)                       # (an event's moments are after its research already)
            else:
                since = {i: research_done(str(r), pair[2], pair[3]) for i, r in enumerate(m["replays"])}
                has = np.array([since.get(int(g)) is not None and m["time"][k] >= since[int(g)] for g, k in zip(game, s)])
            arms.append((name, X, y, p, game, has))
        print(f"  {'the judge says':>15} {'pros':>9} {'in it':>6}" + "".join(f" | {a[0]:>9} {'in it':>6}" for a in arms))
        tabs = [table(hp, hy, edges)] + [table(a[3], a[2], edges) for a in arms]
        for i in range(BINS):
            cells = [f"{t[i][0]:>9,} {'' if t[i][0] == 0 else format(t[i][1], '.0%'):>6}" for t in tabs]
            print(f"  {f'{edges[i]:.0%}-{edges[i + 1]:.0%}':>15} " + " | ".join(cells))
        for name, X, y, p, game, has in arms:
            print(f"  {name}:")
            print(line("every moment", np.ones(len(y), bool), p, y, game, rng))
            print("    " + shape(p, y, tabs[0], edges, judge["auc"]))
            if not event:
                print(line(f"with {pair[2]} its own (the records)", has, p, y, game, rng))
            auc, inside, sure, apart = coverage(judge, X, game, rng)
            print(f"    coverage: Gary's situations told from the pros' with AUC {auc:.3f}; {sure:.0%} of them surely "
                  f"Gary's (odds over {SURE:.0%}: the pros aren't in these)")
            print(line("the situations the pros are in too (the half of its games read)", inside, p, y, game, rng))
            print("    where Gary's situations differ most (its mean against the pros', in the pros' sd): "
                  + "; ".join(f"{nm} {v:.1f}" for v, nm in apart))
            from sklearn.metrics import roc_auc_score
            lo, hi = spread(p, y, game, rng)
            record({"race": args.race, "matchup": args.matchup, "state": state, "round": name,
                    "games": int(len(np.unique(game))), "moments": int(len(y)), "gary": float(y.mean()),
                    "pro": float(p.mean()), "diff": float(y.mean() - p.mean()), "lo": lo, "hi": hi,
                    "rank": float(roc_auc_score(y, p)) if 0 < y.mean() < 1 else None, "pros_auc": judge["auc"],
                    "outside": sure, "apart": "; ".join(f"{nm} {v:.1f}" for v, nm in apart[:2])})


if __name__ == "__main__":
    main()

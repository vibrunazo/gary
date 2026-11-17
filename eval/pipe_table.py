"""What a model asks against what Gary carried out, for every drawn decision (TODO.md Direction b): the check that
found the week's faults (a decoder's turns, the trainer's weights in a draw, the motor unsieging, a selection's spill),
as one table per side.

The fight layer, per unit and half second. A round's fight moments for one side are built as the pros' were for the
role model (ingest/response_dataset.py, kept as pipe_<race>.npz in the round's folder) and labelled as train/roles.py
labels its decisions: the role each unit took over the next half second, from its order and its motion, "keep" where
it didn't change. At each of those moments the side's models give their odds as play computes them: the role model's
(with option rates the trainer's weights taken out, RoleModel.rates), and with modemodel and minemodel the mode and
event models' odds put in for the units of their types (gary/agent/roles.py _with_hazard), each a half second's.
Per decision:

  units      the labelled unit-moments it is asked over (a mode's or an event's: its unit types, once researched)
  raw        the role model's own odds, summed, as a share of them (before the decoder: the weights in, no mode model)
  asked      the odds play draws from, summed, as a share (what a unit drawn every half second would take)
  made       the share labelled with it
  made/asked
  by fifths  the unit-moments sorted by their asked odds, five equal groups: each one's mean odds -> share made

A pipe that carries out what is asked makes about as many as it asks, in every fifth. Under: the decoder's turns, the
hands dropping orders, a rule holding the unit. Over: a rule, the motor or another unit's order doing it unasked (a
selection's spill). The labels are what Gary's units did, read as the pros' were, so a role the game starts by itself
(a unit firing at what walks into its range) is counted as the pros' was. Read it for severalfold differences only
(TODO.md f): the fifths say where. A model trained with --again (TvZ) has no "again" here (its labels need the
re-simulator's unit commands, ingest/reissue_labels.py): its odds are added to keep's.

The army's commit layer, per decision, from the records: its odds of keep, engage and move (before a floor), the
share drawn, the share sent (an order went out), by fifths of the odds. The macro has its own check
(eval/macro_pipe.py: decided, carried out, delay).

    python -m eval.pipe_table --round HT272a --race T
    python -m eval.pipe_table --round PT271a --race T --manifest "gt1+...+modemodel"   (the build the round played)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from eval import monitor, priority  # noqa: E402

FIFTHS = 5
RESEARCH = {"siege": "Siege Mode", "unsiege": "Siege Mode", "mine": "Spider Mines"}   # (the records' macro decision)
RESEARCH_FRAMES = 1200
USES = {"mine": 3}


def _job(job: tuple) -> dict:
    """One game's fight moments for the race's side, with the dataset's labels and the player's order rate."""
    sys.path.insert(0, str(REPO / "ingest"))                 # (the dataset's builders import each other by name)
    from ingest.response_dataset import _job as build
    path, race = job
    got = build((path, None, path, race, None, False))
    return {"path": path, **{k: got[k] for k in ("error", "rows", "extra", "labels", "time", "tags", "budget")}}


def moments(name: str, race: str, workers: int) -> dict:
    """A round's labelled fight moments for one side, built once and kept in its folder."""
    from gary.policy.roles import MAX_UNITS
    out = REPO / "runs" / "league" / name
    cache = out / f"pipe_{race}.npz"
    if cache.exists():
        d = np.load(cache, allow_pickle=True)
        return {k: d[k] for k in d.files}
    table = json.loads((out / "round.json").read_text(encoding="utf-8"))
    replays = [g["replay"] for g in table["games"] if g["result"] != "error"]
    acc = defaultdict(list)
    failed = 0
    with ProcessPoolExecutor(workers, initializer=priority.apply, initargs=("low",)) as pool:
        for i, got in enumerate(monitor.track(pool.map(_job, [(p, race) for p in replays]), len(replays),
                                              f"{name}: labelled fight moments")):
            if got["error"]:
                print(f"  {Path(got['path']).name}: {got['error']}", file=sys.stderr)
                failed += 1
                continue
            for k in ("rows", "extra", "labels", "time", "tags", "budget"):
                acc[k] += got[k]
            acc["game"] += [i] * len(got["rows"])

    def pad(a, width, dtype, fill=0):
        a = np.asarray(a)[:MAX_UNITS]
        if width is None:                                    # (one value a unit)
            z = np.full(MAX_UNITS, fill, dtype)
            z[:len(a)] = a
            return z
        z = np.full((MAX_UNITS, width), fill, dtype)
        if a.size:
            z[:len(a), :min(width, a.shape[1])] = a[:, :width]
        return z

    n = len(acc["rows"])
    got = {"rows": np.stack([pad(r, 11, np.int16) for r in acc["rows"]]) if n else np.zeros((0, MAX_UNITS, 11), np.int16),
           "extra": (np.stack([pad(e, 14, np.float32) for e in acc["extra"]]) if n
                     else np.zeros((0, MAX_UNITS, 14), np.float32)),
           "labels": (np.stack([pad(y, None, np.int8, -1) for y in acc["labels"]]) if n
                      else np.zeros((0, MAX_UNITS), np.int8)),
           "tags": np.stack([pad(t, None, np.int64) for t in acc["tags"]]) if n else np.zeros((0, MAX_UNITS), np.int64),
           "count": np.array([min(len(r), MAX_UNITS) for r in acc["rows"]], np.int32),
           "time": np.array(acc["time"], np.float32), "game": np.array(acc["game"], np.int32),
           "budget": np.array(acc["budget"], np.float32), "replays": np.array(replays)}
    if failed:
        print(f"  {name}: {failed} of {len(replays)} replays couldn't be read (not kept: a rerun builds them)", file=sys.stderr)
    else:
        np.savez_compressed(cache, **got)
    return got


def side_of(name: str, race: str, manifest: str | None) -> tuple[str, str]:
    """(the manifest the side played, the round's matchup) for the round's side of this race."""
    from gary.agent.manifests import manifest_of
    table = json.loads((REPO / "runs" / "league" / name / "round.json").read_text(encoding="utf-8"))
    sides = [s for s in (table.get("terran"), table.get("b") or table.get("zerg")) if s]
    if manifest is None:
        found = [s for s in sides if manifest_of(s).get("race", "T") == race]
        if len(found) != 1:
            raise SystemExit(f"{name}: {len(found)} sides of race {race} ({sides}): name it with --manifest")
        manifest = found[0]
    return manifest, table.get("matchup", "TvZ")


def fight_odds(m: dict, manifest: str, matchup: str, race: str):
    """Per labelled unit-moment: (the moment, the unit, the role model's names, its raw odds, the odds drawn from,
    the decision made), as play would compute them for the manifest's fight layer."""
    from gary.agent.manifests import _against, fight_model_path, manifest_of
    from gary.agent.roles import RoleLearned
    from gary.policy.modes import EVENT_HISTORY, EVENTS, HISTORY, SPELL_MAX, STATES, ModeModel, Situations, latest
    from gary.policy.roles import DECISIONS, ROLES, RoleModel
    from train.roles import decision_labels
    man = manifest_of(manifest)
    enemy = matchup.replace(race, "", 1).replace("v", "") or race
    if enemy in man.get("vs", {}):
        man = _against(man, man["vs"][enemy])
    f = man["fight"] or {}
    path = fight_model_path(man, matchup, race)
    if path is None:
        raise SystemExit(f"{manifest}: no role model in {matchup} (rules only)")
    model = RoleModel.load(path)
    names = model.config["roles"]
    rates = bool(f.get("rates"))
    wanted = (list(STATES.get(race, {})) if f.get("mode_model") else []) + (list(EVENTS.get(race, {})) if f.get("event_model") else [])
    mode_models = {}
    for state in wanted:
        p = latest(matchup, race, state)
        if p is not None:
            mm = ModeModel(p)
            mode_models[state] = mm
    # the made decisions, as the model's data labels them (train/roles.py: decisions, keep where the role held)
    made = decision_labels(m) if "keep" in names else m["labels"]
    as_name = DECISIONS if "keep" in names else ROLES
    research = {}
    for g, rep in enumerate(m["replays"]):
        from eval.judge import research_done
        research[g] = {r: research_done(str(rep), what, RESEARCH_FRAMES) for r, what in RESEARCH.items()}
    out = {"moment": [], "unit": [], "type": [], "raw": [], "asked": [], "made": [], "ready": []}
    order = np.lexsort((m["time"], m["game"]))
    sits: dict = {}
    used: dict = {}                         # (game, tag) -> mines laid
    last_event: dict = {}                   # (game, event, tag) -> time of its last
    for i in monitor.track(order, len(order), "the models' odds"):
        n = int(m["count"][i])
        lab = made[i, :n]
        own = m["rows"][i, :n, 1] == 1
        if not ((lab >= 0) & own).any():
            continue
        g, t = int(m["game"][i]), float(m["time"][i])
        rows, extra, tags = m["rows"][i, :n], m["extra"][i, :n], m["tags"][i, :n]
        budget = None if not np.isfinite(m["budget"][i]) else float(m["budget"][i])
        probs = model.predict(rows, extra, t, budget)
        q = model.rates(probs) if rates else probs
        hazard = {}
        for state, mm in mode_models.items():
            sit = sits.setdefault((g, state), Situations(mm.kinds))
            if mm.event:
                types, role = EVENTS[race][state]
                seen = sit.read(rows, extra, list(tags), t, set(types))
                cols = sit.names + HISTORY
                idx = [cols.index(c) for c in mm.names if c in cols]
                for tag, x in seen.items():
                    since = min(t - last_event[(g, role, tag)], SPELL_MAX) if (g, role, tag) in last_event else SPELL_MAX
                    row = np.concatenate([x[idx], [since for c in mm.names if c not in cols]]).astype(np.float32)
                    hazard[tag] = (role, (role,), float(mm.odds(row[None], np.zeros(1, bool))[0]))
            else:
                off, on, enter, leave = STATES[race][state]
                seen = sit.read(rows, extra, list(tags), t, {off, on})
                kinds = {int(tg): int(rows[j, 0]) for j, tg in enumerate(tags)}
                mine = [tg for tg in seen if kinds.get(int(tg)) in (off, on)]
                if mine:
                    inside = np.array([kinds[int(tg)] == on for tg in mine])
                    h = mm.odds(np.stack([seen[tg] for tg in mine]), inside)
                    for tg, ins, hh in zip(mine, inside, h):
                        hazard[int(tg)] = (leave if ins else enter, (enter, leave), float(hh))
        for j in np.flatnonzero((lab >= 0) & own):
            tag = int(tags[j])
            qj = q[j].astype(np.float64)
            if tag in hazard and hazard[tag][0] in names:
                role, both, h = hazard[tag]
                qj = RoleLearned._with_hazard(qj, names, role, both, h)
            k = as_name[int(lab[j])]
            ready = {}
            for r, at in research[g].items():
                ready[r] = at is not None and t >= at and used.get((g, r, tag), 0) < USES.get(r, 10**9)
            if k in USES:
                used[(g, k, tag)] = used.get((g, k, tag), 0) + 1
            if k in EVENT_ROLES:
                last_event[(g, k, tag)] = t
            out["moment"].append(i)
            out["unit"].append(tag)
            out["type"].append(int(rows[j, 0]))
            out["raw"].append(probs[j])
            out["asked"].append(qj)
            out["made"].append(names.index(k) if k in names else -1)
            out["ready"].append(ready)
    return names, path, rates, {s: str(mm.path) for s, mm in mode_models.items()}, out


EVENT_ROLES = {"mine"}


def role_units(race: str, role: str, types: np.ndarray, ready: list) -> np.ndarray:
    """The unit-moments a decision is asked over: a mode's role its units of the type out of it (siege) or in it
    (unsiege), an event's its units, once researched (and with uses left); any other decision every labelled one."""
    from gary.policy.modes import EVENTS, STATES
    for state, (off, on, enter, leave) in STATES.get(race, {}).items():
        if role in (enter, leave):
            ok = np.array([r.get(role, True) for r in ready])
            return (types == (off if role == enter else on)) & ok
    for event, (kinds, r) in EVENTS.get(race, {}).items():
        if role == r:
            ok = np.array([x.get(role, True) for x in ready])
            return np.isin(types, list(kinds)) & ok
    return np.ones(len(types), bool)


def fifths(asked: np.ndarray, made: np.ndarray) -> str:
    """Each fifth of the unit-moments by the asked odds: its mean odds -> its share made."""
    if len(asked) < FIFTHS * 20:
        return ""
    order = np.argsort(asked, kind="stable")
    parts = np.array_split(order, FIFTHS)
    return "  ".join(f"{asked[p].mean():.1%}>{made[p].mean():.1%}" for p in parts)


def print_fight(race: str, names: list, out: dict) -> None:
    types = np.array(out["type"])
    raw, asked, made = np.array(out["raw"]), np.array(out["asked"]), np.array(out["made"])
    if "again" in names:                      # (no again labels here: its odds go to keep)
        a, k = names.index("again"), names.index("keep")
        for arr in (raw, asked):
            arr[:, k] += arr[:, a]
            arr[:, a] = 0
    print(f"{'decision':>10} {'units':>7} {'raw':>7} {'asked':>7} {'made':>7} {'made/asked':>10}   by fifths of the asked "
          f"odds: mean odds > share made")
    for r, name in enumerate(names):
        if name == "again":
            continue
        sel = role_units(race, name, types, out["ready"])
        if not sel.any():
            continue
        a, p, y = asked[sel, r], raw[sel, r], (made[sel] == r).astype(float)
        if a.sum() < 0.5 and y.sum() == 0:
            continue
        ratio = y.sum() / a.sum() if a.sum() > 0 else float("inf")
        flag = "  <<" if ratio < 1 / 3 else "  >>" if ratio > 3 else ""
        print(f"{name:>10} {sel.sum():7d} {p.mean():7.2%} {a.mean():7.2%} {y.mean():7.2%} {ratio:10.2f}{flag}   "
              f"{fifths(a, y)}")


def outside(m: dict, race: str) -> None:
    """A state's changes where no fight decision is asked: its units' type changing from one moment to the next half
    second (NEXT_S), split by whether the unit was labelled (in a fight, the role model deciding) at the first. The
    army's moves and the motor change modes where nothing is labelled (gt0.39dev: tanks unsieged with no enemy near)."""
    from gary.policy.modes import NEXT_S, STATES
    games = len(m["replays"])
    for state, (off, on, enter, leave) in STATES.get(race, {}).items():
        seq: dict = defaultdict(list)
        for i in range(len(m["time"])):
            n = int(m["count"][i])
            for j in np.flatnonzero((m["rows"][i, :n, 1] == 1) & np.isin(m["rows"][i, :n, 0], (off, on))):
                seq[(int(m["game"][i]), int(m["tags"][i, j]))].append(
                    (float(m["time"][i]), int(m["rows"][i, j, 0]), bool(m["labels"][i, j] >= 0)))
        c = defaultdict(int)
        for s in seq.values():
            s.sort()
            for (t0, a, lab), (t1, b, _) in zip(s, s[1:]):
                if t1 - t0 <= NEXT_S:
                    where = "in" if lab else "out"
                    c[(where, "moments", a)] += 1
                    if a != b:
                        c[(where, enter if b == on else leave, a)] += 1
        print(f"\n{state}, its type changing by the next half second (a game, {games} games): labelled (the fight's) "
              f"and not")
        for where, label in (("in", "labelled"), ("out", "not labelled")):
            print(f"  {label:>12}: {enter} {c[(where, enter, off)] / games:6.1f} of {c[(where, 'moments', off)] / games:7.0f} "
                  f"half seconds out of the mode;  {leave} {c[(where, leave, on)] / games:6.1f} of "
                  f"{c[(where, 'moments', on)] / games:7.0f} in it")


def commit_table(name: str, race: str) -> None:
    """The commit layer's draws from the records: per decision, its odds (before a floor), drawn, sent."""
    out = REPO / "runs" / "league" / name
    q, drawn, sent = [], [], []
    names = ["keep", "engage", "move"]
    for rec in out.glob("*/*.records.jsonl"):
        for line in open(rec, encoding="utf-8"):
            if '"commit"' not in line:
                continue
            r = json.loads(line)
            if r.get("kind") != "decision" or r.get("layer") != "commit" or r.get("side") != race or not r.get("top") \
                    or not str(r.get("by", "")).startswith("draw"):
                continue
            odds = dict(r["top"])
            q.append([odds.get(n, 0.0) for n in names])
            k = names.index(str(r["choice"]).split(" ")[0])
            drawn.append(k)
            sent.append(k if r.get("then") == "sent" else -1)
    if not q:
        print("  commit: no drawn decisions in the records")
        return
    q, drawn, sent = np.array(q), np.array(drawn), np.array(sent)
    print(f"\ncommit ({len(q)} drawn decisions, by: the records' odds before a floor)")
    print(f"{'decision':>10} {'asked':>7} {'drawn':>7} {'sent':>7} {'drawn/asked':>11}   by fifths: mean odds > share drawn")
    for k, n in enumerate(names):
        a, d, s = q[:, k], (drawn == k).astype(float), (sent == k).astype(float)
        ratio = d.sum() / a.sum() if a.sum() > 0 else float("inf")
        flag = "  <<" if ratio < 1 / 3 else "  >>" if ratio > 3 else ""
        print(f"{n:>10} {a.mean():7.2%} {d.mean():7.2%} {s.mean():7.2%} {ratio:11.2f}{flag}   {fifths(a, d)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--round", required=True)
    ap.add_argument("--race", choices=("T", "Z", "P"), required=True)
    ap.add_argument("--manifest", help="the manifest the side played (default: the round's side of this race)")
    ap.add_argument("--workers", type=int, default=4)
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    manifest, matchup = side_of(args.round, args.race, args.manifest)
    m = moments(args.round, args.race, args.workers)
    names, path, rates, modes, out = fight_odds(m, manifest, matchup, args.race)
    print(f"{args.round} {args.race} ({manifest}, {matchup}): {len(out['made'])} labelled unit-moments in "
          f"{len(m['replays'])} games; the role model {Path(path).parent.name}"
          + (", its weights out (rates)" if rates else "") + "".join(f", {s}: {Path(p).name}" for s, p in modes.items()))
    print_fight(args.race, names, out)
    outside(m, args.race)
    commit_table(args.round, args.race)


if __name__ == "__main__":
    main()

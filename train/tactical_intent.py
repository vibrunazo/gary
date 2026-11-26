"""TacticalIntent v0, offline (docs/REFOCUS.md §3.4, Phase 2; 0 games): the pros' army intents labelled from their
commitment ticks, their frequencies and hold lengths, the same labeller over Gary's games, and a model of
P(intent | state, belief) against a time-and-map baseline.

The labeller reads the army dataset's commitment ticks (ingest/army_dataset.py: every TICK seconds, each of a player's
army clusters with what the player did with it in the next TICK seconds: keep, engage or move, the order's cell, and
the cluster's commitment in force). Each tick of the player's main ground cluster (the most supply) gets one intent,
written before any table was read:

  DEFEND_BASE    enemy fighters at a home cell (one with the player's buildings, or next to it: in sight now, seen in
                 the last 30 s, or own losses there in the last LOSS_S), and the cluster is sent within a cell of
                 such a cell, or stands within 2 cells of one with no new order
  ATTACK         sent (or committed) to a cell next to enemy presence the player knew of (the dataset's engage), not
                 a home cell
  RETREAT        sent (or committed) to a cell nearer its main by 2 cells or more, from where enemy fighters were
                 within 2 cells or it lost units in the last LOSS_S
  GATHER         any other move: to a staging point, to the army, back home calm, a position on the map
  HOLD           no commitment in force and no new order: it stands where it is

A commitment kept (no new order) carries the intent of the order that made it: the destination is the cluster's last
order's cell while the dataset's commitment (COMMIT_S) holds. The cells are the dataset's mirrored 16x16 grid (the
player's main in the top-left quadrant). Race-agnostic: the kinds read only own and enemy army, buildings and losses.

The model (P(intent at t | state at t - nothing after t), the intent being what the player does in the next TICK s):
own army and its main cluster's supply, the enemy army seen (now, the last 30 s, ever), the enemy at home, own losses
(at home, near the cluster), the cluster's distance to its main and to the nearest enemy building known, the
cluster's commitment and its age, the intent of the tick before and how long it has held, minerals, gas, supply, the
minute, and the plan belief's odds (the cross-fitted P(spire first) and P(lurker first), train/plan_belief.py --oof,
2:30-10:00, else missing). Baselines: the time-and-map frequencies (minute bucket x map, from the training games) and
the intent of the tick before (persistence). Games split 80/20 by sha1.

    python -m train.tactical_intent --pros                 # label the modern TvZ Terrans, frequencies and hold lengths
    python -m train.tactical_intent --pros --model         # and the model against the baselines
    python -m train.tactical_intent --gary G4299a          # Gary's games of a round, the same labeller
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

INTENTS = ("DEFEND_BASE", "ATTACK", "RETREAT", "GATHER", "HOLD")
TICK = 5
GRID = 16
KEEP, ENGAGE, MOVE = 0, 1, 2
COMMIT_S = 120
MINUTES = (5, 8, 11, 15, 20)               # the baseline's minute buckets


def _cells(mask: np.ndarray) -> list[tuple[int, int]]:
    ys, xs = np.nonzero(mask.reshape(GRID, GRID))
    return list(zip(ys.tolist(), xs.tolist()))


def _d(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _near(c, cells, r) -> bool:
    return any(_d(c, x) <= r for x in cells)


def main_ticks(d, i: int, air_key: bool) -> list[int]:
    """Indices of the player's main ground cluster's ticks: per frame, the most supply (channel 8)."""
    fr = d[f"p{i}_tick_frame"]
    if not len(fr):
        return []
    sup = d[f"p{i}_tick_grid"][:, 8].sum(1)
    air = d[f"p{i}_tick_air"] if air_key else np.zeros(len(fr))
    best: dict[int, int] = {}
    for k in range(len(fr)):
        if air[k]:
            continue
        f = int(fr[k])
        if f not in best or sup[k] > sup[best[f]]:
            best[f] = k
    return [best[f] for f in sorted(best)]


def label_player(d, i: int) -> list[dict]:
    """The player's main cluster's ticks, each with its intent and the features the model reads."""
    keys = set(d.files)
    air_key = f"p{i}_tick_air" in keys
    idx = main_ticks(d, i, air_key)
    if not idx:
        return []
    g = d[f"p{i}_tick_grid"]
    out = []
    dest = None                   # (cell, kind, frame) of the main cluster's last order
    prev, held = None, 0
    from gary.policy.army import ARMY_SUPPLY
    for k in idx:
        grid = g[k].astype(np.int32)
        f = int(d[f"p{i}_tick_frame"][k])
        own_b = _cells(grid[2] > 0)
        home = own_b
        main = min(own_b, key=lambda c: c[0] + c[1]) if own_b else (0, 0)
        enemy_now, enemy_30 = _cells(grid[3] > 0), _cells(grid[7] > 0)
        loss = d[f"p{i}_tick_loss"][k].astype(np.int32) if f"p{i}_tick_loss" in keys else np.zeros(256, np.int32)
        losses = _cells(loss > 0)
        threat = [c for c in home if _near(c, enemy_now + enemy_30, 1) or _near(c, losses, 0)]
        csup = grid[8]
        cc = _cells(csup > 0)
        center = cc[0] if cc else main
        label, target = int(d[f"p{i}_tick_label"][k]), int(d[f"p{i}_tick_target"][k])
        commit, age = int(d[f"p{i}_tick_commit"][k]), float(d[f"p{i}_tick_age"][k])
        if label in (ENGAGE, MOVE) and target >= 0:
            dest = (divmod(target, GRID), label, f)
        elif commit == 0 or (dest is not None and (f - dest[2]) / 24 > COMMIT_S):
            dest = None
        near_enemy = _near(center, enemy_now + enemy_30, 2)
        lost_near = _near(center, losses, 2)
        if threat and ((dest is not None and _near(dest[0], threat, 1)) or (dest is None and _near(center, threat, 2))):
            intent = "DEFEND_BASE"
        elif dest is None:
            intent = "HOLD"
        elif dest[1] == ENGAGE and not _near(dest[0], home, 0):
            intent = "ATTACK"
        elif dest[1] == MOVE and _d(dest[0], main) <= _d(center, main) - 2 and (near_enemy or lost_near):
            intent = "RETREAT"
        else:
            intent = "GATHER"
        units = d[f"p{i}_tick_units"][k].astype(np.float32)
        seen = d[f"p{i}_tick_seen"][k].astype(np.float32)
        eco = d[f"p{i}_tick_eco"][k].astype(np.float32)
        known = d[f"p{i}_tick_known"][k] if f"p{i}_tick_known" in keys else None
        kb = _cells(known > 0) if known is not None else _cells(grid[6] > 0)
        out.append({"f": f, "intent": intent, "prev": prev, "held": held, "x": {
            "minute": f / 1440, "own_army": float(units @ ARMY_SUPPLY), "cluster_sup": float(csup.sum()) / 2,
            "seen_now": float(seen @ ARMY_SUPPLY), "enemy_army_now": float(grid[3].sum()) / 2,
            "enemy_army_30": float(grid[7].sum()) / 2, "enemy_bld_ever": float(grid[6].sum()),
            "enemy_at_home": float(sum(grid[3].reshape(GRID, GRID)[c] + grid[7].reshape(GRID, GRID)[c] for c in home)) / 2,
            "threat_cells": len(threat), "loss_all": float(loss.sum()), "loss_home": float(sum(loss.reshape(GRID, GRID)[c] for c in home)),
            "loss_near": float(lost_near), "near_enemy": float(near_enemy),
            "d_main": _d(center, main), "d_enemy_bld": min((_d(center, c) for c in kb), default=16),
            "d_enemy_army": min((_d(center, c) for c in enemy_now + enemy_30), default=16),
            "commit": commit, "age": min(age, COMMIT_S), "minerals": float(eco[0]), "gas": float(eco[1]),
            "supply": float(eco[2]) / 2, "supply_max": float(eco[3]) / 2, "bases": len(own_b)}})
        held = held + 1 if intent == prev else 1
        prev = intent
    return out


def pro_games(limit: int | None = None) -> list[dict]:
    """The army dataset's modern TvZ Terrans (the dataset version holding TvZ)."""
    from inventory import data_root
    root = data_root() / "interim" / "army"
    for v in ("v6", "v5"):
        idx = root / v / "index.jsonl"
        rows = [json.loads(l) for l in open(idx, encoding="utf-8")] if idx.exists() else []
        rows = [r for r in rows if r.get("ok") and r.get("matchup") == "TvZ" and "cwal" in str(r.get("rel_path"))]
        if rows:
            out = []
            for r in rows[:limit]:
                i = next((k for k, p in enumerate(r["players"]) if p["race"] == "T"), None)
                if i is not None:
                    out.append({"npz": str(root / v / r["sha1"][:2] / f"{r['sha1']}.npz"), "i": i, "sha1": r["sha1"],
                                "rel": r["rel_path"], "slot": r["players"][i]["slot"], "map": r.get("map", "")})
            return out
    return []


def gary_games(round_name: str) -> list[dict]:
    """Gary's Terran in a round's replays, built into commitment ticks (train/rule_labels.py's cache)."""
    from concurrent.futures import ProcessPoolExecutor
    from train.rule_labels import _build
    reps = sorted(glob.glob(str(REPO / "runs" / "league" / round_name / "*" / "*.rep"))) if not round_name.endswith(".rep") \
        else [str(Path(round_name).resolve())]
    with ProcessPoolExecutor(4) as pool:
        infos = list(pool.map(_build, [(Path(round_name).stem if round_name.endswith(".rep") else round_name, r) for r in reps]))
    return [{"npz": x["npz"], "i": x["i"], "sha1": Path(x["npz"]).stem, "rel": r, "slot": None,
             "map": Path(r).parent.name} for x, r in zip(infos, reps) if x]


def label_games(games: list[dict]) -> list[dict]:
    rows = []
    for gm in games:
        try:
            d = np.load(gm["npz"])
        except Exception:  # noqa: BLE001
            continue
        for r in label_player(d, gm["i"]):
            r.update(sha1=gm["sha1"], rel=gm["rel"], slot=gm["slot"], map=gm["map"])
            rows.append(r)
    return rows


def describe(name: str, rows: list[dict]) -> None:
    n = len(rows)
    games = len({r["sha1"] for r in rows})
    c = Counter(r["intent"] for r in rows)
    print(f"\n== {name}: {games} games, {n} main-cluster ticks ({TICK} s)")
    print("  share of ticks: " + ", ".join(f"{k} {c[k] / n:.1%}" for k in INTENTS))
    by = defaultdict(Counter)
    for r in rows:
        by[min(int(r["f"] / 1440 // 5) * 5, 20)][r["intent"]] += 1
    for m in sorted(by):
        t = sum(by[m].values())
        print(f"  {m:2d}-{m + 5 if m < 20 else '':2} min: " + ", ".join(f"{k} {by[m][k] / t:.0%}" for k in INTENTS) + f"  ({t})")
    runs = defaultdict(list)                     # hold lengths: consecutive ticks of one intent, per game
    for sha in {r["sha1"] for r in rows}:
        seq = [r for r in rows if r["sha1"] == sha]
        k = 0
        while k < len(seq):
            j = k
            while j + 1 < len(seq) and seq[j + 1]["intent"] == seq[k]["intent"] and seq[j + 1]["f"] - seq[j]["f"] <= TICK * 24 + 2:
                j += 1
            runs[seq[k]["intent"]].append((j - k + 1) * TICK)
            k = j + 1
    print("  hold lengths (s): " + "; ".join(f"{k} median {np.median(runs[k]):.0f}, p75 {np.percentile(runs[k], 75):.0f}, "
                                            f"{len(runs[k]) / games:.1f} a game" for k in INTENTS if runs[k]))
    trans = Counter((r["prev"], r["intent"]) for r in rows if r["prev"] and r["prev"] != r["intent"])
    tot = sum(trans.values())
    print("  commonest switches: " + ", ".join(f"{a}->{b} {v / tot:.0%}" for (a, b), v in trans.most_common(6)))


FEATS = ("minute", "own_army", "cluster_sup", "seen_now", "enemy_army_now", "enemy_army_30", "enemy_bld_ever",
         "enemy_at_home", "threat_cells", "loss_all", "loss_home", "loss_near", "near_enemy", "d_main", "d_enemy_bld",
         "d_enemy_army", "commit", "age", "minerals", "gas", "supply", "supply_max", "bases")


def _belief(rows: list[dict]) -> None:
    """The cross-fitted plan belief's P(spire first) and P(lurker first) at the latest 30 s sample at or before each
    tick (2:30-10:00; else NaN)."""
    from train.plan_belief import parts
    p = REPO / "runs" / "plan_belief" / "TvZ_T_oof_20261124" / "oof.npz"
    for r in rows:
        r["x"]["p_spire"] = r["x"]["p_lurker"] = float("nan")
    if not p.exists():
        return
    d = np.load(p, allow_pickle=True)
    names = [str(n) for n in d["names"]]
    sp = np.array([parts(n)[2] == "spire first" for n in names])
    lu = np.array([parts(n)[2] == "lurker first" for n in names])
    at = defaultdict(dict)
    for rel, slot, t, o in zip(d["rel_path"], d["slot"], d["t"], d["odds"]):
        at[(str(rel), int(slot))][int(t)] = (float(o[sp].sum()), float(o[lu].sum()))
    for r in rows:
        tab = at.get((r["rel"], r["slot"]))
        if not tab:
            continue
        s = r["f"] // 24
        ts = [t for t in tab if t <= s and s - t < 30]
        if ts:
            r["x"]["p_spire"], r["x"]["p_lurker"] = tab[max(ts)]


def model(rows: list[dict]) -> None:
    from sklearn.ensemble import HistGradientBoostingClassifier
    _belief(rows)
    rows = [r for r in rows if r["prev"] is not None]
    held = lambda r: int(hashlib.sha1(r["sha1"].encode()).hexdigest()[:8], 16) % 5 == 0
    tr, te = [r for r in rows if not held(r)], [r for r in rows if held(r)]
    K = len(INTENTS)
    feats = FEATS + ("p_spire", "p_lurker")
    X = lambda rs: np.array([[r["x"][f] for f in feats] + [INTENTS.index(r["prev"]), min(r["held"], 60)] for r in rs], np.float32)
    y = lambda rs: np.array([INTENTS.index(r["intent"]) for r in rs])
    Xtr, ytr, Xte, yte = X(tr), y(tr), X(te), y(te)
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
                                       categorical_features=[len(feats)], random_state=0).fit(Xtr, ytr)
    pm = m.predict_proba(Xte)
    pm = np.column_stack([pm[:, list(m.classes_).index(c)] if c in m.classes_ else np.zeros(len(te)) for c in range(K)])

    def mapname(r):
        from ladder_maps import clean_name
        return clean_name(r["map"]).rsplit(" ", 1)[0]
    bucket = lambda r: int(np.searchsorted(MINUTES, r["f"] / 1440, side="right"))
    tm, tb = defaultdict(lambda: np.ones(K)), defaultdict(lambda: np.ones(K))
    for r in tr:
        tm[(bucket(r), mapname(r))][INTENTS.index(r["intent"])] += 1
        tb[bucket(r)][INTENTS.index(r["intent"])] += 1
    pb = np.array([(tm[(bucket(r), mapname(r))] if (bucket(r), mapname(r)) in tm else tb[bucket(r)]) for r in te], np.float64)
    pb /= pb.sum(1, keepdims=True)
    trans = defaultdict(lambda: np.ones(K))      # persistence: P(intent | the tick before's), from the training games
    for r in tr:
        trans[r["prev"]][INTENTS.index(r["intent"])] += 1
    pp = np.array([trans[r["prev"]] / trans[r["prev"]].sum() for r in te])

    def scores(p):
        eps = 1e-6
        ll = -np.mean(np.log(np.clip(p[np.arange(len(yte)), yte], eps, 1)))
        oh = np.eye(K)[yte]
        brier = np.mean(((p - oh) ** 2).sum(1))
        acc = np.mean(p.argmax(1) == yte)
        conf, hit = p.max(1), p.argmax(1) == yte
        bins = np.linspace(0, 1, 11)
        ece = sum(abs(conf[(conf >= a) & (conf < b)].mean() - hit[(conf >= a) & (conf < b)].mean()) *
                  np.mean((conf >= a) & (conf < b)) for a, b in zip(bins[:-1], bins[1:]) if np.any((conf >= a) & (conf < b)))
        return ll, brier, acc, ece
    print(f"\n== P(intent | state, belief): {len({r['sha1'] for r in tr})} training games ({len(tr)} ticks), "
          f"{len({r['sha1'] for r in te})} held out ({len(te)})")
    for name, p in (("time and map", pb), ("the tick before (persistence)", pp), ("model", pm)):
        ll, br, acc, ece = scores(p)
        print(f"  {name:32s} log-loss {ll:.3f}  Brier {br:.3f}  accuracy {acc:.3f}  ECE {ece:.3f}")
    switch = np.array([r["intent"] != r["prev"] for r in te])
    for name, p in (("time and map", pb), ("persistence", pp), ("model", pm)):
        print(f"  on the {switch.sum()} held-out ticks where the intent changes, {name}: accuracy "
              f"{np.mean(p[switch].argmax(1) == yte[switch]):.3f}, log-loss "
              f"{-np.mean(np.log(np.clip(p[switch][np.arange(switch.sum()), yte[switch]], 1e-6, 1))):.3f}")
    print("  per intent (held out): " + "; ".join(
        f"{c} n {np.sum(yte == k)}, mean P {pm[yte == k, k].mean():.2f}, recall {np.mean(pm[yte == k].argmax(1) == k):.2f}"
        for k, c in enumerate(INTENTS) if np.sum(yte == k)))
    conf = pm.max(1)
    for a, b in ((0, .4), (.4, .6), (.6, .8), (.8, .9), (.9, 1.01)):
        s = (conf >= a) & (conf < b)
        if s.any():
            print(f"  calibration: confidence {a:.1f}-{min(b, 1):.1f}: {s.mean():.0%} of ticks, accuracy {np.mean(pm[s].argmax(1) == yte[s]):.2f}")
    print(f"  with the belief (2:30-10:00): {np.mean(~np.isnan(Xte[:, len(FEATS)])):.0%} of held-out ticks")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pros", action="store_true")
    ap.add_argument("--model", action="store_true")
    ap.add_argument("--gary", nargs="*", default=[], help="rounds (or replays) of Gary's: the same labeller")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dump", help="the pros' labelled ticks to this JSON (a sample to read by hand)")
    a = ap.parse_args()
    if a.pros:
        rows = label_games(pro_games(a.limit))
        describe("modern TvZ pros (Terran)", rows)
        if a.dump:
            Path(a.dump).write_text(json.dumps(rows[:4000], default=float), encoding="utf-8")
        if a.model:
            model(rows)
    for g in a.gary:
        describe(f"Gary: {g}", label_games(gary_games(g)))


if __name__ == "__main__":
    main()

"""TacticalIntent (docs/TACTICAL_INTENT.md, Phase 2): the army's intents labelled on the pros' commitment ticks, their
frequencies and hold lengths, the same labeller over Gary's games, and the intent model: a switch hazard, the next
intent given a switch, and the defence's size (gary/policy/tactical.py, which holds the labeller and the numbers).

The labeller reads the army dataset's commitment ticks (ingest/army_dataset.py: every TICK seconds, each army cluster
with what the player did with it in the next TICK seconds, keep / engage / move and the order's cell, and the
commitment in force). The main ground cluster (the most supply at the moment) carries its last order's destination
along while its commitment holds; every other cluster is labelled from its own row (an order's cell, or its
commitment's kind). cluster_intents() gives every row's intent, for the commit model's input (train/commit.py
--intent); main_intents() the main cluster's by frame, for the role model's (train/roles.py --intent).

The model (P(intent at t | the state at t), the intent being what the player does in the next TICK s): the numbers of
gary/policy/tactical.py FEATURES (with the army's cohesion: the share of the own army within 2 cells of the cluster and
of its destination, the clusters), the intent of the tick before and how long it has held. Two heads of gradient-boosted
trees, decoded in play at the pros' hazard: does it switch now, and to what. Baselines: the time-and-map frequencies
and persistence; the score where the pro gave a new order (the labeller's own rule sets HOLD and a standing defence from
inputs) is the one that counts. The defence: the supply the pros send or keep at a threatened base (every cluster sent
within a cell of the threat, or standing within 2 cells of it), as a hurdle on SIZER_FEATURES: does anyone go (a
classifier), and how much when someone does (a median regression on those moments).
Games split 80/20 by sha1.

    python -m train.tactical_intent --pros                 # label the modern TvZ Terrans: frequencies, hold lengths
    python -m train.tactical_intent --pros --train         # and train the model, scored against the baselines
    python -m train.tactical_intent --gary G4299a          # Gary's games of a round, the same labeller
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

from gary.policy.tactical import (ENGAGE, FEATURES, GRID, INTENTS, KEEP, MOVE, SIZER_FEATURES, IntentModel, Scene,  # noqa: E402
                                  dist, features, label, near, sizer_features)

TICK = 5
MINUTES = (5, 8, 11, 15, 20)               # the baseline's minute buckets


def _frames(d, i: int):
    """Per frame, its tick rows; and each frame's main ground cluster's row."""
    fr = d[f"p{i}_tick_frame"]
    keys = set(d.files)
    air = d[f"p{i}_tick_air"] if f"p{i}_tick_air" in keys else np.zeros(len(fr))
    sup = d[f"p{i}_tick_grid"][:, 8].sum(1)
    by: dict[int, list[int]] = defaultdict(list)
    for k in range(len(fr)):
        by[int(fr[k])].append(k)
    out = []
    for f in sorted(by):
        ground = [k for k in by[f] if not air[k]]
        out.append((f, by[f], max(ground, key=lambda k: sup[k]) if ground else None))
    return out


def _row(d, i: int, k: int):
    keys = set(d.files)
    grid = d[f"p{i}_tick_grid"][k]
    loss = d[f"p{i}_tick_loss"][k] if f"p{i}_tick_loss" in keys else None
    return Scene(grid, loss), int(d[f"p{i}_tick_label"][k]), int(d[f"p{i}_tick_target"][k]), \
        int(d[f"p{i}_tick_commit"][k]), float(d[f"p{i}_tick_age"][k])


def label_player(d, i: int, rows: bool = False):
    """The main cluster's ticks: intent, the numbers, the tick's label, the commitment and its target (v6); with rows,
    every tick row's intent too (-1: a flyers' cluster)."""
    keys = set(d.files)
    n = len(d[f"p{i}_tick_frame"])
    per_row = np.full(n, -1, np.int8)
    air = d[f"p{i}_tick_air"] if f"p{i}_tick_air" in keys else np.zeros(n)
    out, dest, prev, held = [], None, None, 0
    for f, ks, main in _frames(d, i):
        if main is None:
            continue
        scene, lab, tgt, com, age = _row(d, i, main)
        intent, dest = label(scene, lab, tgt, com, dest)
        if rows:
            per_row[main] = INTENTS.index(intent)
            for k in ks:
                if k != main and not air[k]:
                    s2, l2, t2, c2, _ = _row(d, i, k)
                    per_row[k] = INTENTS.index(label(s2, l2, t2, c2, None)[0])
        x = features(scene, d[f"p{i}_tick_eco"][main], f, com, age, dest[0] if dest else None,
                     sum(1 for k in ks if not air[k]), prev, held)
        ct = int(d[f"p{i}_tick_ctarget"][main]) if f"p{i}_tick_ctarget" in keys else None
        out.append({"f": f, "intent": intent, "prev": prev, "held": held, "label": lab, "commit_kind": com,
                    "dest": None if dest is None else dest[0][0] * GRID + dest[0][1], "ctarget": ct, "x": x,
                    "sizer": _defence(d, i, ks, scene, f) if scene.threat else None})
        held = held + 1 if intent == prev else 1
        prev = intent
    return (out, per_row) if rows else out


def _defence(d, i: int, ks: list[int], scene: Scene, f: int) -> dict:
    """At a threatened moment: the supply every cluster sends within a cell of the threat or keeps within 2 cells of it
    (the defence's size), and the sizer's numbers."""
    sent = 0.0
    for k in ks:
        g8 = d[f"p{i}_tick_grid"][k][8]
        c = np.nonzero(g8)[0]
        if not len(c):
            continue
        center = divmod(int(c[0]), GRID)
        lab, tgt = int(d[f"p{i}_tick_label"][k]), int(d[f"p{i}_tick_target"][k])
        if (lab != KEEP and tgt >= 0 and near(divmod(tgt, GRID), scene.threat, 1)) or (lab == KEEP and near(center, scene.threat, 2)):
            sent += float(g8.sum()) / 2
    return {"y": sent, "x": sizer_features(scene, f, len(ks))}


def cluster_intents(path, i: int) -> np.ndarray:
    """Every tick row's intent (INTENTS index; -1 for a flyers' cluster), cached beside nothing: cheap enough to redo."""
    return label_player(np.load(path), i, rows=True)[1]


def main_intents(path, i: int) -> tuple[np.ndarray, np.ndarray]:
    """The main cluster's (frames, intents) of a player's game."""
    rows = label_player(np.load(path), i)
    return np.array([r["f"] for r in rows], np.int64), np.array([INTENTS.index(r["intent"]) for r in rows], np.int8)


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
    """Gary's Terran in a round's replays (or one replay), built into commitment ticks (train/rule_labels.py's cache)."""
    from train.rule_labels import _build
    reps = [str(Path(round_name).resolve())] if round_name.endswith(".rep") else \
        sorted(glob.glob(str(REPO / "runs" / "league" / round_name / "*" / "*.rep")))
    name = Path(round_name).stem if round_name.endswith(".rep") else round_name
    out = []
    for r in reps:
        x = _build((name, r))
        if x:
            out.append({"npz": x["npz"], "i": x["i"], "sha1": Path(x["npz"]).stem, "rel": r, "slot": None,
                        "map": Path(r).parent.name})
    return out


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
    hold = [r for r in rows if r["intent"] == "HOLD"]
    print(f"  HOLD with a commitment in force: {sum(r['commit_kind'] != 0 for r in hold) / max(1, len(hold)):.1%}")
    by = defaultdict(Counter)
    for r in rows:
        by[min(int(r["f"] / 1440 // 5) * 5, 20)][r["intent"]] += 1
    for m in sorted(by):
        t = sum(by[m].values())
        print(f"  {m:2d}-{m + 5 if m < 20 else '':2} min: " + ", ".join(f"{k} {by[m][k] / t:.0%}" for k in INTENTS) + f"  ({t})")
    runs = defaultdict(list)
    seqs = defaultdict(list)
    for r in rows:
        seqs[r["sha1"]].append(r)
    for seq in seqs.values():
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


def _held(r) -> bool:
    return int(hashlib.sha1(r["sha1"].encode()).hexdigest()[:8], 16) % 5 == 0


def train(rows: list[dict], out_dir: Path) -> dict:
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
    K = len(INTENTS)
    rr = [r for r in rows if r["prev"] is not None]
    tr, te = [r for r in rr if not _held(r)], [r for r in rr if _held(r)]
    X = lambda q: np.array([[r["x"][f] for f in FEATURES] for r in q], np.float32)
    y = lambda q: np.array([INTENTS.index(r["intent"]) for r in q])
    cat = [FEATURES.index("prev")]
    rep: dict = {"train_games": len({r["sha1"] for r in tr}), "test_games": len({r["sha1"] for r in te}),
                 "train_ticks": len(tr), "test_ticks": len(te)}
    sw = lambda q: np.array([r["intent"] != r["prev"] for r in q])
    hz = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, random_state=0, categorical_features=cat)
    hz.fit(X(tr), sw(tr))
    trs = [r for r in tr if r["intent"] != r["prev"]]
    nx = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, random_state=0, categorical_features=cat)
    nx.fit(X(trs), y(trs))
    model = IntentModel({"hazard": hz, "next": nx, "features": list(FEATURES), "intents": list(INTENTS),
                         "send": None, "sizer": None, "sizer_features": list(SIZER_FEATURES)})     # (the defence's below)
    # the combined odds: stay with 1 - P(switch), else the next head's
    Xt, yt = X(te), y(te)
    ps = hz.predict_proba(Xt)[:, 1]
    pn = np.zeros((len(te), K))
    pn[:, nx.classes_.astype(int)] = nx.predict_proba(Xt)
    prev = np.array([INTENTS.index(r["prev"]) for r in te])
    pn[np.arange(len(te)), prev] = 0
    pn /= np.maximum(pn.sum(1, keepdims=True), 1e-9)
    p = pn * ps[:, None]
    p[np.arange(len(te)), prev] += 1 - ps
    bucket = lambda r: int(np.searchsorted(MINUTES, r["f"] / 1440, side="right"))
    tb = defaultdict(lambda: np.ones(K))
    for r in tr:
        tb[bucket(r)][INTENTS.index(r["intent"])] += 1
    pb = np.array([tb[bucket(r)] / tb[bucket(r)].sum() for r in te])
    ll = lambda q, m: float(-np.mean(np.log(np.clip(q[m][np.arange(m.sum()), yt[m]], 1e-6, 1))))
    acc = lambda q, m: float(np.mean(q[m].argmax(1) == yt[m]))
    new = np.array([r["label"] != KEEP for r in te])
    swm = prev != yt
    for name, m in (("all", np.ones(len(te), bool)), ("new order", new), ("switch", swm), ("switch, new order", swm & new)):
        rep[name] = {"n": int(m.sum()), "model": [round(ll(p, m), 3), round(acc(p, m), 3)],
                     "time": [round(ll(pb, m), 3), round(acc(pb, m), 3)]}
        if "switch" in name:                                 # (the next head alone, given the switch)
            rep[name]["next_head"] = [round(ll(pn, m), 3), round(acc(pn, m), 3)]
    from sklearn.metrics import roc_auc_score
    rep["hazard_auc"] = round(float(roc_auc_score(swm, ps)), 3)
    conf = p.max(1)
    rep["calibration"] = {f"{a:.1f}-{b:.1f}": [round(float(((conf >= a) & (conf < b)).mean()), 3),
                                               round(float((p.argmax(1) == yt)[(conf >= a) & (conf < b)].mean()), 3)]
                          for a, b in ((0, .4), (.4, .6), (.6, .8), (.8, .9), (.9, 1.01)) if ((conf >= a) & (conf < b)).any()}
    # the cohesion numbers' part: the next head without them, on the switches with a new order
    coh = [FEATURES.index(n) for n in ("army_near_cluster", "army_near_dest", "cluster_share", "n_clusters")]
    keep_cols = [k for k in range(len(FEATURES)) if k not in coh]
    nx2 = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, random_state=0,
                                         categorical_features=[keep_cols.index(cat[0])]).fit(X(trs)[:, keep_cols], y(trs))
    pn2 = np.zeros((len(te), K))
    pn2[:, nx2.classes_.astype(int)] = nx2.predict_proba(Xt[:, keep_cols])
    pn2[np.arange(len(te)), prev] = 0
    pn2 /= np.maximum(pn2.sum(1, keepdims=True), 1e-9)
    m = swm & new
    rep["next_head_without_cohesion"] = [round(ll(pn2, m), 3), round(acc(pn2, m), 3)]
    ga = swm & (prev == INTENTS.index("GATHER")) & (yt == INTENTS.index("ATTACK"))
    gx = swm & (prev == INTENTS.index("GATHER"))
    if gx.any():
        rep["gather_to_attack"] = {"n": int(gx.sum()), "p_attack_with": round(float(pn[ga, 1].mean()), 3),
                                   "p_attack_without": round(float(pn2[ga, 1].mean()), 3),
                                   "auc_with": round(float(roc_auc_score(ga[gx], pn[gx, 1])), 3),
                                   "auc_without": round(float(roc_auc_score(ga[gx], pn2[gx, 1])), 3)}
    # the defence: does anyone go (a classifier), and how much goes when someone does (a median regression on the moments
    # someone defended): a hurdle model, so a losses-only or small threat can send nobody, as the pros do in 19-32%
    s_tr = [r["sizer"] for r in tr if r["sizer"] is not None]
    s_te = [r["sizer"] for r in te if r["sizer"] is not None]
    SX = lambda q: np.array([[s["x"][f] for f in SIZER_FEATURES] for s in q], np.float32)
    sy = lambda q: np.array([s["y"] for s in q], np.float32)
    go = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, random_state=0).fit(SX(s_tr), sy(s_tr) > 0)
    xs, yt_s = SX(s_te), sy(s_te)
    pg = go.predict_proba(xs)[:, 1]
    th = xs[:, SIZER_FEATURES.index("threat_sup")]
    army = xs[:, SIZER_FEATURES.index("own_army")]
    minute = xs[:, SIZER_FEATURES.index("minute")]
    lossh = xs[:, SIZER_FEATURES.index("loss_home")]
    sent = yt_s > 0
    rep["send"] = {"n_test": len(s_te), "auc": round(float(roc_auc_score(sent, pg)), 3),
                   "pros_nobody": round(float(1 - sent.mean()), 3), "model_nobody": round(float(1 - pg.mean()), 3)}
    bands = (("0-2", th <= 2), ("2-6", (th > 2) & (th <= 6)), ("6-12", (th > 6) & (th <= 12)), ("12+", th > 12),
             ("losses only (no enemy seen)", (th == 0) & (lossh > 0)))
    rep["send_by_threat"] = {name: {"n": int(m.sum()), "pros_nobody": round(float(1 - sent[m].mean()), 3),
                                    "model_nobody": round(float(1 - pg[m].mean()), 3)} for name, m in bands if m.any()}
    s_tr1 = [s for s in s_tr if s["y"] > 0]
    sz = HistGradientBoostingRegressor(loss="quantile", quantile=0.5, max_iter=300, random_state=0).fit(SX(s_tr1), sy(s_tr1))
    pred = sz.predict(xs)
    base = np.median(sy(s_tr1))
    rep["sizer"] = {"n_test_sent": int(sent.sum()), "mae": round(float(np.mean(np.abs(pred[sent] - yt_s[sent]))), 2),
                    "mae_constant_median": round(float(np.mean(np.abs(base - yt_s[sent]))), 2), "constant": float(base)}
    rep["sizer_by_threat"] = {name: {"n": int((m & sent).sum()), "pros_median": round(float(np.median(yt_s[m & sent])), 1),
                                     "model_median": round(float(np.median(pred[m & sent])), 1),
                                     "pros_share_of_army": round(float(np.median(yt_s[m & sent] / np.maximum(army[m & sent], 1))), 2),
                                     "model_half_army_or_more": round(float(np.mean(pred[m & sent] >= 0.5 * army[m & sent])), 3)}
                              for name, m in bands if (m & sent).any()}
    small = (army <= 6) & (minute <= 4.5)
    if small.any():
        rep["sizer_small_army_early"] = {"n": int(small.sum()), "army_median": round(float(np.median(army[small])), 1),
                                         "pros_nobody": round(float(1 - sent[small].mean()), 3),
                                         "model_nobody": round(float(1 - pg[small].mean()), 3),
                                         "pros_median_sent": round(float(np.median(yt_s[small & sent])), 1) if (small & sent).any() else None,
                                         "model_median": round(float(np.median(pred[small])), 1),
                                         "model_over_army": round(float(np.mean(pred[small] > army[small])), 3)}
    model.d.update(send=go, sizer=sz, sizer_features=list(SIZER_FEATURES))
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save(out_dir / "model.pkl")
    (out_dir / "report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    return rep


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pros", action="store_true")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--gary", nargs="*", default=[], help="rounds (or replays) of Gary's: the same labeller")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", help="the model's folder (default runs/intent/TvZ_T_<time>: what Gary loads as newest)")
    a = ap.parse_args()
    if a.pros:
        rows = label_games(pro_games(a.limit))
        describe("modern TvZ pros (Terran)", rows)
        if a.train:
            out = Path(a.out) if a.out else REPO / "runs" / "intent" / f"TvZ_T_{time.strftime('%Y%m%d-%H%M%S')}"
            print(json.dumps(train(rows, out), indent=1))
            print(f"saved {out / 'model.pkl'}")
    for g in a.gary:
        describe(f"Gary: {g}", label_games(gary_games(g)))


if __name__ == "__main__":
    main()

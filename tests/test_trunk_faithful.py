"""Decision faithfulness of the strategic trunk (docs/REFOCUS.md §3.5 metric 2, Phase 1 gate 3): the trunk re-queried in
memory on a saved input state, with valid upstream edits (the belief's bucket, the looked split), finds the minimal
abductive set of facts whose change flips the branch (gary/agent/selector.py minimal_flips). A unit test, not a
threshold: on a deterministic trunk, reverting the triggering evidence reverts the switch by construction.

  synthetic      a table built here: a decision with one cause (one fact flips it) and an overdetermined one (no single
                 fact flips it, two together do), always run
  saved games    every branch score of Phase 1's games under the chain table (TC294a4, TB295a*: runs/, skipped without
                 them): the record's own state re-scored gives the record's P_pro and take; each start flips back when
                 its belief is set to the contrast's (the low belief); each query in memory under 1 ms

Run: python tests/test_trunk_faithful.py
"""
from __future__ import annotations

import glob
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

TABLE = REPO / "runs" / "selector" / "TvZ_T_PREP_VS_LURKER_chainA_20261124.json"
ROUNDS = ("TC294a4", "TB295a0", "TB295a1", "TB295a4", "TB295a9")
BUDGET_MS = 1.0


def _scorer_with(cells: dict, meta: dict):
    import tempfile
    from gary.agent.selector import ProFrequencyScorer
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "t.json"
        p.write_text(json.dumps({"meta": meta, "cells": cells}), encoding="utf-8")
        return ProFrequencyScorer({"B": p})


def test_synthetic():
    from gary.agent.selector import minimal_flips
    meta = {"tech": "lurker first", "buckets": [0.5], "minutes": [360], "chains": [["Factory"]], "min_n": 10,
            "threshold": 0.5, "contrast": {"belief": 0}, "contrast_level": "same",
            "backoff": [["belief", "looked", "a", "minute"], ["belief"]]}
    c = lambda p: {"p": p, "lo": p - 0.05, "hi": p + 0.05, "games": 50, "pro_won_if_taken": 0.5, "pro_won_if_not": 0.5}
    cells = {}
    for b in (0, 1):
        for lk in (0, 1):
            for mi in (0, 1):
                # with a high belief the pros take it if Gary looked or it is late, either (overdetermined); with a
                # low one (the contrast) never
                cells[f"belief={b}|looked={lk}|a=0|minute={mi}"] = c(0.9 if b == 1 and (lk or mi) else 0.1)
    cells["belief=0"], cells["belief=1"] = c(0.1), c(0.9)
    sc = _scorer_with(cells, meta)
    # one cause each: early, looked; the belief or the look alone flips it
    base, flips = minimal_flips(sc, "B", {"belief": 1, "looked": 1, "a": 0, "minute": 0}, {"belief": [0], "looked": [0]})
    assert base is True and flips == [{"belief": 0}, {"looked": 0}], flips
    # overdetermined: late and looked; of the sighting and clock facts no single one flips it, the two together do
    base, flips = minimal_flips(sc, "B", {"belief": 1, "looked": 1, "a": 0, "minute": 1}, {"looked": [0], "minute": [0]})
    assert base is True and flips == [{"looked": 0, "minute": 0}], flips


def _saved():
    """(record, its state's fields, p_tech) of every branch score under the chain table in the saved rounds."""
    out = []
    for rnd in ROUNDS:
        for rec in sorted(glob.glob(str(REPO / "runs" / "league" / rnd / "*" / "*.records.jsonl"))):
            rows = [json.loads(s) for s in Path(rec).read_text(encoding="utf-8").splitlines()[1:]]
            by_id = {r["id"]: r for r in rows if "id" in r and r.get("side") == "T"}
            for r in rows:
                if r.get("kind") != "branch_select" or r.get("side") != "T" or "p_pro" not in r \
                        or r.get("table") != TABLE.name:
                    continue
                if "fields" in r:
                    fields, p = r["fields"], r.get("p_tech")
                elif r.get("backoff") == 0:          # (before the records kept them: the finest cell's key has them all)
                    fields = {k: int(v) for k, v in (x.split("=") for x in r["cell"].split("|"))}
                    p = by_id.get(r.get("parent"), {}).get("tech", {}).get("lurker first")
                else:                                # (a coarser cell: the rest rebuilt from the records and the replay)
                    fields, p = _rebuilt(rec, r, by_id)
                    if fields is None:
                        continue
                out.append((rnd, Path(rec).parent.name, r, fields, p))
    return out


_ITEMS: dict = {}


def _rebuilt(rec: str, r: dict, by_id: dict):
    """A coarser cell's whole state: the belief's odds and looked from its plan_belief record, the minute from its
    frame, each chain's items had from Gary's replay (its orders by then, the replay's clock), kept only where these
    give the record's own cell back."""
    meta = json.loads(TABLE.read_text(encoding="utf-8"))["meta"]
    pb = by_id.get(r.get("parent"))
    if pb is None:
        return None, None
    if rec not in _ITEMS:
        sys.path.insert(0, str(REPO / "ingest"))
        from eval.trunk_dryrun import items_of
        _ITEMS[rec] = items_of(rec.replace(".records.jsonl", ".rep"))["T"]
    have = _ITEMS[rec]
    rt = r["f"] * 42 / 1000
    import numpy as np
    p = pb["tech"].get(meta["tech"], 0.0)
    fields = {"belief": int(np.searchsorted(meta["buckets"], p, side="right")), "looked": int(bool(pb.get("looked"))),
              "minute": int(np.searchsorted(meta["minutes"], r["f"] / 24, side="right"))}
    names = {"Siege Mode": "Tank Siege Mode"}
    for letter, chain in zip("abcdefgh", meta["chains"]):
        k = 0
        while k < len(chain) and have.get(names.get(chain[k], chain[k]), 1e9) <= rt:
            k += 1
        fields[letter] = k
    key = "|".join(f"{k}={fields[k]}" for k in meta["backoff"][r["backoff"]])
    return (fields, p) if key == r["cell"] else (None, None)


def test_saved_games():
    if not TABLE.exists():
        print("skip: no chain table (runs/selector)")
        return
    from gary.agent.selector import ProFrequencyScorer, minimal_flips, state_of
    sc = ProFrequencyScorer({"PREP_VS_LURKER": TABLE})
    meta = sc.tables["PREP_VS_LURKER"]["meta"]
    saved = _saved()
    if not saved:
        print("skip: no saved Phase 1 games under the chain table")
        return
    n_q, t0 = 0, time.perf_counter()
    same, starts, flipped = 0, 0, 0
    for rnd, game, r, fields, p in saved:
        belief, ctx = state_of(meta, fields, p)
        s = sc.score(belief, None, ctx, [type("C", (), {"name": "PREP_VS_LURKER"})])["PREP_VS_LURKER"]
        n_q += 1
        took = r["chosen"] != "none"
        assert abs(s.p - r["p_pro"]) < 1e-9 and s.take == took, (rnd, game, r["f"], r["cell"], s, r["p_pro"], took)
        same += 1
        if took:
            starts += 1
            edits = {"belief": [b for b in range(len(meta["buckets"]) + 1) if b != fields["belief"]],
                     "looked": [1 - int(fields["looked"])]}
            base, flips = minimal_flips(sc, "PREP_VS_LURKER", fields, edits, p)
            n_q += 1 + len(edits["belief"]) + 1 + len(edits["belief"]) * 1
            assert base is True and flips, (rnd, game, r["f"], fields)
            # reverting the triggering evidence (the belief to the contrast's, the low belief) reverts the switch
            assert {"belief": meta["contrast"]["belief"]} in flips or any(set(f) == {"belief"} for f in flips), flips
            flipped += 1
    ms = (time.perf_counter() - t0) * 1000 / n_q
    print(f"  {same} branch scores re-queried as recorded, {starts} starts, {flipped} flipped back by their belief; "
          f"{ms:.3f} ms a query ({n_q} queries)")
    assert ms < BUDGET_MS, f"{ms:.3f} ms a query"


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"FAIL {name}: {type(e).__name__}: {e}")
                failed += 1
    sys.exit(1 if failed else 0)

"""Training data for Gary's army model: where a player sends their army, and how.

From every clean, re-simulated game, each player's orders to army units (at least 4 supply
selected; at most one per 2 s, the last) become samples of:

  grid    (9, 16, 16)  the map as that player knew it, on a 16x16 grid (values capped at 255):
                       0-2 own army supply x2 / workers / buildings,
                       3-5 the same for enemy units visible right now,
                       6 enemy buildings ever seen (most at once), 7 enemy army seen in the last 30 s,
                       8 the ordered group (its supply x2, in its cell)
  units   (228,)       own units by type (all), seen (228,) enemy units visible now
  eco     (4,)         minerals, gas, supply used x2, supply max x2;  frame
  target  cell 0-255 where the group was sent;  kind 0 move, 1 attack (attack-move or a target)
  sup     supply x2 of the ordered group

Coordinates are mirrored so the player's own main is always in the top-left quadrant (maps and
start positions differ; the model learns "toward the enemy", not "toward the top-right").
Far moves (attacks, retreats, defending) and short ones (holding, fighting in place) are both
kept, so the model also learns when the army stays where it is.

Output: data/interim/army/v1/<sha1[:2]>/<sha1>.npz and data/interim/army/v1/index.jsonl.

Usage:
  python ingest/army_dataset.py --matchup TvZ --limit 200
  python ingest/army_dataset.py --matchup TvZ
  python ingest/army_dataset.py --report
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from inventory import data_root
from macro_dataset import RACES, TOWN_HALLS, run_resim, select

VERSION = "v1"
GRID, CELLS, CHANNELS = 16, 256, 9
MIN_SUP = 8                  # at least 4 supply (x2) selected
WINDOW = 48                  # at most one sample per player per 2 s
RECENT = 30                  # channel 7 remembers enemy army for 30 s
KIND = {"move": 0, "amove": 1, "attack": 1, "patrol": 1}


def out_dir() -> Path:
    return data_root() / "interim" / "army" / VERSION


def flip_cells(a: np.ndarray, fx: bool, fy: bool) -> np.ndarray:
    """Mirror (..., 256) cell arrays so the player's main is top-left."""
    g = a.reshape(*a.shape[:-1], GRID, GRID)
    if fy:
        g = g[..., ::-1, :]
    if fx:
        g = g[..., :, ::-1]
    return np.ascontiguousarray(g).reshape(a.shape)


def cell_of(x: float, y: float, mw: int, mh: int, fx: bool, fy: bool) -> int:
    gx = min(GRID - 1, max(0, int(x * GRID // mw)))
    gy = min(GRID - 1, max(0, int(y * GRID // mh)))
    if fx:
        gx = GRID - 1 - gx
    if fy:
        gy = GRID - 1 - gy
    return gy * GRID + gx


def build_game(rec: dict) -> dict:
    row = {"sha1": rec["sha1"], "rel_path": rec["rel_path"], "matchup": rec["matchup"]}
    t0 = time.time()
    try:
        lines = run_resim(rec["rel_path"])
    except Exception as e:  # noqa: BLE001 - one bad replay must not stop the batch
        row.update(ok=False, error=str(e)[:300])
        return row
    header = next(r for r in lines if r["type"] == "header")
    mw, mh = header.get("map_w", 4096), header.get("map_h", 4096)
    snaps = [r for r in lines if r["type"] == "snapshot"]
    accepted: dict[int, int] = {}
    for s in snaps:
        for p in s["players"]:
            accepted[p["slot"]] = accepted.get(p["slot"], 0) + p["accepted"]
    slots = sorted(sorted(accepted, key=lambda s: -accepted[s])[:2])
    if len(slots) != 2 or not snaps:
        row.update(ok=False, error="not two players")
        return row
    starts = {}
    for r in lines:
        if r["type"] == "event" and r["frame"] <= 1 and r.get("unit") in TOWN_HALLS and r["slot"] in slots:
            starts.setdefault(r["slot"], (r["x"], r["y"]))
    if len(starts) != 2:
        row.update(ok=False, error="no start town halls")
        return row

    T = len(snaps)
    frames = np.array([s["frame"] for s in snaps], dtype=np.int32)
    per = {}
    for s in slots:
        per[s] = {"g": np.zeros((T, 6, CELLS), np.uint16), "units": np.zeros((T, 228), np.uint16),
                  "seen": np.zeros((T, 228), np.uint16), "eco": np.zeros((T, 4), np.int32)}
    for t, snap in enumerate(snaps):
        for p in snap["players"]:
            d = per.get(p["slot"])
            if d is None:
                continue
            g = p.get("g", [])
            flat = d["g"][t].reshape(-1)
            flat[np.array(g[0::2], dtype=np.int64)] = np.array(g[1::2], dtype=np.uint16)
            for k, (n_all, _) in p["units"].items():
                d["units"][t, int(k)] = n_all
            for k, n in p.get("seen", {}).items():
                d["seen"][t, int(k)] = n
            d["eco"][t] = (p["minerals"], p["gas"], round(p["supply_used"] * 2), round(p["supply_max"] * 2))

    out = {}
    counts = {}
    for i, s in enumerate(slots):
        fx, fy = starts[s][0] > mw / 2, starts[s][1] > mh / 2
        d = per[s]
        g = flip_cells(d["g"], fx, fy)
        seen_bld = np.maximum.accumulate(g[:, 5], axis=0)
        recent = np.zeros_like(g[:, 3])
        for t in range(T):           # enemy army seen in the last RECENT seconds (most at once)
            recent[t] = g[max(0, t - RECENT):t + 1, 3].max(0)
        orders = [r for r in lines if r["type"] == "army" and r["slot"] == s and r["sup"] >= MIN_SUP
                  and r["kind"] in KIND and 0 <= r["x"] < mw and 0 <= r["y"] < mh]
        picked = {}
        for r in orders:              # the last order in each 2-second window
            picked[r["frame"] // WINDOW] = r
        rows = sorted(picked.values(), key=lambda r: r["frame"])
        n = len(rows)
        grid = np.zeros((n, CHANNELS, CELLS), np.uint16)    # stored as uint8 (capped at 255)
        tidx = np.zeros(n, np.int32)
        target = np.zeros(n, np.int16)
        kind = np.zeros(n, np.int8)
        sup = np.zeros(n, np.int16)
        for j, r in enumerate(rows):
            t = max(0, min(T - 1, int(np.searchsorted(frames, r["frame"], side="right")) - 1))
            tidx[j] = t
            grid[j, :6] = g[t]
            grid[j, 6] = seen_bld[t]
            grid[j, 7] = recent[t]
            grid[j, 8, cell_of(r["cx"], r["cy"], mw, mh, fx, fy)] = r["sup"]
            target[j] = cell_of(r["x"], r["y"], mw, mh, fx, fy)
            kind[j] = KIND[r["kind"]]
            sup[j] = r["sup"]
        out[f"p{i}_grid"] = np.minimum(grid, 255).astype(np.uint8)
        out[f"p{i}_frame"] = frames[tidx]
        out[f"p{i}_units"] = d["units"][tidx]
        out[f"p{i}_seen"] = d["seen"][tidx]
        out[f"p{i}_eco"] = d["eco"][tidx]
        out[f"p{i}_target"] = target
        out[f"p{i}_kind"] = kind
        out[f"p{i}_sup"] = sup
        counts[i] = n

    path = out_dir() / rec["sha1"][:2] / f"{rec['sha1']}.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    np.savez_compressed(buf, **out)
    path.write_bytes(buf.getvalue())
    names = {p["slot"]: p for p in header["players"]}
    players = [{"slot": s, "name": names.get(s, {}).get("name", ""),
                "race": RACES.get(names.get(s, {}).get("race"), "?"), "samples": counts[i]}
               for i, s in enumerate(slots)]
    row.update(ok=True, map=header.get("map"), map_w=mw, map_h=mh, end_frame=header.get("end_frame"),
               players=players, bytes=path.stat().st_size, seconds=round(time.time() - t0, 2))
    return row


def load_index() -> dict[str, dict]:
    path = out_dir() / "index.jsonl"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["sha1"]: r for r in map(json.loads, f)}


def report() -> None:
    rows = list(load_index().values())
    ok = [r for r in rows if r.get("ok")]
    if not rows:
        print("no games yet")
        return
    print(f"games {len(ok)} ok, {len(rows) - len(ok)} failed")
    print(f"army-order samples {sum(p['samples'] for r in ok for p in r['players']):,}")
    print(f"disk {sum(r['bytes'] for r in ok) / 1e6:.0f} MB, resim {sum(r['seconds'] for r in ok) / max(1, len(ok)):.1f} s/game")
    for r in [r for r in rows if not r.get("ok")][:5]:
        print("  failed:", r["rel_path"], r.get("error"))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--matchup", default="TvZ")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        report()
        return
    done = {} if args.force else load_index()
    todo = [r for r in select(args.matchup) if r["sha1"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} games to build ({len(done)} already done)", flush=True)
    out_dir().mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with open(out_dir() / "index.jsonl", "a", encoding="utf-8") as index, \
            ProcessPoolExecutor(args.workers) as pool:
        futures = [pool.submit(build_game, r) for r in todo]
        for n, fut in enumerate(as_completed(futures), 1):
            index.write(json.dumps(fut.result(), ensure_ascii=False) + "\n")
            if n % 100 == 0 or n == len(todo):
                index.flush()
                print(f"{n}/{len(todo)}  {time.time() - t0:.0f} s", flush=True)
    report()


if __name__ == "__main__":
    main()

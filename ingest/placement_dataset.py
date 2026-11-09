"""The placement dataset: where the pros start each building, against what the player knew then (#65: the learned
placement model that replaces the pros' placement table, AGENTS.md's stop-gap "Buildings' base and side by the pros'
shares").

The table draws a building's base and side from the pros' shares at that minute, blind to the game; the pros' are not:
their PvZ cannons at 7-9 minutes stand by a mineral line in 14% before they saw a Spire or Mutalisks and 51% after, in
the main by its minerals 6% and 25% (199 modern games). So here every building a pro starts (town halls and gas
buildings aside: the executor places those itself) is a sample, labelled with its base (the main, the natural, a newer
base with a town hall of the player's: the nearest of them, as the executor's bases) and its side of it (by the
minerals as eval/placement.py tells it, or the front), with what the player knew as it was decided:

  per base (main, natural, newer)  a town hall there, the player's buildings, of this type, static defense (the race's,
                                   gary/races.py), workers, and workers and buildings lost there in the last LOSS_S
                                   (gone GONE frames and not back: gary/policy/placement.py, shared with play)
  the building                     its type, how many of it the player had started, the minute, the bases held
  the enemy                        the units in sight now and the most of each type seen at once so far: the macro
                                   dataset's seen and seen_max (ingest/macro_dataset.py), as the macro tracker counts
                                   them in play (tests/test_inputs.py holds those)
  the style                        the player's build style (gary/styles.py's labels), -1 if none

Re-simulated in-process (gary.env Game.scenario, the full state: the player's own units, which it knows), every LOOK_EVERY
frames to MINUTES; a building is a sample at the step it first appears, with the state of the step before. Modern
clean games only (the current ladder maps: the old maps' bases stand elsewhere).

    python -m ingest.placement_dataset --matchup PvZ --race P
Output: data/interim/placement/v1/<sha1[:2]>/<sha1>_<race>.npz (per player i: p{i}_bases (n, 3, BASE_FEATURES),
p{i}_glob (n, 4), p{i}_type, p{i}_seen, p{i}_seen_max (n, 228), p{i}_base, p{i}_side, p{i}_frame) and its index.jsonl
(the players' slots, races, styles and samples).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

from eval import monitor, priority  # noqa: E402
from inventory import data_root  # noqa: E402
from gary.race import Race  # noqa: E402
from gary.policy.placement import BASE_FEATURES, LOOK_EVERY, Losses, base_features, kinds as placed_kinds, \
    newer_bases  # noqa: E402

VERSION = "v1"
MINUTES = 14
MINERAL_SIDE, MINERAL_TILES = 0.3, 9    # eval/placement.py's mineral side


def out_dir() -> Path:
    return data_root() / "interim" / "placement" / VERSION


def npz_path(sha1: str, race: str) -> Path:
    """A game's samples of one race (both races of a game have theirs: TvZ's Terran and Zerg)."""
    return out_dir() / sha1[:2] / f"{sha1}_{race}.npz"


def select(matchup: str) -> list[dict]:
    """The matchup's modern clean games in the macro dataset (8 minutes at least), with its file."""
    from eval.humanlike import clean_replays
    clean = clean_replays()
    macro = data_root() / "interim" / "macro" / "v1"
    out = []
    for line in open(macro / "index.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("ok") and r["matchup"] == matchup and r["rel_path"].startswith("cwal") and r["rel_path"] in clean \
                and r.get("end_frame", 0) >= 8 * 1440:
            out.append({**r, "macro": str(macro / r["sha1"][:2] / f"{r['sha1']}.npz")})
    return out


def _side(x: float, y: float, base) -> int:
    """1 on the base's mineral side (eval/placement.py's rule), else 0."""
    hx, hy = base.center
    mx = sum(m[0] for m in base.minerals) / len(base.minerals)
    my = sum(m[1] for m in base.minerals) / len(base.minerals)
    d = math.dist((x, y), (hx, hy))
    if d == 0 or d >= MINERAL_TILES * 32:
        return 0
    vx, vy, wx, wy = x - hx, y - hy, mx - hx, my - hy
    return int((vx * wx + vy * wy) / (d * math.hypot(wx, wy) + 1e-9) > MINERAL_SIDE)


def build_game(rec: dict, race: str) -> dict:
    """The race's players' samples of one game, written to its npz; its index row."""
    from gary import styles
    row = {"sha1": rec["sha1"], "rel_path": rec["rel_path"], "matchup": rec["matchup"], "race": race}
    labels = (styles.catalog(rec["matchup"], race) or {}).get("assignments", {})
    m = np.load(rec["macro"])
    players = [(i, p) for i, p in enumerate(rec["players"]) if p["race"] == race]
    try:
        arrays = game_samples(str(data_root() / "raw" / rec["rel_path"]), race, [p["slot"] for _, p in players],
                              m["frames"], [m["seen"][:, i] for i, _ in players])
    except Exception as e:  # noqa: BLE001 - one bad replay must not stop the batch
        row.update(ok=False, error=str(e)[:300])
        return row
    out, meta = {}, []
    for k, ((_, p), a) in enumerate(zip(players, arrays)):
        out.update({f"p{k}_{name}": v for name, v in a.items()})
        meta.append({"slot": p["slot"], "name": p["name"], "style": labels.get(f"{rec['rel_path']}|{p['name']}", -1),
                     "samples": len(a["type"])})
    path = npz_path(rec["sha1"], race)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **out)
    row.update(ok=True, players=meta, kinds=placed_kinds(Race.of(race)))
    return row


def game_samples(replay: str, race: str, slots: list[int], mframes: np.ndarray, mseen: list[np.ndarray]) -> list[dict]:
    """Each player's (by slot) samples of a replay, given the macro dataset's frames and the player's seen counts there
    ((frames, 228)): bases, glob, type, base, side, frame, seen, seen_max (tests/test_inputs.py compares play's)."""
    from gary.env import Game
    from gary.mapinfo import MapInfo
    from gary.races import ENEMY
    R = Race.of(race)
    static = ENEMY[race].static
    kinds = placed_kinds(R)
    g = Game.scenario(replay)
    mapinfo = MapInfo.from_game(g)
    st = {slot: {"main": None, "natural": None, "known": set(), "losses": Losses(R), "started": {}, "rows": []}
          for slot in slots}
    while g.frame < MINUTES * 1440:
        try:
            g.step(LOOK_EVERY)
        except Exception:
            break
        units = g.observe()["units"]
        for slot in slots:
            s = st[slot]
            mine = {u["tag"]: u for u in units if u["owner"] == slot}
            if s["main"] is None:
                halls = [u for u in mine.values() if u["type"] in R.town_halls]
                if not halls:
                    continue
                s["main"] = mapinfo.base_near((halls[0]["x"], halls[0]["y"]))
                s["natural"] = mapinfo.natural_of(s["main"])
            prev = s["losses"].prev
            s["losses"].look(g.frame, mine)
            new = [u for tag, u in mine.items() if u["type"] in kinds and tag not in s["known"]]
            for u in new:
                s["known"].add(u["tag"])
                if prev:
                    s["rows"].append(_sample(s, u, prev, g.frame, R, static, kinds, mapinfo))
            s["known"].update(tag for tag, u in mine.items() if u["type"] in kinds)
    out = []
    for slot, seen in zip(slots, mseen):
        rows = st[slot]["rows"]
        t = np.clip(np.searchsorted(mframes, [r["frame"] for r in rows], side="right") - 1, 0, len(mframes) - 1) \
            if rows else np.zeros(0, int)
        smax = np.maximum.accumulate(seen, axis=0)
        out.append({"bases": np.array([r["bases"] for r in rows], np.float32).reshape(-1, 3, len(BASE_FEATURES)),
                    "glob": np.array([r["glob"] for r in rows], np.float32).reshape(-1, 4),
                    "type": np.array([r["type"] for r in rows], np.int16),
                    "base": np.array([r["base"] for r in rows], np.int8),
                    "side": np.array([r["side"] for r in rows], np.int8),
                    "frame": np.array([r["frame"] for r in rows], np.int32),
                    "seen": np.minimum(seen[t], 255).astype(np.uint8),
                    "seen_max": np.minimum(smax[t], 255).astype(np.uint8)})
    return out


def _sample(s: dict, u: dict, prev: dict, frame: int, R, static, kinds: list, mapinfo) -> dict:
    """One building's sample: the state of the look before it appeared, its base and side."""
    main, natural = s["main"], s["natural"]
    own = list(prev.values())
    newer = newer_bases(mapinfo.bases, main, natural, own, R)
    cands = [(0, main), (1, natural)] + [(2, b) for b in newer]
    base, b = min(cands, key=lambda kb: math.dist(kb[1].center, (u["x"], u["y"])))
    feats = base_features(own, u["type"], main, natural, newer, R, static, s["losses"].recent(frame))
    started = s["started"].get(u["type"], 0)
    s["started"][u["type"]] = started + 1
    return {"bases": feats, "glob": [frame / 1440, started, len(newer) + 2, kinds.index(u["type"])],
            "type": u["type"], "base": base, "side": _side(u["x"], u["y"], b), "frame": frame}


def load_index() -> dict[str, dict]:
    path = out_dir() / "index.jsonl"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["sha1"] + r.get("race", ""): r for r in map(json.loads, f) if r.get("ok")}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--matchup", default="PvZ")
    ap.add_argument("--race", default="P")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=3)
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    done = load_index()
    todo = [r for r in select(args.matchup) if r["sha1"] + args.race not in done
            and any(p["race"] == args.race for p in r["players"])]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} games to build ({len(done)} already done)", flush=True)
    out_dir().mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with open(out_dir() / "index.jsonl", "a", encoding="utf-8") as index, ProcessPoolExecutor(args.workers) as pool:
        futures = [pool.submit(build_game, r, args.race) for r in todo]
        for n, fut in enumerate(monitor.track(as_completed(futures), len(futures), "games built"), 1):
            index.write(json.dumps(fut.result(), ensure_ascii=False) + "\n")
            if n % 50 == 0 or n == len(todo):
                index.flush()
                print(f"{n}/{len(todo)}  {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()

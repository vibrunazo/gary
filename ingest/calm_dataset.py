"""The calm dataset: what the pros told their fighters out of contact (gary/policy/calm.py).

From clean re-simulated pro games (ingest/response_dataset.py select: the race's side of its matchups), the game as the
player sees it, every SAMPLE frames up to MAX_MIN minutes: a snapshot around each bunch of calm fighters (no seen enemy
fighter within CALM_SIGHT), rows and extras as the role model's (the motion over the half second before, the terrain,
the age and the biggest bunch), and each calm fighter's label over the next LABEL frames from the player's unit commands
(the re-simulator's, OpenBW's unit IDs as the game's): gary/policy/calm.py NAMES; for "again" its point (cmd_to:
tiles from the unit, mirrored as the rows). state: the unit's order then (0 standing, 1 moving, 2 other).

    python -m ingest.calm_dataset --race T --matchups TvZ --games 150
Output: data/interim/calm/calm_<race>_<matchups>.npz, for train/roles.py --data ... --again --move-free.
"""
from __future__ import annotations

import argparse
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from eval import monitor, priority
from gary.policy.calm import MOVED, NAMES, POINT_ORDERS, RECLICK, army_cell, snapshots
from gary.policy.roles import AGAIN, EXTRA, MAX_UNITS
from ingest.response_dataset import Seen, select

SAMPLE = 96                   # frames between snapshots (4 s: a game gives about 450 by 30:00)
LABEL = 12                    # frames: a command this soon after the snapshot is its decision (the role data's half second)
MAX_MIN = 30
STANDING = {2, 3, 107}        # Guard, PlayerGuard, HoldPosition
MOVING = {6, 14}              # Move, AttackMove


def label(cmd: dict | None, u: dict, mw: int, mh: int, flip) -> tuple[int, float, float]:
    """(NAMES index, cmd_to x, y) of the unit's first command in the window (None: keep)."""
    if cmd is None:
        return NAMES.index("keep"), np.nan, np.nan
    point = cmd.get("x") is not None and ((cmd["cmd"] == "rclick" and not cmd.get("target"))
                                          or (cmd["cmd"] == "order" and cmd.get("order") in POINT_ORDERS))
    if not point:
        return NAMES.index("other"), np.nan, np.nan
    if u["order"] in MOVING and math.dist((cmd["x"], cmd["y"]), (u["tx"], u["ty"])) <= RECLICK:
        return NAMES.index("reclick"), np.nan, np.nan
    a, b = army_cell(cmd["x"], cmd["y"], mw, mh), army_cell(u["x"], u["y"], mw, mh)
    if max(abs(a[0] - b[0]), abs(a[1] - b[1])) >= MOVED:
        return NAMES.index("far"), np.nan, np.nan
    fx, fy = (-1 if flip[0] else 1), (-1 if flip[1] else 1)
    return NAMES.index(AGAIN), fx * (cmd["x"] - u["x"]) / 32, fy * (cmd["y"] - u["y"]) / 32


def _job(job: tuple) -> dict:
    import bisect
    from gary.env import Game
    from gary.policy.army import is_building, is_worker, supply_x2
    from gary.policy.roles import RACE_SHELTERS, Ground, extra_features, own_extras, terrain_features
    from ingest.reissue_labels import _resim
    from ingest.role_dataset import HALLS
    path, end, sha1, race, player = job
    out = {"sha1": sha1, "error": None, "rows": [], "extra": [], "labels": [], "to": [], "state": [], "time": []}
    try:
        lines = _resim(Path(path))
        if lines is None:
            raise RuntimeError("the re-simulator's commands couldn't be read")
        g = Game.scenario(path)
        try:
            g.step(24)
            obs = g.observe()
            slot = next((p["slot"] for p in obs["players"] if p.get("name") == player), None)
            if slot is None:
                slot = next(u["owner"] for u in obs["units"] if u["type"] in HALLS[race])
            cmds = sorted((r for r in lines if r["type"] == "ucmd" and r["slot"] == slot), key=lambda r: r["frame"])
            cf = [r["frame"] for r in cmds]
            mw, mh = obs["map"]["w"], obs["map"]["h"]
            hall = next(u for u in obs["units"] if u["owner"] == slot and u["type"] in HALLS[race])
            starts = g.start_locations()
            main = min(starts, key=lambda s: math.dist((s["x"], s["y"]), (hall["x"], hall["y"]))) if starts else hall
            flip = (main["x"] > mw / 2, main["y"] > mh / 2)
            try:
                ground = Ground.of(g, (main["x"], main["y"]))
            except Exception:
                ground = None
            seen = Seen(g, slot)
            first_seen: dict[int, int] = {}
            last = min(end or MAX_MIN * 1440, MAX_MIN * 1440)
            f = SAMPLE
            while f + LABEL <= last:
                g.step(f - LABEL - g.frame)
                prev = {u["tag"]: (u["x"], u["y"]) for u in seen.observe()["units"]}
                g.step(LABEL)
                o = seen.observe()
                by_tag = {u["tag"]: u for u in o["units"]}
                positions = {t: (u["x"], u["y"]) for t, u in by_tag.items()}
                own = [u for u in o["units"] if u["owner"] == slot]
                for u in own:
                    if u["completed"] and supply_x2(u["type"]) > 0 and not is_worker(u["type"]) and not is_building(u["type"]):
                        first_seen.setdefault(u["tag"], f)
                for rows, tags, _, calm in snapshots(o, slot, flip, supply_x2, is_worker, is_building, MAX_UNITS):
                    extra = extra_features(rows, tags, positions, prev, flip)
                    extra[:, 6:] = terrain_features(tags, positions, ground, [(u["x"], u["y"]) for u in own if u["type"] in HALLS[race]],
                                                    [(u["x"], u["y"]) for u in own if u["type"] in RACE_SHELTERS[race] and u["completed"]],
                                                    flip)
                    own_extras(extra, tags, by_tag, slot, first_seen, f)
                    y = np.full(len(tags), -1, np.int8)
                    to = np.full((len(tags), 2), np.nan, np.float32)
                    state = np.full(len(tags), -1, np.int8)
                    for i, t in enumerate(tags):
                        if t not in calm:
                            continue
                        u = by_tag[t]
                        k = bisect.bisect_left(cf, f)
                        cmd = None
                        while k < len(cf) and cf[k] < f + LABEL:
                            if t in cmds[k]["units"]:
                                cmd = cmds[k]
                                break
                            k += 1
                        y[i], to[i, 0], to[i, 1] = label(cmd, u, mw, mh, flip)
                        state[i] = 0 if u["order"] in STANDING else 1 if u["order"] in MOVING else 2
                    if (y >= 0).any():
                        out["rows"].append(rows)
                        out["extra"].append(extra)
                        out["labels"].append(y)
                        out["to"].append(to)
                        out["state"].append(state)
                        out["time"].append(f * 42 / 1000)
                f += SAMPLE
        finally:
            g.close()
    except Exception as e:                         # (a replay that won't run: counted, skipped)
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--race", choices=("T", "Z", "P"), default="T")
    ap.add_argument("--matchups", default="TvZ", help="comma-joined")
    ap.add_argument("--games", type=int, default=150)
    ap.add_argument("--era", choices=("old", "modern", "both"), default="modern")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--out", help="default: data/interim/calm/calm_<race>_<matchups>.npz")
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    from ingest.inventory import data_root
    matchups = tuple(args.matchups.split(","))
    jobs = select(args.games, args.race, args.era, matchups)
    with ProcessPoolExecutor(args.parallel) as pool:
        results = list(monitor.track(pool.map(_job, jobs, chunksize=1), len(jobs), "games"))
    n = sum(len(r["rows"]) for r in results)
    rows = np.zeros((n, MAX_UNITS, 11), np.int16)
    extra = np.zeros((n, MAX_UNITS, EXTRA), np.float16)
    labels = np.full((n, MAX_UNITS), -1, np.int8)
    to = np.full((n, MAX_UNITS, 2), np.nan, np.float16)
    state = np.full((n, MAX_UNITS), -1, np.int8)
    count = np.zeros(n, np.int16)
    time_s = np.zeros(n, np.float32)
    game = np.zeros(n, np.int32)
    i = 0
    for gi, r in enumerate(results):
        for rr, e, y, t, s, ts in zip(r["rows"], r["extra"], r["labels"], r["to"], r["state"], r["time"]):
            k = min(len(rr), MAX_UNITS)
            rows[i, :k], extra[i, :k], labels[i, :k], to[i, :k], state[i, :k] = rr[:k], e[:k], y[:k], t[:k], s[:k]
            count[i], time_s[i], game[i] = k, ts, gi
            i += 1
    out = Path(args.out) if args.out else data_root() / "interim" / "calm" / f"calm_{args.race}_{'_'.join(matchups)}.npz"
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, rows=rows, extra=extra, labels=labels, cmd_to=to, state=state, count=count, time=time_s,
                        game=game, sha1=np.array([r["sha1"] for r in results]), names=np.array(NAMES))
    errors = [r["error"] for r in results if r["error"]]
    y = labels[labels >= 0]
    print(f"{len(results)} games ({len(errors)} errors{': ' + errors[0] if errors else ''}), {n} snapshots, "
          f"{len(y)} labeled calm fighters -> {out}")
    for name, m in (("all", labels >= 0), ("standing", (labels >= 0) & (state == 0)), ("moving", (labels >= 0) & (state == 1))):
        yy = labels[m]
        print(f"  {name:9s} " + ", ".join(f"{NAMES[k]} {np.mean(yy == k):.2%}" for k in range(len(NAMES)))
              + f"  (a fighter a minute, again: {np.mean(yy == NAMES.index(AGAIN)) * 120:.2f})")
    again = to[labels == NAMES.index(AGAIN)].astype(np.float32)
    if len(again):
        d = np.hypot(again[:, 0], again[:, 1])
        print(f"  again's points: median {np.nanmedian(d):.1f} tiles from the unit; mean vector "
              f"({np.nanmean(again[:, 0]):.2f}, {np.nanmean(again[:, 1]):.2f})")


if __name__ == "__main__":
    main()

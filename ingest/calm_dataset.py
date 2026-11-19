"""The calm dataset: what the pros told their fighters out of contact (gary/policy/calm.py).

From clean re-simulated pro games (ingest/response_dataset.py select: the race's side of its matchups), the game as the
player sees it, up to MAX_MIN minutes, two kinds of snapshots, rows and extras as the role model's (the motion over the
half second before, the terrain, the age and the biggest bunch) and then gary/policy/calm.py map_extras:
  rate   every SAMPLE frames, around each bunch of calm fighters (no seen enemy fighter within CALM_SIGHT): each calm
         fighter labeled over the next LABEL frames from the player's unit commands (the re-simulator's, OpenBW's unit
         IDs as the game's), gary/policy/calm.py NAMES; cmd_to NaN
  (--far: only where snapshots, at the far point commands to calm bunches under SMALL supply, for the calm_far model)
  where  at every short point command mostly for calm fighters (one a second for the same units: a pro's spam is one
         decision), centered on the commanded calm units' middle: no labels (-1), cmd_to the click from that middle
         (tiles, mirrored as the rows) on each commanded unit. A pro's short order is one command for a median 10 units,
         every one's target the click, and sampling every SAMPLE frames kept one command in eight (2026-11-19)
state: the unit's order then (0 standing, 1 moving, 2 other); where: the snapshot's kind.

    python -m ingest.calm_dataset --race T --matchups TvZ --games 300
Output: data/interim/calm/calm_<race>_<matchups>.npz, for train/roles.py --data ... --decisions --again --offset-bins.
"""
from __future__ import annotations

import argparse
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from eval import monitor, priority
from gary.policy.calm import MAP_EXTRA, MOVED, NAMES, POINT_ORDERS, RECLICK, SMALL, army_cell, snapshots
from gary.policy.roles import AGAIN, EXTRA, MAX_UNITS
from ingest.response_dataset import Seen, select

SAMPLE = 96                   # frames between rate snapshots (4 s: a game gives about 450 by 30:00)
LABEL = 12                    # frames: a command this soon after the snapshot is its decision (the role data's half second)
MAX_MIN = 30
STANDING = {2, 3, 107}        # Guard, PlayerGuard, HoldPosition
MOVING = {6, 14}              # Move, AttackMove


def is_point(cmd: dict) -> bool:
    """A command that places units at a point: a right-click on the ground or an attack-move."""
    return cmd.get("x") is not None and ((cmd["cmd"] == "rclick" and not cmd.get("target"))
                                         or (cmd["cmd"] == "order" and cmd.get("order") in POINT_ORDERS))


def label(cmd: dict | None, u: dict, mw: int, mh: int) -> int:
    """The NAMES index of the unit's first command in the window (None: keep)."""
    if cmd is None:
        return NAMES.index("keep")
    if not is_point(cmd):
        return NAMES.index("other")
    if u["order"] in MOVING and math.dist((cmd["x"], cmd["y"]), (u["tx"], u["ty"])) <= RECLICK:
        return NAMES.index("reclick")
    a, b = army_cell(cmd["x"], cmd["y"], mw, mh), army_cell(u["x"], u["y"], mw, mh)
    return NAMES.index("far") if max(abs(a[0] - b[0]), abs(a[1] - b[1])) >= MOVED else NAMES.index(AGAIN)


def _job(job: tuple) -> dict:
    import bisect
    from gary.env import Game
    from gary.policy.army import is_building, is_worker, supply_x2
    from gary.policy.calm import AROUND_OTHER, AROUND_OWN, calm_fighters, map_extras
    from gary.policy.fight import rows_at
    from gary.policy.roles import RACE_SHELTERS, Ground, extra_features, own_extras, terrain_features
    from ingest.reissue_labels import _resim
    from ingest.role_dataset import HALLS
    path, end, sha1, race, player, far = job
    out = {"sha1": sha1, "error": None, "rows": [], "extra": [], "labels": [], "to": [], "state": [], "time": [],
           "where": []}
    fighter = lambda u: supply_x2(u["type"]) > 0 and not is_worker(u["type"]) and not is_building(u["type"])
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
            fx, fy = (-1 if flip[0] else 1), (-1 if flip[1] else 1)
            try:
                ground = Ground.of(g, (main["x"], main["y"]))
            except Exception:
                ground = None
            seen = Seen(g, slot)
            first_seen: dict[int, int] = {}
            last = min(end or MAX_MIN * 1440, MAX_MIN * 1440)
            events = [] if far else [(f, None) for f in range(SAMPLE, last - LABEL + 1, SAMPLE)]
            events += [(r["frame"], r) for r in cmds if is_point(r) and SAMPLE <= r["frame"] < last - LABEL]
            events.sort(key=lambda e: (e[0], e[1] is not None))
            kept: dict[frozenset, tuple[int, float, float]] = {}
            prev_pos, prev_frame = {}, None
            for f, cmd in events:
                if f > g.frame:
                    if f - LABEL > g.frame:
                        g.step(f - LABEL - g.frame)
                        prev_pos, prev_frame = {u["tag"]: (u["x"], u["y"]) for u in seen.observe()["units"]}, g.frame
                    g.step(f - g.frame)
                o = seen.observe()
                by_tag = {u["tag"]: u for u in o["units"]}
                positions = {t: (u["x"], u["y"]) for t, u in by_tag.items()}
                prev = prev_pos if prev_frame is not None and g.frame - prev_frame == LABEL else {}
                own = [u for u in o["units"] if u["owner"] == slot]
                for u in own:
                    if u["completed"] and fighter(u):
                        first_seen.setdefault(u["tag"], f)

                def extras(rows, tags):
                    extra = extra_features(rows, tags, positions, prev, flip)
                    extra[:, 6:] = terrain_features(
                        tags, positions, ground, [(u["x"], u["y"]) for u in own if u["type"] in HALLS[race]],
                        [(u["x"], u["y"]) for u in own if u["type"] in RACE_SHELTERS[race] and u["completed"]], flip)
                    own_extras(extra, tags, by_tag, slot, first_seen, f)
                    return np.concatenate([extra, map_extras(tags, positions, ground, mw, mh, flip)], 1)

                def keep(rows, tags, y, to, state, where):
                    out["rows"].append(rows)
                    out["extra"].append(extras(rows, tags))
                    out["labels"].append(y)
                    out["to"].append(to)
                    out["state"].append(state)
                    out["time"].append(f * 42 / 1000)
                    out["where"].append(where)

                if cmd is None:                    # a rate snapshot
                    for rows, tags, _, calm in snapshots(o, slot, flip, supply_x2, is_worker, is_building, MAX_UNITS):
                        y = np.full(len(tags), -1, np.int8)
                        state = np.full(len(tags), -1, np.int8)
                        for i, t in enumerate(tags):
                            if t not in calm:
                                continue
                            u = by_tag[t]
                            k = bisect.bisect_left(cf, f)
                            hit = None
                            while k < len(cf) and cf[k] < f + LABEL:
                                if t in cmds[k]["units"]:
                                    hit = cmds[k]
                                    break
                                k += 1
                            y[i] = label(hit, u, mw, mh)
                            state[i] = 0 if u["order"] in STANDING else 1 if u["order"] in MOVING else 2
                        if (y >= 0).any():
                            keep(rows, tags, y, np.full((len(tags), 2), np.nan, np.float32), state, False)
                    continue
                calm = {u["tag"]: u for u in calm_fighters(o, slot, supply_x2, is_worker, is_building)}
                us = [calm[t] for t in cmd["units"] if t in calm]
                fighters = [t for t in cmd["units"] if t in by_tag and by_tag[t]["owner"] == slot and fighter(by_tag[t])]
                if not us or len(us) * 2 < len(fighters):
                    continue                       # (a command mostly for units in contact: the role model's)
                cx, cy = sum(u["x"] for u in us) / len(us), sum(u["y"] for u in us) / len(us)
                a, b = army_cell(cmd["x"], cmd["y"], mw, mh), army_cell(cx, cy, mw, mh)
                if (max(abs(a[0] - b[0]), abs(a[1] - b[1])) >= MOVED) != far:
                    continue                       # (short for the where data; far for the far data)
                if far and sum(supply_x2(u["type"]) for u in us) >= SMALL:
                    continue                       # (a far order for a cluster the commit model is asked about)
                key = frozenset(u["tag"] for u in us)
                before = kept.get(key)
                if before and f - before[0] < 24 and math.dist(before[1:], (cmd["x"], cmd["y"])) <= RECLICK:
                    continue                       # (the same click again within a second)
                kept[key] = (f, cmd["x"], cmd["y"])
                rows, tags = rows_at(o, slot, flip, (cx, cy), AROUND_OWN, AROUND_OTHER, MAX_UNITS)
                to = np.full((len(tags), 2), np.nan, np.float32)
                state = np.full(len(tags), -1, np.int8)
                for i, t in enumerate(tags):
                    if t in key:
                        to[i] = (fx * (cmd["x"] - cx) / 32, fy * (cmd["y"] - cy) / 32)
                        state[i] = 0 if calm[t]["order"] in STANDING else 1 if calm[t]["order"] in MOVING else 2
                if np.isfinite(to).any():
                    keep(rows, tags, np.full(len(tags), -1, np.int8), to, state, True)
        finally:
            g.close()
    except Exception as e:                         # (a replay that won't run: counted, skipped)
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--race", choices=("T", "Z", "P"), default="T")
    ap.add_argument("--matchups", default="TvZ", help="comma-joined")
    ap.add_argument("--games", type=int, default=300)
    ap.add_argument("--era", choices=("old", "modern", "both"), default="modern")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--far", action="store_true", help="the far data: where snapshots alone, at the far point commands "
                    "to calm bunches under SMALL supply (the calm layer's far points, for the calm_far model)")
    ap.add_argument("--out", help="default: data/interim/calm/calm[_far]_<race>_<matchups>.npz")
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    from ingest.inventory import data_root
    matchups = tuple(args.matchups.split(","))
    jobs = [(*j, args.far) for j in select(args.games, args.race, args.era, matchups)]
    with ProcessPoolExecutor(args.parallel) as pool:
        results = list(monitor.track(pool.map(_job, jobs, chunksize=1), len(jobs), "games"))
    n = sum(len(r["rows"]) for r in results)
    rows = np.zeros((n, MAX_UNITS, 11), np.int16)
    extra = np.zeros((n, MAX_UNITS, EXTRA + MAP_EXTRA), np.float16)
    labels = np.full((n, MAX_UNITS), -1, np.int8)
    to = np.full((n, MAX_UNITS, 2), np.nan, np.float16)
    state = np.full((n, MAX_UNITS), -1, np.int8)
    count = np.zeros(n, np.int16)
    time_s = np.zeros(n, np.float32)
    game = np.zeros(n, np.int32)
    where = np.zeros(n, bool)
    i = 0
    for gi, r in enumerate(results):
        for rr, e, y, t, s, ts, w in zip(r["rows"], r["extra"], r["labels"], r["to"], r["state"], r["time"], r["where"]):
            k = min(len(rr), MAX_UNITS)
            rows[i, :k], extra[i, :k], labels[i, :k], to[i, :k], state[i, :k] = rr[:k], e[:k], y[:k], t[:k], s[:k]
            count[i], time_s[i], game[i], where[i] = k, ts, gi, w
            i += 1
    out = Path(args.out) if args.out else data_root() / "interim" / "calm" / f"calm{'_far' if args.far else ''}_{args.race}_{'_'.join(matchups)}.npz"
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, rows=rows, extra=extra, labels=labels, cmd_to=to, state=state, count=count, time=time_s,
                        game=game, where=where, sha1=np.array([r["sha1"] for r in results]), names=np.array(NAMES))
    errors = [r["error"] for r in results if r["error"]]
    y = labels[labels >= 0]
    print(f"{len(results)} games ({len(errors)} errors{': ' + errors[0] if errors else ''}), {n} snapshots "
          f"({where.sum()} where), {len(y)} labeled calm fighters -> {out}")
    for name, m in (("all", labels >= 0), ("standing", (labels >= 0) & (state == 0)), ("moving", (labels >= 0) & (state == 1))):
        yy = labels[m]
        print(f"  {name:9s} " + ", ".join(f"{NAMES[k]} {np.mean(yy == k):.2%}" for k in range(len(NAMES)))
              + f"  (a fighter a minute, again: {np.mean(yy == NAMES.index(AGAIN)) * 120:.2f})")
    w = to[where].reshape(-1, 2).astype(np.float32)
    w = w[np.isfinite(w).all(1)]
    if len(w):
        d = np.hypot(w[:, 0], w[:, 1])
        print(f"  where: {len(w)} commanded units; the clicks a median {np.median(d):.1f} tiles from their middle")


if __name__ == "__main__":
    main()

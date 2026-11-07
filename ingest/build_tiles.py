"""The pros' building tiles per ladder map (#16: the tile, after the placement model's base and side): every building a
modern pro orders by 14:00 on a current ladder map (ingest/ladder_maps.py), its top-left tile as the build command
gives it (ingest/build_orders.py's positions), with its base (the main, the natural, or a base where the player orders
a town hall: the nearest to the building's centre of those, within BASE_TILES) and its side of that base (by the
minerals or the front, the placement dataset's rule), and the how-manieth of its type at that base it is. Gary's
executor takes a building's tile from one pro's game on the same map and start (gary/agent/executor.py tiles), so a
base's buildings stand as one pro's layout.

The player's main is the start base of their first gas building (always at the main's geyser), or else the start base
nearest their first building. Town halls and gas buildings are left out (the executor places those itself); cancelled
and never-built orders too, and builds beyond BASE_TILES of every base of the player's (proxies).

    python -m ingest.build_tiles --matchup PvZ --race P
Output: runs/tiles/<matchup>_<race>_<date>/tiles.json: per map hash its starts, and per game the player's main tile,
style and builds [type, base tile x, base tile y, side, tile x, tile y, frame, ordinal].
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

from inventory import data_root  # noqa: E402
from gary.race import Race  # noqa: E402
from gary.policy.placement import kinds as placed_kinds  # noqa: E402

MINUTES = 14
BASE_TILES = 16                   # a building this near a base's centre (tiles) can be that base's
NOT_BUILT = ("cancelled?", "not built")
MINERAL_SIDE, MINERAL_TILES = 0.3, 9   # the placement dataset's mineral side


def ladder_maps() -> dict[str, "MapInfo"]:
    """The current ladder maps' MapInfo by map hash."""
    from gary.env import Game
    from gary.mapinfo import MapInfo
    out = {}
    for rep in sorted((data_root() / "maps" / "ladder").glob("*.rep")):
        g = Game.new(rep, ["P", "Z"], seed=1)
        out[rep.with_suffix(".maphash").read_text().strip()] = MapInfo.from_game(g)
    return out


def side_of(x: float, y: float, base) -> int:
    """1 on the base's mineral side, else 0 (ingest/placement_dataset.py's rule)."""
    hx, hy = base.center
    mx = sum(m[0] for m in base.minerals) / len(base.minerals)
    my = sum(m[1] for m in base.minerals) / len(base.minerals)
    d = math.dist((x, y), (hx, hy))
    if d == 0 or d >= MINERAL_TILES * 32:
        return 0
    vx, vy, wx, wy = x - hx, y - hy, mx - hx, my - hy
    return int((vx * wx + vy * wy) / (d * math.hypot(wx, wy) + 1e-9) > MINERAL_SIDE)


def game_builds(items: list[dict], mi, R) -> dict | None:
    """One player's main tile and builds on a ladder map, or None (no main found)."""
    ids = {name: uid for uid, name in R.names.items()}
    kinds = set(placed_kinds(R))
    halls = {R.names[t] for t in R.town_halls}
    gas = R.names[R.gas_building]
    builds = [i for i in items if i["kind"] == "build" and i.get("pos") and i["conf"] not in NOT_BUILT
              and i["frame"] < MINUTES * 1440]
    starts = [b for b in mi.bases if b.start]
    if not builds or not starts:
        return None
    first = next((i for i in builds if i["name"] == gas and i["frame"] < 5 * 1440), builds[0])
    fx, fy = first["pos"]
    main = min(starts, key=lambda b: math.dist(b.tile, (fx, fy)))
    if math.dist(main.tile, (fx, fy)) > BASE_TILES:
        return None
    natural = mi.natural_of(main)
    bases = [main, natural]
    for i in builds:
        if i["name"] in halls:
            b = min(mi.bases, key=lambda b: math.dist(b.tile, i["pos"]))
            if math.dist(b.tile, i["pos"]) <= 2 and b not in bases:
                bases.append(b)
    out, count = [], defaultdict(int)
    for i in builds:
        uid = ids.get(i["name"])
        if uid not in kinds:
            continue
        w, h = R.sizes[uid]
        tx, ty = i["pos"]
        cx, cy = tx * 32 + w * 16, ty * 32 + h * 16
        b = min(bases, key=lambda b: math.dist(b.center, (cx, cy)))
        if math.dist(b.center, (cx, cy)) > BASE_TILES * 32:
            continue
        key = (uid, b.tile)
        out.append([uid, b.tile[0], b.tile[1], side_of(cx, cy, b), tx, ty, i["frame"], count[key]])
        count[key] += 1
    return {"main": list(main.tile), "builds": out}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--matchup", default="PvZ")
    ap.add_argument("--race", default="P")
    ap.add_argument("--out", default=str(REPO / "runs" / "tiles"))
    args = ap.parse_args()
    from gary import styles
    R = Race.of(args.race)
    maps = ladder_maps()
    inv = {}
    for line in open(data_root() / "interim" / "inventory.jsonl", encoding="utf-8"):
        r = json.loads(line)
        inv[r["sha1"]] = r
    labels = styles.catalog(args.matchup, args.race)["assignments"]
    out = {h: {"starts": [list(b.tile) for b in mi.bases if b.start], "games": []} for h, mi in maps.items()}
    t0, n = time.time(), 0
    for line in open(data_root() / "interim" / "build_orders.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["race"] != args.race or r["matchup"] != args.matchup or r["map_hash"] not in maps \
                or not r["rel_path"].startswith("cwal"):
            continue
        rec = inv.get(r["sha1"], {})
        if rec.get("has_bot_suspect") or rec.get("labeled_bot_game") or rec.get("dup_of") or not rec.get("is_1v1_human"):
            continue
        game = game_builds(r["items"], maps[r["map_hash"]], R)
        if game is None:
            continue
        game.update(sha1=r["sha1"], style=labels.get(f"{r['rel_path']}|{r['player']}", -1))
        out[r["map_hash"]]["games"].append(game)
        n += 1
    path = Path(args.out) / f"{args.matchup}_{args.race}_{time.strftime('%Y%m%d-%H%M%S')}" / "tiles.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out), encoding="utf-8")
    for h, m in out.items():
        per = defaultdict(int)
        for gm in m["games"]:
            per[tuple(gm["main"])] += 1
        print(h[:8], len(m["games"]), "games;", "per start", dict(per))
    print(f"{n} players' layouts, {time.time() - t0:.0f} s -> {path}")


if __name__ == "__main__":
    main()

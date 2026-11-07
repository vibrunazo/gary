"""How near the pros' tiles a race's buildings stand on the ladder maps (#16): per building type and base (the main, the
natural, newer), the share of buildings on a tile some pro used for that type at that base on the same map from the same
start (ingest/build_tiles.py's table), and the share of those pros' games that used that very tile (how common a spot
it is). The pros' own, each against the other pros (one left out at a time), are the check.

    python -m eval.tiles --matchup PvZ --race P                                         # the pros', leave one out
    python -m eval.tiles --matchup PvZ --race P --gary "runs/league/PL231a/*/*.rep"     # Gary's against them
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

from gary.race import Race  # noqa: E402

KINDS = ("main", "natural", "newer")
MIN_GAMES = 5                  # a key (type, base, side) counted where this many pros' games have it


def table(matchup: str, race: str) -> dict:
    runs = sorted((REPO / "runs" / "tiles").glob(f"{matchup}_{race}_*/tiles.json"))
    return json.loads(runs[-1].read_text(encoding="utf-8"))


def score(builds: list, pros: list[dict], main: tuple, natural: tuple, minutes: float, rows: dict, R) -> None:
    """Add a player's builds to rows[(type name, base kind)] = [n, on a pro's tile, share of pros' games there]."""
    by_key = defaultdict(list)
    for gm in pros:
        keys = defaultdict(set)
        for uid, bx, by, side, tx, ty, *_ in gm["builds"]:
            keys[uid, bx, by, side].add((tx, ty))
        for key, tiles in keys.items():
            by_key[key].append(tiles)
    for uid, bx, by, side, tx, ty, frame, _ in builds:
        games = by_key.get((uid, bx, by, side), [])
        if len(games) < MIN_GAMES or frame >= minutes * 1440:
            continue
        kind = "main" if (bx, by) == main else "natural" if (bx, by) == natural else "newer"
        share = sum(1 for tiles in games if (tx, ty) in tiles) / len(games)
        for k in ((R.names[uid], kind), ("all", kind), ("all", "all")):
            r = rows.setdefault(k, [0, 0, 0.0])
            r[0] += 1
            r[1] += share > 0
            r[2] += share


def report(rows: dict, label: str) -> None:
    print(f"\n{label}: buildings  on a pro's tile  pros' games with that tile")
    for (name, kind), (n, on, share) in sorted(rows.items(), key=lambda kv: (kv[0][0] != "all", -kv[1][0])):
        if n >= 10:
            print(f"  {name:22s} {kind:8s} {n:6d}  {on / n:6.0%}  {share / n:6.1%}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--matchup", default="PvZ")
    ap.add_argument("--race", default="P")
    ap.add_argument("--gary", help="Gary's replays (a glob; the map is the replay's folder name)")
    ap.add_argument("--minutes", type=float, default=12)
    ap.add_argument("--pros", type=int, default=400, help="pros' games left out one at a time")
    args = ap.parse_args()
    from ingest.build_tiles import game_builds, ladder_maps
    R = Race.of(args.race)
    t = table(args.matchup, args.race)
    maps = ladder_maps()
    rows: dict = {}
    if not args.gary:
        n = 0
        for h, m in t.items():
            mi = maps[h]
            for i, gm in enumerate(m["games"]):
                if n >= args.pros:
                    break
                main = tuple(gm["main"])
                natural = tuple(mi.natural_of(next(b for b in mi.bases if tuple(b.tile) == main)).tile)
                others = [o for j, o in enumerate(m["games"]) if j != i and tuple(o["main"]) == main]
                score(gm["builds"], others, main, natural, args.minutes, rows, R)
                n += 1
        return report(rows, f"the pros ({n} games, each against the others)")
    from cmdcache import load_game
    from build_orders import extract_player
    from inventory import data_root, find_screp
    by_name = {p.stem: p.with_suffix(".maphash").read_text().strip()
               for p in (data_root() / "maps" / "ladder").glob("*.rep")}
    screp = find_screp(None)
    n = 0
    for path in sorted(glob.glob(args.gary)):
        h = by_name.get(Path(path).parent.name)
        if h is None:
            continue
        game = load_game(screp, Path(path), hashlib.sha1(Path(path).read_bytes()).hexdigest(),
                         data_root() / "interim" / "cmdcache")
        player = next((p for p in game["players"] if p["race"] == args.race and not p["observer"]), None)
        if player is None:
            continue
        cmds = [c for c in game["cmds"] if c[1] == player["id"]]
        gb = game_builds(extract_player(cmds, args.race)[0], maps[h], R)
        if gb is None:
            continue
        mi, main = maps[h], tuple(gb["main"])
        natural = tuple(mi.natural_of(next(b for b in mi.bases if tuple(b.tile) == main)).tile)
        pros = [o for o in t[h]["games"] if tuple(o["main"]) == main]
        score(gb["builds"], pros, main, natural, args.minutes, rows, R)
        n += 1
    report(rows, f"Gary ({n} games)")


if __name__ == "__main__":
    main()

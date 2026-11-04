"""Where a race's buildings start, Gary's against the modern pros': per building and minute window, the base it
stands at (by its town hall's order: the main, the natural, a newer base) and its side of that base (the mineral side,
within MINERAL_TILES of the town hall toward its minerals, or the front), and how near a mineral-side building stands to
its workers' lanes (the gap from its footprint to the nearest town hall-to-mineral segment: gary/protoss.py PLACE_LANE).
The pros' shares, each building's first and second of the game apart, are Gary's check (the learned placement model,
gary/policy/placement.py, replaced the table they were drawn from in gp0.21dev).
Re-simulated, the full game state (not Gary's view).

    python -m eval.placement --race P --matchup PvZ --pros 60                          # the pros' shares
    python -m eval.placement --race P --matchup PvZ --gary "runs/league/BL191a/*/*.rep"   # Gary's, against it
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import random
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

from eval import monitor, priority

MINUTES = 12
WINDOWS = ((0, 5), (5, 8), (8, MINUTES))
MINERALS = (176, 177, 178)
EVERY = 48                     # frames between looks
MINERAL_SIDE = 0.3             # cos(building - hall, minerals - hall) over this: the mineral side ...
MINERAL_TILES = 9              # ... and this near its town hall
CLASSES = ("main", "natural", "newer")
LANE_MIN = 10                  # mineral-side starts for a building's gap to the workers' lanes
FIRSTS = 2                     # a building's first and second of the game get their own shares
FIRST_MIN = 0.3                # ... where they come in this many games at least
STYLE_MIN = 20                 # a build style's own firsts from this many of its games (gary/styles.py's labels)


def starts(args: tuple) -> list[dict] | None:
    """Every building of the race's player started by MINUTES: its type, minute, base (the main, the natural, a newer
    one: the town hall it stands nearest of all the player's by MINUTES, by their order; a forge-first wall at the
    natural before its Nexus is the natural's) and side."""
    path, race = args
    from gary.env import Game
    from gary.agent.executor import _to_segment
    from gary.race import Race
    R = Race.of(race)
    halls, kinds = set(R.town_halls), {t for t in R.sizes if t not in R.town_halls and t != R.gas_building}
    try:
        g = Game.scenario(path)
    except Exception:
        return None
    slot, hall_at, seen, out = None, {}, set(), []
    while g.frame < MINUTES * 1440:
        try:
            g.step(EVERY)
        except Exception:
            break
        units = g.observe()["units"]
        if slot is None:
            owners = [u["owner"] for u in units if u["type"] in halls]
            if not owners:
                continue
            slot = owners[0]
        mine = [u for u in units if u["owner"] == slot]
        for u in mine:
            if u["type"] in halls and u["tag"] not in hall_at:
                ms = [m for m in units if m["type"] in MINERALS and math.dist((m["x"], m["y"]), (u["x"], u["y"])) < 12 * 32]
                mc = (sum(m["x"] for m in ms) / len(ms), sum(m["y"] for m in ms) / len(ms)) if ms else None
                hall_at[u["tag"]] = (min(len(hall_at) + 1, 3), u["x"], u["y"], mc, [(m["x"], m["y"]) for m in ms])
        for u in mine:
            if u["type"] in kinds and u["tag"] not in seen:
                seen.add(u["tag"])
                out.append((u["type"], g.frame / 1440, u["x"], u["y"]))
    if not hall_at:
        return None
    rows = []
    for t, minute, x, y in out:
        k, hx, hy, mc, ms = min(hall_at.values(), key=lambda h: math.dist((h[1], h[2]), (x, y)))
        d = math.dist((hx, hy), (x, y))
        side, lane = "front", None
        if mc is not None and d > 0:
            vx, vy, wx, wy = x - hx, y - hy, mc[0] - hx, mc[1] - hy
            if (vx * wx + vy * wy) / (d * math.hypot(wx, wy) + 1e-9) > MINERAL_SIDE and d < MINERAL_TILES * 32:
                side = "minerals"
                lane = (min(_to_segment((x, y), (hx, hy), m) for m in ms) - 16 * max(R.sizes[t])) / 32
        rows.append({"type": R.names.get(t, t), "id": t, "t": minute, "base": CLASSES[k - 1], "side": side,
                     "lane": lane, "hall": d / 32})
    return rows


def table(games: list[list[dict]]) -> dict:
    """{building id: [(until minute, (main, natural, newer) shares, mineral side share, starts a game)]}."""
    out = {}
    for t in sorted({b["id"] for g in games for b in g}):
        rows = []
        for lo, hi in WINDOWS:
            w = [b for g in games for b in g if b["id"] == t and lo <= b["t"] < hi]
            if not w:
                continue
            c = Counter(b["base"] for b in w)
            rows.append((hi, tuple(round(c[k] / len(w), 2) for k in CLASSES),
                         round(sum(b["side"] == "minerals" for b in w) / len(w), 2), round(len(w) / len(games), 1)))
        out[t] = rows
    return out


def firsts(games: list[list[dict]]) -> dict:
    """{building id: [((main, natural, newer) shares, mineral side share, games with it)] for its first FIRSTS of the
    game}: a window's shares mix them, while the pros' first Pylon in PvZ stands at the natural in 92% of games and the
    second in the main in 84% (the window's share 47%), and the first Gateway with the first Pylon in all 80."""
    out = {}
    for t in sorted({b["id"] for g in games for b in g}):
        rows = []
        for i in range(FIRSTS):
            w = [s[i] for g in games if len(s := sorted((b for b in g if b["id"] == t), key=lambda b: b["t"])) > i]
            if len(w) < FIRST_MIN * len(games):
                break
            c = Counter(b["base"] for b in w)
            rows.append((tuple(round(c[k] / len(w), 2) for k in CLASSES),
                         round(sum(b["side"] == "minerals" for b in w) / len(w), 2), round(len(w) / len(games), 2)))
        if rows:
            out[t] = rows
    return out


def lanes(games: list[list[dict]], names: dict) -> dict:
    """{building: the median gap of its mineral-side starts to the workers' lanes, in tiles}, LANE_MIN starts at least
    (the race's PLACE_LANE, the executor's limit by the minerals)."""
    out = {}
    for t in sorted({b["id"] for g in games for b in g}):
        gaps = sorted(b["lane"] for g in games for b in g if b["id"] == t and b["lane"] is not None)
        if len(gaps) >= LANE_MIN:
            out[names.get(t, t)] = round(gaps[len(gaps) // 2], 1)
    return out


def summary(name: str, games: list[list[dict]], names: dict) -> None:
    print(f"== {name}: {len(games)} games")
    for t, rows in table(games).items():
        print(f"  {names.get(t, t)}: " + " | ".join(f"to {hi}: {n}/game, main/natural/newer "
                                                   f"{'/'.join(f'{s:.0%}' for s in shares)}, mineral side {m:.0%}"
                                                   for hi, shares, m, n in rows))
        side = sorted((b["lane"], b["hall"]) for g in games for b in g if b["id"] == t and b["lane"] is not None)
        if len(side) >= 5:
            q = lambda xs, f: xs[int(f * (len(xs) - 1))]
            lanes, halls = [a for a, _ in side], sorted(h for _, h in side)
            print(f"    by the minerals ({len(side)}): gap to the workers' lanes 10/50/90% "
                  f"{q(lanes, .1):.1f}/{q(lanes, .5):.1f}/{q(lanes, .9):.1f} tiles, from the town hall "
                  f"{q(halls, .1):.1f}/{q(halls, .5):.1f}/{q(halls, .9):.1f}")
    for t, rows in firsts(games).items():
        print(f"  {names.get(t, t)}'s firsts: " + " | ".join(
            f"#{i + 1} in {n:.0%} of games, main/natural/newer {'/'.join(f'{s:.0%}' for s in shares)}, mineral side {m:.0%}"
            for i, (shares, m, n) in enumerate(rows)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--race", default="P")
    ap.add_argument("--matchup", default="PvZ")
    ap.add_argument("--gary", nargs="*", default=[], help="globs of Gary's replays (its side: the race's player)")
    ap.add_argument("--pros", type=int, default=0, help="this many modern pro games of the matchup (clean, 8+ minutes)")
    ap.add_argument("--workers", type=int, default=8)
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    from gary.race import Race
    names = Race.of(args.race).names
    sets = [(pattern, sorted(glob.glob(pattern))) for pattern in args.gary]
    if args.pros:
        from inventory import data_root
        from eval.humanlike import clean_replays
        clean = clean_replays()
        recs = []
        with open(data_root() / "interim" / "build_orders.jsonl", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("matchup") == args.matchup and r.get("race") == args.race and r.get("source") == "cwal" \
                        and r["rel_path"] in clean and r.get("duration_s", 0) >= 480:
                    recs.append(r)
        random.Random(0).shuffle(recs)
        recs = recs[:args.pros]
        from gary import styles
        labels = styles.catalog(args.matchup, args.race)["assignments"]
        style_of = [labels.get(f"{r['rel_path']}|{r['player']}") for r in recs]
        sets.append(("pros", [str(data_root() / "raw" / r["rel_path"]) for r in recs]))
    with ProcessPoolExecutor(args.workers) as pool:
        for name, paths in sets:
            jobs = [(p, args.race) for p in paths]
            done = list(monitor.track(pool.map(starts, jobs), len(jobs), f"replays: {name}"))
            games = [g for g in done if g is not None]
            summary(name, games, names)
            if name == "pros":
                print("  the table:", json.dumps({names.get(t, t): rows for t, rows in table(games).items()}))
                print("  the lanes:", json.dumps(lanes(games, names)))
                print("  the firsts:", json.dumps({names.get(t, t): rows for t, rows in firsts(games).items()}))
                # (an opening is one plan: the pros' Forge stands with their first Gateway in a gateway-first PvZ game,
                # drawn apart it stood in the main and the natural walled nothing, round PL209a)
                by = {}
                for g, st in zip(done, style_of):
                    if g is not None and st is not None:
                        by.setdefault(st, []).append(g)
                print("  the firsts by style:", json.dumps({st: {names.get(t, t): rows for t, rows in firsts(gs).items()}
                                                            for st, gs in sorted(by.items()) if len(gs) >= STYLE_MIN}))
                print("  games by style:", json.dumps({st: len(gs) for st, gs in sorted(by.items())}))


if __name__ == "__main__":
    main()

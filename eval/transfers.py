"""Workers at a new base as its town hall finishes, Gary's against the modern pros': per new base (the second base
taken, the third), the workers within NEAR of it when its town hall starts, when it finishes and FOLLOW seconds after,
and the workers at the bases it already had then (per mineral patch). A base without workers when it finishes reads to
the placement model as one nobody uses (Gary-Z's first colony stood in the main in 25% of TZ240a's games, the pros' 2%:
its natural had drones from its rally only, the pros 2.5 there before 3:30). Re-simulated, the full game state.

    python -m eval.transfers --race Z --matchup TvZ --pros 120
    python -m eval.transfers --race Z --matchup TvZ --gary "runs/league/TZ240a/*/*.rep"
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

from eval import monitor, priority  # noqa: E402

MINUTES = 14
EVERY = 24                      # frames between looks
NEAR = 10 * 32                  # px: a worker this near a base's centre is at it
HELD = 6 * 32                   # px: a town hall this near a base's centre takes it
FOLLOW = (15, 30, 60)           # seconds after the town hall finishes
BASES = 2                       # the second and third bases taken


def follow(args: tuple) -> list[dict] | None:
    """The race's player's new bases by MINUTES: [{"k": the how-manieth base, "start", "done": minutes, "at_start",
    "at_done", "after": [workers at FOLLOW], "old_sat": workers a patch at its older bases when it finished}]."""
    path, race = args
    from gary.env import Game
    from gary.mapinfo import MapInfo
    from gary.race import Race
    R = Race.of(race)
    try:
        g = Game.scenario(path)
        mi = MapInfo.from_game(g)
    except Exception:
        return None
    slot, bases, out = None, [], {}       # bases: [(base, hall tag)] in the order taken
    while g.frame < MINUTES * 1440 + max(FOLLOW) * 24:
        try:
            g.step(EVERY)
        except Exception:
            break
        units = g.observe()["units"]
        if slot is None:
            owners = [u["owner"] for u in units if u["type"] in R.town_halls]
            if not owners:
                continue
            slot = owners[0]
        mine = [u for u in units if u["owner"] == slot]
        workers = [u for u in mine if u["type"] == R.worker]
        at = lambda b: sum(1 for w in workers if math.dist(b.center, (w["x"], w["y"])) < NEAR)
        for u in mine:
            if u["type"] not in R.town_halls or any(t == u["tag"] for _, t in bases) or g.frame > MINUTES * 1440:
                continue
            b = mi.base_near((u["x"], u["y"]))
            if b is None or math.dist(b.center, (u["x"], u["y"])) > HELD or any(bb is b for bb, _ in bases):
                continue                       # (a macro hatchery in a base already held)
            bases.append((b, u["tag"]))
            if 2 <= len(bases) <= 1 + BASES:
                out[u["tag"]] = {"k": len(bases), "start": g.frame / 1440, "at_start": at(b), "done": None, "after": []}
        for b, tag in bases:
            r = out.get(tag)
            if r is None:
                continue
            u = next((v for v in mine if v["tag"] == tag), None)
            if r["done"] is None and u is not None and u["completed"]:
                r["done"], r["at_done"], r["_f"] = g.frame / 1440, at(b), g.frame
                older = [bb for bb, t in bases if t != tag and out.get(t, {}).get("done", 0) is not None]
                patches = sum(len(bb.minerals) for bb in older) or 1
                r["old_sat"] = round(sum(at(bb) for bb in older) / patches, 2)
                r["_older"], r["patches"] = older, len(b.minerals) or 1
            if r["done"] is not None and len(r["after"]) < len(FOLLOW) and g.frame >= r["_f"] + FOLLOW[len(r["after"])] * 24:
                r["after"].append(at(b))
                # (the ratio of the new base's workers a patch to the older's, at each FOLLOW)
                old = sum(at(bb) for bb in r["_older"]) / (sum(len(bb.minerals) for bb in r["_older"]) or 1)
                r.setdefault("ratios", []).append(round(r["after"][-1] / r["patches"] / old, 2) if old else None)
    rows = [{k: v for k, v in r.items() if k not in ("_f", "_older")} for r in out.values()
            if r["done"] is not None and len(r["after"]) == len(FOLLOW)]
    return rows


def summary(name: str, games: list[list[dict]]) -> None:
    print(f"== {name}: {len(games)} games")
    for k in range(2, 2 + BASES):
        rows = [r for gm in games for r in gm if r["k"] == k]
        if not rows:
            continue
        q = lambda xs, f: sorted(xs)[int(f * (len(xs) - 1))]
        mean = lambda key: sum(r[key] for r in rows) / len(rows)
        after = [sum(r["after"][i] for r in rows) / len(rows) for i in range(len(FOLLOW))]
        print(f"  base {k} ({len(rows)}): finished at {q([r['done'] for r in rows], .5):.1f} min (median); workers at it: "
              f"at its start {mean('at_start'):.1f}, finished {mean('at_done'):.1f}, "
              + ", ".join(f"+{s}s {a:.1f}" for s, a in zip(FOLLOW, after))
              + f"; none at it finished {sum(r['at_done'] == 0 for r in rows) / len(rows):.0%}, "
                f"at +{FOLLOW[0]}s {sum(r['after'][0] == 0 for r in rows) / len(rows):.0%}; "
                f"the older bases' workers a patch then {mean('old_sat'):.2f}; its workers a patch to theirs (median) "
              + ", ".join(f"+{t}s {q(v, .5):.2f}" for i, t in enumerate(FOLLOW)
                          if (v := [r['ratios'][i] for r in rows if r['ratios'][i] is not None])))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--race", default="Z")
    ap.add_argument("--matchup", default="TvZ")
    ap.add_argument("--gary", nargs="*", default=[], help="globs of Gary's replays (its side: the race's player)")
    ap.add_argument("--pros", type=int, default=0, help="this many modern pro games of the matchup (clean, 8+ minutes)")
    ap.add_argument("--end", type=float, help="the games' length in minutes (Gary's rounds: --minutes); a base finished "
                    "less than the last FOLLOW before it is left out (nobody plays on after a replay's end)")
    ap.add_argument("--workers", type=int, default=4)
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
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
        sets.append(("pros", [str(data_root() / "raw" / r["rel_path"]) for r in recs[:args.pros]]))
    with ProcessPoolExecutor(args.workers) as pool:
        for name, paths in sets:
            jobs = [(p, args.race) for p in paths]
            games = [g for g in monitor.track(pool.map(follow, jobs), len(jobs), f"replays: {name}") if g is not None]
            if args.end and name != "pros":
                games = [[r for r in gm if r["done"] <= args.end - max(FOLLOW) / 60] for gm in games]
            summary(name, games)


if __name__ == "__main__":
    main()

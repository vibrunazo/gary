"""The scouting counts (docs/REFOCUS.md §3.1 and §4.3, Phase 1 step 2): what a player saw of the enemy's tech, when, and
by what means, the same function for the pros and for Gary, every race and matchup.

One pass a replay (gary.env Game.scenario, the replay playing its own commands), both players' views, a look every
LOOK_EVERY frames to UNTIL; per player it logs:
  tech     each enemy tech building of the race's table (TECH, from taxonomy/label_all.py's plan rules) and the units that
           tell a plan (TELL): when it first stood (any player's view: the game's truth), when the player first had it in
           sight, and by what: a scan (a Comsat scan of the player's within SCAN_SEES of it, in the SCAN_LASTS before) or
           the type of the player's unit nearest it, with the distance
  scans    each Comsat scan (a Comsat of the player's losing 50 energy between looks; the observation has no sweep unit,
           the scanned place turns visible: checked 2026-11-23) with its point (the replay's command, by screp: neither
           the observation nor the re-simulator's unit commands carry it), what it showed, the Comsats' age, and whether
           the plan's tech had been seen before
  exposure per look, the player's Comsats with a scan's energy and whether the plan's tech was seen yet (the scans' hazard)
  scout    the first own worker at the enemy's main (within NEAR_MAIN of its start and nearer it than its natural): arrival,
           how long it stayed (until gone LEFT_FOR), and the first own unit of any type there
  main     when the enemy's main was known (gary/policy/sightings.py EnemyMain, the player's view) and whether right
  looks    per enemy tech building standing at a look: was it within the player's sight by gary/policy/sightings.py's
           model (a unit's or building's sight radius, a scan's) and was it in sight (does the model hold?); and the
           first try, a unit within LOOK of its base's center (refuted: "proxy")
  sight    seconds with an enemy unit in sight at 3:00-6:00

    python -m eval.scouting --pros --matchups TvZ PvT PvZ PvP ZvZ TvT --games 150 --out runs/scouting/pros
    python -m eval.scouting --rounds RD285a HS284a --race T --out runs/scouting/gary
    python -m eval.scouting --report runs/scouting/pros runs/scouting/gary
Output: <out>/events.jsonl (one line a player-game) and the report printed (and <out>/report.json).
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

from eval import monitor, priority  # noqa: E402

LOOK_EVERY = 48               # frames (2 s)
UNTIL = 10 * 60 * 24          # frames: the first ten minutes
NEAR_MAIN = 20 * 32           # px: a unit this near the enemy's start (and nearer it than its natural) is at its main
LEFT_FOR = 10 * 24            # frames: gone this long, the scout has left
LOOK = 8 * 32                 # px: the looking proxy (gary/policy/sightings.py LOOK)
SCAN_SEES = 10 * 32           # px: a scan's sight (10 tiles)
SCAN_LASTS = 7 * 24           # frames: a scan's sweep stays about this long
BUILDING_SLACK = 2.5 * 32     # px: a building is in sight when any part is: its center this beyond a sight radius
SCAN_ENERGY = 50
COMSAT = 107
HALLS = {"Z": (131, 132, 133), "T": (106,), "P": (154,)}
WORKER = {"Z": 41, "T": 7, "P": 64}
# the tech each race's plans are told by (taxonomy/label_all.py: the Zerg's spire / lurker / hydralisk plans, the Terran's
# Factory / Starport / Barracks, the Protoss's Robotics / Citadel / Stargate), with the tech that tells no plan (a Lair)
TECH = {"Z": {132: "Lair", 141: "Spire", 137: "Greater Spire", 135: "Hydralisk Den", 133: "Hive", 138: "Queens Nest",
              142: "Spawning Pool", 139: "Evolution Chamber"},
        "T": {111: "Barracks", 113: "Factory", 114: "Starport", 112: "Academy", 123: "Armory", 116: "Science Facility",
              120: "Machine Shop", 122: "Engineering Bay"},
        "P": {160: "Gateway", 164: "Cybernetics Core", 155: "Robotics Facility", 163: "Citadel of Adun",
              167: "Stargate", 165: "Templar Archives", 159: "Observatory", 166: "Forge"}}
TELL = {"Z": {97: "Lurker Egg", 103: "Lurker", 43: "Mutalisk", 38: "Hydralisk"},
        "T": {5: "Siege Tank", 2: "Vulture", 30: "Siege Tank (sieged)", 8: "Wraith", 34: "Medic"},
        "P": {83: "Reaver", 66: "Dragoon", 65: "Zealot", 84: "Observer", 60: "Corsair", 61: "Dark Templar"}}
# the plan's tech, the scouting measure's "Spire or Den" for each race (Lair apart)
PLAN_TECH = {"Z": {141, 137, 135}, "T": {113, 114}, "P": {155, 163, 167}}
MINUTES = (5, 6, 7, 8)


def scan_points(replay: str) -> list[tuple[int, int, int]]:
    """(frame, x, y) of every Comsat scan command in the replay (screp; its players' ids aren't the game's slots)."""
    from inventory import find_screp
    out = subprocess.run([find_screp(None), "-indent=false", "-cmds", replay], capture_output=True, timeout=120)
    if out.returncode:
        return []
    d = json.loads(out.stdout.decode("utf-8", "replace"))
    pts = []
    for c in (d.get("Commands") or {}).get("Cmds") or []:
        if (c.get("Order") or {}).get("Name") == "CastScannerSweep" and c.get("Pos"):
            pts.append((int(c["Frame"]), int(c["Pos"]["X"]), int(c["Pos"]["Y"])))
    return pts


def _place(p, mapinfo, own_start, enemy_start) -> str:
    """A point's place for a player: the enemy's main, its natural, another base of the map, the player's own main or
    natural, or the field."""
    b = mapinfo.base_near(p)
    if math.dist(b.center, p) > 12 * 32:
        return "field"
    if b is enemy_start:
        return "enemy main"
    if b is mapinfo.natural_of(enemy_start):
        return "enemy natural"
    if b is own_start or b is mapinfo.natural_of(own_start):
        return "own base"
    return "other base"


def game_events(job: tuple) -> list[dict] | str:
    """One replay: a dict per player (both, or only `only` slot's race), or the reason it failed."""
    from gary.env import Game
    from gary.mapinfo import MapInfo
    from gary.policy.army import is_building
    from gary.policy.sightings import EnemyMain, SCAN_SEES as SEES, covered, sight_px
    replay, tag, only_race = job
    try:
        g = Game.scenario(replay)
    except Exception as e:  # noqa: BLE001
        return f"scenario: {type(e).__name__}: {e}"
    try:
        scans_cmd = scan_points(replay)
        g.step(24)
        obs = g.observe()
        mi = MapInfo.from_game(g)
        halls = {}
        for u in obs["units"]:
            for race, types in HALLS.items():
                if u["type"] in types and u["owner"] != 11 and u["owner"] not in halls:
                    halls[u["owner"]] = (race, mi.base_near((u["x"], u["y"])))
        if len(halls) != 2:
            return f"{len(halls)} players with a town hall"
        slots = sorted(halls)
        P = {}
        for s in slots:
            race, own = halls[s]
            e = [x for x in slots if x != s][0]
            erace, estart = halls[e]
            if only_race and race != only_race:
                continue
            starts = [b.center for b in mi.bases if b.start and b is not own] or [estart.center]
            P[s] = {"slot": s, "race": race, "enemy": erace, "own": own, "estart": estart, "e": e,
                    "enat": mi.natural_of(estart).center, "sight": Counter(),
                    "finder": EnemyMain(starts, is_building), "main_at": None, "main_right": None,
                    "stood": {}, "seen": {}, "means": {}, "scans": [], "exposure": [], "energy": {}, "comsat_first": None,
                    "scout_in": None, "scout_out": None, "scout_last": None, "first_unit": None, "sight_s": 0,
                    "looks": Counter(), "plan_seen_at": None}
        if not P:
            return "no player of the race"
        used_cmd = set()
        while g.frame < UNTIL:
            g.step(LOOK_EVERY)
            o = g.observe()
            f = g.frame
            units = o["units"]
            for s, p in P.items():
                mine = [u for u in units if u["owner"] == s]
                vis = [u for u in units if u["owner"] == p["e"] and (u.get("visible_to", 0) >> s) & 1]
                theirs = [u for u in units if u["owner"] == p["e"]]
                tech, tell = TECH[p["enemy"]], TELL[p["enemy"]]
                # scans: a Comsat that lost a scan's energy since the last look
                comsats = [u for u in mine if u["type"] == COMSAT and u["completed"]]
                if comsats and p["comsat_first"] is None:
                    p["comsat_first"] = f
                for c in comsats:
                    before = p["energy"].get(c["tag"])
                    if before is not None and before - (c.get("energy") or 0) >= SCAN_ENERGY - 5:
                        cand = [(abs(fc - f), k, (x, y)) for k, (fc, x, y) in enumerate(scans_cmd)
                                if k not in used_cmd and f - 2 * LOOK_EVERY <= fc <= f]
                        pt = None
                        if cand:
                            _, k, pt = min(cand)
                            used_cmd.add(k)
                        showed = sorted({tech.get(u["type"]) or tell.get(u["type"]) for u in vis if pt is not None
                                         and math.dist((u["x"], u["y"]), pt) <= SCAN_SEES
                                         and (u["type"] in tech or u["type"] in tell)} - {None})
                        p["scans"].append({"f": f, "at": list(pt) if pt else None,
                                           "place": _place(pt, mi, p["own"], p["estart"]) if pt else None,
                                           "showed": showed, "comsat_age": f - p["comsat_first"],
                                           "plan_seen": p["plan_seen_at"] is not None})
                    p["energy"][c["tag"]] = c.get("energy") or 0
                p["exposure"].append((f, sum(1 for c in comsats if (c.get("energy") or 0) >= SCAN_ENERGY),
                                      int(p["plan_seen_at"] is not None)))
                recent = [sc["at"] for sc in p["scans"] if sc["at"] and f - sc["f"] <= SCAN_LASTS]
                # tech: stood and seen
                for u in theirs:
                    if u["type"] in tech or u["type"] in tell:
                        p["stood"].setdefault(u["type"], f)
                for u in vis:
                    t = u["type"]
                    if (t in tech or t in tell) and t not in p["seen"]:
                        p["seen"][t] = f
                        if t in PLAN_TECH[p["enemy"]] and p["plan_seen_at"] is None:
                            p["plan_seen_at"] = f
                        if any(math.dist((u["x"], u["y"]), a) <= SCAN_SEES for a in recent):
                            p["means"][t] = ["scan", None]
                        elif mine:
                            n = min(mine, key=lambda m: math.dist((m["x"], m["y"]), (u["x"], u["y"])))
                            p["means"][t] = [n["type"], round(math.dist((n["x"], n["y"]), (u["x"], u["y"])) / 32, 1)]
                # the sight model (and the refuted proxy) against the sight, for every enemy tech building standing
                pos = [(m["x"], m["y"]) for m in mine]
                vis_tags = {u["tag"] for u in vis}
                eyes = np.array(pos + [tuple(a) for a in recent], np.float64).reshape(-1, 2)
                radii = np.array([sight_px(m["type"]) for m in mine] + [SEES] * len(recent), np.float64)
                for u in theirs:
                    if u["type"] in tech:
                        b = mi.base_near((u["x"], u["y"])).center
                        proxy = any(math.dist(q, b) <= LOOK for q in pos) or any(math.dist(a, b) <= SCAN_SEES for a in recent)
                        p["looks"][f"{int(proxy)}{int(u['tag'] in vis_tags)}"] += 1
                        model = bool(covered(np.array([(u["x"], u["y"])], np.float64), eyes, radii + BUILDING_SLACK)[0])
                        p["sight"][f"{int(model)}{int(u['tag'] in vis_tags)}"] += 1
                # the enemy's main, as the player could know it
                if p["main_at"] is None and p["finder"].look(pos, vis) is not None:
                    p["main_at"] = f
                    p["main_right"] = math.dist(p["finder"].main, p["estart"].center) < 4 * 32
                # the first scout
                at_main = [m for m in mine if math.dist((m["x"], m["y"]), p["estart"].center) <= NEAR_MAIN
                           and math.dist((m["x"], m["y"]), p["estart"].center) < math.dist((m["x"], m["y"]), p["enat"])
                           and not is_building(m["type"])]
                if at_main and p["first_unit"] is None:
                    p["first_unit"] = [at_main[0]["type"], f]
                workers = [m for m in at_main if m["type"] == WORKER[p["race"]]]
                if workers:
                    if p["scout_in"] is None:
                        p["scout_in"] = f
                    if p["scout_out"] is None:
                        p["scout_last"] = f
                elif p["scout_in"] is not None and p["scout_out"] is None and f - p["scout_last"] >= LEFT_FOR:
                    p["scout_out"] = p["scout_last"]
                if 180 * 24 <= f < 360 * 24 and vis:
                    p["sight_s"] += LOOK_EVERY / 24
            if not any(u["owner"] in P for u in units):
                break
        out = []
        for s, p in P.items():
            out.append({"replay": tag, "slot": s, "race": p["race"], "enemy": p["enemy"], "map": mi.name if hasattr(mi, "name") else None,
                        "starts": sum(1 for b in mi.bases if b.start), "end": g.frame,
                        "stood": {str(k): v for k, v in p["stood"].items()}, "seen": {str(k): v for k, v in p["seen"].items()},
                        "means": {str(k): v for k, v in p["means"].items()}, "scans": p["scans"],
                        "exposure": p["exposure"], "comsat_first": p["comsat_first"],
                        "scout": [p["scout_in"], p["scout_out"] if p["scout_out"] is not None else p["scout_last"]],
                        "first_unit": p["first_unit"], "main_at": p["main_at"], "main_right": p["main_right"],
                        "looks": dict(p["looks"]), "sight": dict(p["sight"]), "sight_s": p["sight_s"],
                        "plan_seen_at": p["plan_seen_at"]})
        return out
    except Exception as e:  # noqa: BLE001 - reported, not dropped
        return f"{type(e).__name__}: {e}"
    finally:
        g.close()


def pro_jobs(matchups: list[str], games: int) -> list[tuple]:
    """A seeded sample of each matchup's modern pro games (the macro dataset's index: re-simulated clean)."""
    from inventory import data_root
    root = data_root()
    by = defaultdict(list)
    seen = set()
    for line in open(root / "interim" / "macro" / "v1" / "index.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("ok") and r.get("matchup") in matchups and r["rel_path"].startswith("cwal/") \
                and r.get("end_frame", 0) >= 300 and r["rel_path"] not in seen:
            seen.add(r["rel_path"])
            by[r["matchup"]].append(r["rel_path"])
    rng = np.random.default_rng(0)
    out = []
    for m in matchups:
        rels = sorted(by[m])
        pick = rng.choice(len(rels), min(games, len(rels)), replace=False) if rels else []
        out += [(str(root / "raw" / rels[k]), f"pro/{m}/{rels[k]}", None) for k in sorted(pick)]
    return out


def gary_jobs(rounds: list[str], race: str) -> list[tuple]:
    return [(str(p), f"gary/{r}/{p.parent.name}/{p.name}", race) for r in rounds
            for p in sorted((REPO / "runs" / "league" / r).rglob("*.rep"))]


def run(jobs: list[tuple], out: Path, workers: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    failed = Counter()
    n = 0
    with ProcessPoolExecutor(workers) as pool, open(out / "events.jsonl", "w", encoding="utf-8") as fh:
        for res in monitor.track(pool.map(game_events, jobs, chunksize=1), len(jobs), "games"):
            if isinstance(res, str):
                failed[res.split(":")[0]] += 1
                continue
            for r in res:
                fh.write(json.dumps(r) + "\n")
                n += 1
    print(f"{n} player-games from {len(jobs)} replays; failed: {dict(failed) or 'none'}")


def _share(xs) -> str:
    xs = list(xs)
    return f"{np.mean(xs):.0%} (n {len(xs)})" if xs else "- (n 0)"


def report(dirs: list[str]) -> dict:
    rows = []
    for d in dirs:
        rows += [{**json.loads(l), "source": d} for l in open(Path(d) / "events.jsonl", encoding="utf-8")]
    out = {}
    groups = defaultdict(list)
    for r in rows:
        who = "gary" if r["replay"].startswith("gary/") else "pros"
        groups[(who, f"{r['race']}v{r['enemy']}")].append(r)
    for (who, mu), rs in sorted(groups.items()):
        res = {"player_games": len(rs)}
        print(f"\n== {who}, {mu} (the {rs[0]['race']}'s view of the {rs[0]['enemy']}): {len(rs)} player-games")
        er = rs[0]["enemy"]
        # seen given that it stood, by type and minute
        tab = {}
        for t, name in {**TECH[er], **TELL[er]}.items():
            cells = {}
            for m in MINUTES:
                f = m * 60 * 24
                stood = [r for r in rs if r["stood"].get(str(t), 1e12) <= f and r["end"] >= f]
                cells[m] = [r["seen"].get(str(t), 1e12) <= f for r in stood]
            if any(cells.values()):
                tab[name] = {m: (float(np.mean(v)) if v else None, len(v)) for m, v in cells.items()}
                print(f"  {name:22s} seen by 5/6/7/8 min given it stood: " +
                      ", ".join(f"{m}: {_share(cells[m])}" for m in MINUTES))
        res["seen_given_stood"] = tab
        plan = PLAN_TECH[er]
        pt = {}
        for m in MINUTES:
            f = m * 60 * 24
            stood = [r for r in rs if min((r["stood"].get(str(t), 1e12) for t in plan)) <= f and r["end"] >= f]
            pt[m] = [r["plan_seen_at"] is not None and r["plan_seen_at"] <= f for r in stood]
        print("  the plan's tech (" + "/".join(TECH[er].get(t, str(t)) for t in sorted(plan)) + ") seen given it stood: "
              + ", ".join(f"{m}: {_share(pt[m])}" for m in MINUTES))
        res["plan_tech_seen"] = {m: (float(np.mean(v)) if v else None, len(v)) for m, v in pt.items()}
        # by what means, at the first sight of each tech type (and of the plan's tech)
        means = Counter()
        names = {7: "SCV", 64: "Probe", 41: "Drone", 42: "Overlord", 37: "Zergling", 84: "Observer"}
        for r in rs:
            for t, (what, dist) in r["means"].items():
                if int(t) in plan:
                    means["scan" if what == "scan" else names.get(what, "building" if 106 <= what <= 175 else "fighter")] += 1
        tot = sum(means.values())
        print("  the plan's tech first seen by: " + ", ".join(f"{k} {v / tot:.0%}" for k, v in means.most_common()) + f" (n {tot})")
        res["plan_tech_means"] = dict(means)
        # the scans (where the player has Comsats)
        sc = [s for r in rs for s in r["scans"]]
        if any(r["comsat_first"] is not None for r in rs):
            by_min = Counter(int(s["f"] // 1440) for s in sc)
            print(f"  scans: {len(sc) / len(rs):.2f} a game by 10:00; by minute " +
                  ", ".join(f"{m}:{by_min[m]}" for m in sorted(by_min)))
            places = Counter(s["place"] for s in sc)
            print("  scan targets: " + ", ".join(f"{k} {v / max(1, len(sc)):.0%}" for k, v in places.most_common()))
            first = [min(s["f"] for s in r["scans"]) / 1440 for r in rs if r["scans"]]
            if first:
                print(f"  first scan: median {np.median(first):.2f} min (in {len(first)} of {len(rs)} games)")
            # the hazard: scans per minute of a ready Comsat, by whether the plan's tech was seen, and the Comsat's age
            haz = {}
            for seen_flag in (0, 1):
                ready = sum(LOOK_EVERY / 1440 for r in rs for (_, k, s) in r["exposure"] if k > 0 and s == seen_flag)
                n = sum(1 for s in sc if s["plan_seen"] == bool(seen_flag))
                haz[seen_flag] = (n / ready if ready else None, n, ready)
            print(f"  scans a ready-Comsat minute: plan's tech not seen yet {haz[0][0] or 0:.3f} ({haz[0][1]} in "
                  f"{haz[0][2]:.0f} min), seen {haz[1][0] or 0:.3f} ({haz[1][1]} in {haz[1][2]:.0f} min)")
            ages = Counter(min(4, int(s["comsat_age"] // 1440)) for s in sc)
            print("  scans by the first Comsat's age (min): " + ", ".join(f"{k}{'+' if k == 4 else ''}: {v}" for k, v in sorted(ages.items())))
            res["scans"] = {"per_game": len(sc) / len(rs), "places": dict(places), "by_minute": dict(by_min),
                            "hazard": {str(k): v for k, v in haz.items()}, "ages": dict(ages),
                            "showed_plan": float(np.mean([any(TECH[er].get(t) in s["showed"] for t in plan) for s in sc])) if sc else None}
        # the first scout
        arr = [r["scout"][0] / 1440 for r in rs if r["scout"][0] is not None]
        stay = [(r["scout"][1] - r["scout"][0]) / 24 for r in rs if r["scout"][0] is not None and r["scout"][1] is not None]
        fu = Counter(names.get(r["first_unit"][0], str(r["first_unit"][0])) for r in rs if r["first_unit"])
        print(f"  first worker at the enemy main: in {len(arr)} of {len(rs)}, median {np.median(arr) if arr else float('nan'):.2f} "
              f"min, stayed a median {np.median(stay) if stay else float('nan'):.0f} s (quartiles "
              f"{np.percentile(stay, 25) if stay else float('nan'):.0f}-{np.percentile(stay, 75) if stay else float('nan'):.0f})"
              f"; first unit there: " + ", ".join(f"{k} {v}" for k, v in fu.most_common(4)))
        res["scout"] = {"arrived": len(arr), "arrive_min": float(np.median(arr)) if arr else None,
                        "stay_s": float(np.median(stay)) if stay else None, "first_unit": dict(fu)}
        # the enemy's main known, and the looking proxy against the sight
        mk = [r["main_at"] is not None and r["main_at"] <= 390 * 24 for r in rs]
        wrong = sum(1 for r in rs if r["main_right"] is False)
        print(f"  the enemy's main known by 6:30: {_share(mk)}, wrong {wrong}; enemy in sight at 3:00-6:00: "
              f"{np.mean([r['sight_s'] for r in rs]):.0f} s")
        for key, name in (("looks", "the refuted proxy (a unit within 8 tiles of the base's center)"),
                          ("sight", "the sight model (sight radii, scans)")):
            lk = Counter()
            for r in rs:
                lk.update(r.get(key, {}))
            seen = lk["11"] + lk["01"]
            print(f"  standing tech in sight caught by {name}: {lk['11'] / max(1, seen):.0%} (n {seen}); its looks with the "
                  f"tech out of sight {lk['10'] / max(1, lk['10'] + lk['11']):.0%} (n {lk['10'] + lk['11']})")
            res[key] = dict(lk)
        res.update({"main_known_630": float(np.mean(mk)), "main_wrong": wrong,
                    "sight_3_6_s": float(np.mean([r["sight_s"] for r in rs]))})
        out[f"{who} {mu}"] = res
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pros", action="store_true")
    ap.add_argument("--matchups", nargs="+", default=["TvZ", "PvT", "PvZ", "PvP", "ZvZ", "TvT"])
    ap.add_argument("--games", type=int, default=150, help="modern pro games a matchup (a seeded sample)")
    ap.add_argument("--rounds", nargs="+", help="Gary's league rounds")
    ap.add_argument("--race", default="T", help="with --rounds: the side whose view is read")
    ap.add_argument("--out")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--report", nargs="+", metavar="DIR")
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    if args.report:
        res = report(args.report)
        Path(args.report[0], "report.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        return
    jobs = pro_jobs(args.matchups, args.games) if args.pros else gary_jobs(args.rounds, args.race)
    run(jobs, Path(args.out), args.workers)
    report([args.out])


if __name__ == "__main__":
    main()

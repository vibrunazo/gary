"""Phase 2 item 1 (0 games): what leaves Gary's fighters to die alone, and its attacks' late arrivals, from replays
re-simulated (the full state) joined with the game's records (orders by tag and origin). The pros through the same
measures (no records).

Per Terran fighter death (a tag gone for good, not just loaded into a bunker):
  alone        no other Terran fighter within 6 tiles at its last look (gary/agent/sightings.py ALONE)
  alone_before alone 10 s earlier already
  cluster      at death and over the 30 s before it: in a ground cluster the commit layer asks (>= 4 supply, army.py
               _split: the densest cell and every unit within 2 cells, up to 3) or never in one
  outnumbered  the Zerg fighter supply within 8 tiles over the Terran's
  last order   its last order (records, by tag) in the 60 s before death, by origin: roles, the calm layer, the reinforce
               rule, the commit layer (its decision's units: was this one 16 tiles or more from their middle at the order,
               "swept", or ordered by another commit decision with a different destination within 30 s before, "re-taken")
Fighter samples (every 2 s, 5-20 minutes): the share in no asked cluster, and the share alone.
Late arrivals: eval/attacks.py's attacks() on the same replays.

A unit left alone in its last 10 s (its neighbours then died, or moved off, and by what) or alone already (by what
brought it there: its last order 10-90 s before, the roles' aside) is the second partition. Live games' records don't
join (the bridge's unit ids are not the replay's): their deaths are counted without the orders.

    python -m eval.alone --gary "runs/league/G4299a/*/*.rep" --pros 60 --out alone.json
"""
import argparse, glob, json, math, random, sys
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ingest"))
from eval import monitor, priority
from eval.attacks import FIGHTERS, Z_FIGHTERS, SIEGED, _supply, _zsupply, attacks

STEP, END = 12, 30 * 60 * 24
ALONE, NEAR, SWEPT = 6 * 32, 8 * 32, 16 * 32
GROUND_MIN = 8                         # supply x2 (army.py MIN_SUP)
from gary.races import AIR_FIGHTERS as _AF  # noqa: E402
AIR = set(_AF)                         # the fighting flyers: clustered apart (army.py), not here


def _x2(t):
    return int(round(2 * _supply(t)))


def clusters(units, w, h):
    """army.py _split over the ground fighters (each [tag, type, x, y]): tag -> cluster supply x2 (0: in none)."""
    cell = lambda u: (int(u[3] * 16 // h), int(u[2] * 16 // w))
    left = [u for u in units if u[1] not in AIR]
    out = {}
    n = 0
    while left and n < 3 and sum(_x2(u[1]) for u in left) >= GROUND_MIN:
        sup = defaultdict(int)
        cs = [cell(u) for u in left]
        for u, c in zip(left, cs):
            sup[c] += _x2(u[1])
        center = min(sup, key=lambda c: (-sup[c], c))
        near = [u for u, c in zip(left, cs) if max(abs(c[0] - center[0]), abs(c[1] - center[1])) <= 2]
        s = sum(_x2(u[1]) for u in near)
        if s >= GROUND_MIN:
            for u in near:
                out[u[0]] = s
            n += 1
        left = [u for u in left if u not in near]
    return out


def records(rep):
    rec = Path(str(rep).replace(".rep", ".records.jsonl"))
    if not rec.exists():
        return None
    orders = defaultdict(list)        # tag -> [(f, origin)]
    commits = defaultdict(list)       # tag -> [(f, by, to, tags)]
    deaths = []
    with open(rec, encoding="utf-8") as fh:
        for line in fh:
            if '"T"' not in line:
                continue
            r = json.loads(line)
            if r.get("side") != "T":
                continue
            k = r.get("kind")
            if k == "order" and r.get("units") and r.get("fate") == "sent":
                by = r.get("by", "?")
                if by.startswith("executor") or by in ("macro", "scout"):
                    continue
                for t in r["units"]:
                    orders[t].append((r["f"], by))
            elif k == "decision" and r.get("choice") == "army order":
                for t in r["in"]["tags"]:
                    commits[t].append((r["f"], r.get("by", "?"), tuple(r["in"]["to"]), tuple(r["in"]["tags"])))
            elif k == "death":
                deaths.append(r)
    return orders, commits, deaths


def one(rep):
    from gary.env import Game
    try:
        g = Game.scenario(str(rep))
    except Exception:
        return None
    recs = records(rep)
    ts = zs = None
    hist = defaultdict(list)           # tag -> [(f, x, y)]
    looks = deque(maxlen=31)           # (f, [[tag, type, x, y]]) own fighters, the last 15 s
    in_cluster = defaultdict(deque)    # tag -> recent (f, cluster supply x2)
    last = {}                          # tag -> (f, [tag,type,x,y], own near list, zsup near, own sup near, cluster)
    samples = Counter()
    w = h = 4096
    prev_tags = set()
    gone = {}
    while g.frame < END:
        try:
            g.step(STEP)
        except Exception:
            break
        o = g.observe()
        if ts is None:
            ts = next((p["slot"] for p in o["players"] if p["race"] == 1), None)
            zs = next((p["slot"] for p in o["players"] if p["race"] == 0), None)
            if ts is None or zs is None:
                return None
            w, h = o["map"]["w"], o["map"]["h"]
        f = o["frame"]
        mine = [[u["tag"], u["type"], u["x"], u["y"]] for u in o["units"]
                if u["owner"] == ts and u["type"] in FIGHTERS and u["completed"]]
        zf = [(u["x"], u["y"], _zsupply(u["type"])) for u in o["units"] if u["owner"] == zs and u["type"] in Z_FIGHTERS]
        cl = clusters(mine, w, h)
        tags = {u[0] for u in mine}
        for u in mine:
            hist[u[0]].append((f, u[2], u[3]))
            q = in_cluster[u[0]]
            q.append((f, cl.get(u[0], 0)))
            while q and f - q[0][0] > 30 * 24:
                q.popleft()
        if 5 * 1440 <= f < 20 * 1440 and f % 48 < STEP:
            for u in mine:
                others = sum(1 for v in mine if v is not u and math.dist(u[2:], v[2:]) < ALONE)
                samples["n"] += 1
                samples["alone"] += others == 0
                if u[1] not in AIR:
                    samples["ground"] += 1
                    samples["unasked"] += cl.get(u[0], 0) == 0
        for t in prev_tags - tags:
            st = last.get(t)
            if st is None:
                continue
            ab = {}
            for lag in (72, 240):              # alone 3 s and 10 s before its last look
                snap = next((m for fl, m in looks if st[0] - fl >= lag), None)
                snap = [m for fl, m in looks if st[0] - fl >= lag]
                if snap:
                    m = snap[-1]
                    me = next((v for v in m if v[0] == t), None)
                    ab[lag] = None if me is None else not any(v[0] != t and math.dist(me[2:], v[2:]) < ALONE for v in m)
                    if lag == 240 and me is not None:
                        ab["nb"] = [v[0] for v in m if v[0] != t and math.dist(me[2:], v[2:]) < ALONE]
            gone[t] = st + (ab,)
        for t in tags & set(gone):
            gone.pop(t)                    # (back: it was inside a bunker or out of sight of nothing)
        for u in mine:
            near_own = [v for v in mine if v is not u and math.dist(u[2:], v[2:]) < ALONE]
            zsup = sum(s for x, y, s in zf if math.dist((x, y), u[2:]) < NEAR)
            osup = sum(_supply(v[1]) for v in mine if math.dist(u[2:], v[2:]) < NEAR)
            last[u[0]] = (f, u, len(near_own), zsup, osup, cl.get(u[0], 0), list(in_cluster[u[0]]))
        looks.append((f, mine))
        prev_tags = tags
    end_f = g.frame
    deaths = []
    for t, st in gone.items():
        if st is None or end_f - st[0] < 2 * STEP:
            continue
        f, u, n_near, zsup, osup, csup, cq, ab = st
        orders = recs[0].get(t, []) if recs else []
        if recs and any(by == "rule:load" and f - fo < 15 * 24 for fo, by in orders if fo <= f):
            continue                      # (loaded into a bunker)
        alone_before, alone_3s = ab.get(240), ab.get(72)
        nb = ab.get("nb") or []
        nb_dead = sum(1 for x in nb if x in gone and gone[x] is not None and gone[x][0] <= f)
        d = {"f": f, "type": u[1], "alone": n_near == 0, "alone_before": alone_before, "alone_3s": alone_3s, "nb": len(nb), "nb_dead": nb_dead, "zsup": zsup, "osup": osup,
             "cluster_now": csup > 0, "cluster_30s": any(s > 0 for _, s in cq), "air": u[1] in AIR}
        if recs:
            o60 = [(fo, by) for fo, by in orders if f - 60 * 24 <= fo <= f]
            d["last"] = o60[-1][1] if o60 else None
            ob = [(fo, by) for fo, by in orders if f - 90 * 24 <= fo <= f - 240 and not by.startswith("roles")]
            d["brought"] = ob[-1][1] if ob else None
            moved = Counter()
            for x in nb:
                if not (x in gone and gone[x] is not None and gone[x][0] <= f):
                    ox = [by for fo, by in recs[0].get(x, []) if f - 240 <= fo <= f]
                    moved[ox[-1] if ox else "none"] += 1
            d["nb_moved_by"] = moved.most_common(1)[0][0] if moved else None
            cb = [c for c in recs[1].get(t, []) if f - 90 * 24 <= c[0] <= f - 240]
            d["brought_commit"] = cb[-1][1] if cb else None
            cm = [c for c in recs[1].get(t, []) if f - 60 * 24 <= c[0] <= f]
            d["commit_last"] = None
            if cm and (d["last"] in ("army", None) or cm[-1][0] >= o60[-1][0] - 2):
                fo, by, to, tg = cm[-1]
                # where was it and the order's others at the order
                def pos(tag, fr):
                    hp = [p for p in hist.get(tag, []) if p[0] <= fr]
                    return hp[-1][1:] if hp else None
                me = pos(t, fo)
                ps = [pos(x, fo) for x in tg if x != t]
                ps = [p for p in ps if p]
                swept = bool(me and ps and math.dist(me, (sorted(p[0] for p in ps)[len(ps) // 2],
                                                          sorted(p[1] for p in ps)[len(ps) // 2])) >= SWEPT)
                prevc = [c for c in recs[1].get(t, []) if fo - 30 * 24 <= c[0] < fo and c[3] != tg
                         and math.dist(c[2], to) > 2]
                d["commit_last"] = by
                d["swept"], d["retaken"] = swept, bool(prevc)
                d["commit_f"] = fo
        deaths.append(d)
    att = attacks(str(rep))
    return {"rep": str(rep), "deaths": deaths, "samples": dict(samples), "attacks": att, "records": recs is not None}


def cause2(d):
    """A death alone: left alone in its last 10 s (its neighbours then died, or left), or alone already, by what had
    brought it there (its last order 10-90 s before, roles' orders aside)."""
    if d.get("alone_before") is False:
        if d["nb_dead"] >= max(1, d["nb"] / 2):
            return "left alone: its neighbours died"
        return f"left alone: its neighbours moved off (by {d.get('nb_moved_by')})"
    if d.get("alone_before") is None:
        return "unknown"
    b = d.get("brought")
    if b == "army:calm":
        return "alone already: the calm layer moved it"
    if b == "rule:reinforce":
        return "alone already: the reinforce rule sent it"
    if b == "army" or d.get("brought_commit"):
        return "alone already: a commit order brought it" + (" (in no asked cluster now)" if not d["cluster_now"] else "")
    if b is None:
        return "alone already: no order 10-90 s before, " + ("never in an asked cluster" if not d["cluster_30s"] else "in an asked cluster")
    return f"alone already: {b}"


def cause(d):
    """The partition of a death alone by what last moved it (Gary's, with records)."""
    last = d.get("last")
    if last in ("rule:reinforce",):
        return "d reinforce rule"
    if last == "army:calm":
        return "c calm layer"
    if last in ("roles", "roles:queued"):
        return "e/roles: roles' order"
    if d.get("commit_last") and (last in ("army", None)):
        if d.get("swept") or d.get("retaken"):
            return "f commit: swept or re-taken"
        return "b commit: its own cluster's order"
    if last is None:
        return "a never in an asked cluster (30 s)" if not d["cluster_30s"] else "b asked, no order in 60 s (kept)"
    return f"other: {last}"


def report(name, rows):
    rows = [r for r in rows if r]
    deaths = [d for r in rows for d in r["deaths"] if not d["air"] or True]
    n = len(deaths); al = [d for d in deaths if d["alone"]]
    print(f"\n== {name}: {len(rows)} games, {n} fighter deaths, alone {len(al)} ({len(al) / max(1, n):.0%})")
    if not al:
        return
    ab = [d for d in al if d["alone_before"] is not None]
    a3 = [d for d in al if d.get("alone_3s") is not None]
    print(f"  alone 3 s before already {sum(d['alone_3s'] for d in a3) / max(1, len(a3)):.0%} (of {len(a3)}), 10 s before {sum(d['alone_before'] for d in ab) / max(1, len(ab)):.0%} (of {len(ab)}); outnumbered "
          f"(zerg supply within 8 tiles > own) {sum(d['zsup'] > d['osup'] for d in al) / len(al):.0%}; in no asked "
          f"cluster at death {sum(not d['cluster_now'] for d in al) / len(al):.0%}, nor in the 30 s before "
          f"{sum(not d['cluster_30s'] for d in al) / len(al):.0%}; flyers {sum(d['air'] for d in al) / len(al):.0%}")
    s = Counter()
    for r in rows:
        s.update(r["samples"])
    if s["n"]:
        print(f"  fighter samples 5-20 min: alone {s['alone'] / s['n']:.3f}; ground ones in no asked cluster {s['unasked'] / max(1, s['ground']):.3f}")
    if all(r["records"] for r in rows):
        c = Counter(cause(d) for d in al)
        for k, v in sorted(c.items()):
            sub = [d for d in al if cause(d) == k]
            print(f"   {v:5d} {v / len(al):5.0%}  {k}  (alone 10 s before {sum(bool(d['alone_before']) for d in sub) / v:.0%}, outnumbered {sum(d['zsup'] > d['osup'] for d in sub) / v:.0%})")
    if all(r["records"] for r in rows):
        print("  by what left it alone:")
    c2 = Counter(cause2(d) if all(r["records"] for r in rows) else ("left alone" if d.get("alone_before") is False else "alone already" if d.get("alone_before") else "unknown") for d in al)
    for k, v in sorted(c2.items(), key=lambda x: -x[1]):
        print(f"   {v:5d} {v / len(al):5.0%}  {k}")
    att = [a for r in rows for a in (r["attacks"] or [])]
    if att:
        late = sum(a["late_n"] for a in att) / max(1, sum(a["late_n"] / a["late"] if a["late"] else 0 for a in att))
        src = Counter()
        for a in att:
            src.update(a.get("late_src", {}))
        tot = sum(src.values())
        sh = sorted(a["share"] for a in att)
        print(f"  attacks {len(att)}: the army's share there (median) {sh[len(sh) // 2]:.2f}; late arrivals per one there {sum(a['late'] for a in att) / len(att):.2f} (mean of attacks); "
              f"made after it began {sum(a['late_new'] for a in att) / max(1, sum(a['late_n'] for a in att)):.0%}; sent by "
              + (", ".join(f"{k} {v / tot:.0%}" for k, v in src.most_common()) if tot else "no records"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gary", nargs="*", default=[])
    ap.add_argument("--pros", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out")
    priority.add_argument(ap)
    a = ap.parse_args()
    priority.apply(a.priority)
    paths = sorted(p for g in a.gary for p in glob.glob(g))
    sets = [("gary", paths)] if paths else []
    if a.pros:
        from inventory import data_root
        from eval.humanlike import clean_replays
        clean = clean_replays()
        recs = [json.loads(l) for l in open(data_root() / "interim" / "build_orders.jsonl", encoding="utf-8")]
        recs = [r for r in recs if r.get("matchup") == "TvZ" and r.get("race") == "T" and r.get("source") == "cwal"
                and r["rel_path"] in clean and r.get("duration_s", 0) >= 600]
        random.Random(0).shuffle(recs)
        sets.append(("pros", [str(data_root() / "raw" / r["rel_path"]) for r in recs[:a.pros]]))
    out = {}
    with ProcessPoolExecutor(a.workers) as pool:
        for name, paths in sets:
            out[name] = list(monitor.track(pool.map(one, paths), len(paths), f"alone: {name}"))
    if a.out:
        Path(a.out).write_text(json.dumps(out, default=str), encoding="utf-8")
    for name, rows in out.items():
        report(name, rows)


if __name__ == "__main__":
    main()

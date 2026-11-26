"""The pipe check of the army's tactical intents (docs/TACTICAL_INTENT.md §5; option `intent`): does a pushed intent
move what Gary's army does? One headless game of gt1dev+intent against gz1dev to 12:00; at every minute from 6:00 both
bots deep-copied once per intent (eval/pairs.py's copy), that intent forced on the main for ARM frames, and the arm's
own records read: the army's orders (the motor's "army order" lines: their units and cells), the commit model's
decisions, the lease conflicts. Needs the game data and the models (skips without them).

Printed, with the pass criteria written before the check was run (docs/TACTICAL_INTENT.md §5; 1, 2 and 4 restated
2026-11-26 by the user's calls, §8):
  1. the commit layer's and the intent layer's orders to a forced intent's units after its switch go to its target
     (within 2 cells), 90% or more (HOLD: none); the calm layer's hops are local by design and not counted. A forced
     intent is always a fresh one (its own target), even where the main already had that kind;
  2. the five arms' orders differ pairwise in 80% of the army-active moments or more (a moment where some arm's army
     was asked; where a fight holds the hands no arm's is, criterion 3's other side);
  3. no lease conflict on a unit outside contact that the intent layer ordered;
  4. the defence against a small threat is about the pros': nobody goes in a sixth to a half of such moments (theirs
     36% against 2 supply or less), and someone going sends their median given a defence within half of it (9 supply,
     the intent model's report); a small army
     early defends whole (the size half the army or more: the main itself, no detachment);
  5. the commit model's odds move with the intent input (engage most under ATTACK, keep under HOLD), and the role
     model's close-in falls under RETREAT;
and the specialists: sieged tanks kept sieged by the intent's orders (an order to a sieged tank in an arm counted), the
control groups' keys one unit type each and flyers never on a ground key.

Run: python tests/test_intent_pipe.py   (a few minutes)
"""
from __future__ import annotations

import contextlib
import io
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

START, UNTIL, EVERY = 6 * 1440, 12 * 1440, 1440
ARM = 15 * 24
INTENTS = ("DEFEND_BASE", "ATTACK", "RETREAT", "GATHER", "HOLD")


def _tile_cell(g, name):
    """A record's tile "(x,y)" as the army tracker's cell."""
    x, y = (int(v) for v in str(name).strip("()").split(","))
    return g.army.tracker.cell(x * 32 + 16, y * 32 + 16)


def test_intent_pipe(report: dict | None = None):
    try:
        from eval.match import Match
        import os
        with contextlib.redirect_stdout(io.StringIO()):
            m = Match(1, os.environ.get("PIPE_MANIFEST", "gt1dev+intent"), REPO / "tests" / "fixtures" / "replays" / "stardata_tvz_standard_ozp3w.rep",
                      opponent="gz1dev")
    except Exception as e:                      # no game data, env DLL or models here
        print(f"skip: {e}")
        return
    from eval.pairs import _copy, _play
    from gary.agent.army import cell_dist
    from gary.races import AIR_FIGHTERS
    from gary.policy.army import supply_x2
    g = m.gary
    assert getattr(g, "tactical", None) is not None, "gt1dev+intent built without its intent layer (no intent model?)"
    out = {"to_target": [], "hold_orders": [], "differ": [], "conflicts": 0, "conflicts_contact": 0, "sieged_ordered": 0, "conflict_takers": {}, "intent_over": {}, "by_origin": {},
           "sieged_unsieged": 0, "moments": 0, "commit": {k: [] for k in INTENTS}, "roles": {k: [] for k in INTENTS},
           "keys": [], "questions": Counter(), "taken": {k: Counter() for k in INTENTS}, "miss": Counter(), "hit": Counter(),
           "det_n": [], "det_share": [], "active": [], "before": [],
           "dest": __import__("collections").defaultdict(list)}
    next_at = START
    while m.game.frame < UNTIL and not m.done:
        with contextlib.redirect_stdout(io.StringIO()):
            m.step()
        if g.tactical.main is not None and m.game.frame % 24 == 0:        # (the unforced main line: its detachments)
            o = g.hi.observe()
            sup = {u["tag"]: supply_x2(u["type"]) for u in o["units"] if u["owner"] == g.slot and u["type"] in g.army_types}
            total = sum(sup.values()) or 1
            out["det_n"].append(len(g.tactical.details))
            out["det_share"].append(sum(sup.get(t, 0) for d in g.tactical.details for t in d["units"]) / total)
        if m.game.frame < next_at or g.tactical.main is None:
            continue
        from gary.env import GameError
        try:
            m.game.save()
        except GameError:
            continue                                # (commands in flight: a moment later)
        next_at += EVERY
        out["moments"] += 1
        obs = g.hi.observe()
        _offline(g, obs, out)
        ctx = {"gary": m.gary, "zerg": m.zerg, "his": m.his, "slot_of": m.slot}
        arms, asked = {}, {}
        for kind in INTENTS:
            m.game.restore()
            arm = _copy(ctx)
            ag = arm["gary"]
            events = []
            ag.event = lambda kind_, **kw: events.append((kind_, kw))
            ag.tactical.forced, ag.tactical.next = kind, 0
            started = []                       # (each army order's units at its start, and whether a detachment's)

            def _start(intent, _orig=ag.motor.start, _ag=ag, _started=started):
                tac = _ag.tactical
                mid = tac.main["id"] if tac.main else None
                _started.append((_ag.hi.frame, set(intent.units),
                                 bool(intent.units) and all(tac.of.get(t, mid) != mid for t in intent.units)))
                return _orig(intent)
            ag.motor.start = _start
            sieged = {u["tag"] for u in obs["units"] if u["owner"] == g.slot and u["type"] == 30}
            recs = _play(m.game, arm, ARM)
            after = ag.hi.observe()
            still = {u["tag"] for u in after["units"] if u["owner"] == g.slot and u["type"] == 30}
            target = ag.tactical.main.get("target") if ag.tactical.main else None
            switched = [r for r in recs if r.get("kind") == "decision" and r.get("layer") == "intent"
                        and str(r.get("by", "")).startswith("forced")]
            f_sw = switched[0]["f"] if switched else None
            for r in recs:                             # (each commit question in the arm: before the switch, or after it
                if r.get("kind") != "decision" or r.get("layer") != "commit" or r.get("side") != "T":
                    continue                           # with the forced intent, another, or a detachment's)
                ins = r.get("in") or {}
                when = "no switch (already that intent)" if f_sw is None else "before the switch" if r["f"] < f_sw else                     "after, a detachment's" if ins.get("of") == "detachment" else                     "after, the forced intent" if ins.get("intent") == INTENTS.index(kind) else "after, another intent"
                out["questions"][when] += 1
                if when in ("after, the forced intent", "no switch (already that intent)") and ins.get("of") == "main":
                    out["taken"][kind][str(r.get("choice", "")).split(" ")[0]] += 1
                    ch = str(r.get("choice", ""))
                    if " to (" in ch and kind != "HOLD" and target is not None and r.get("then") == "sent":
                        at, to = (_tile_cell(ag, s_) for s_ in (ins.get("at"), ch.split(" to ")[1]))
                        key = ("the intent's target" if str(r.get("by")).endswith("the intent's target") else
                               "near the intent's target" if "near the intent's target" in str(r.get("by")) else
                               "own cell, the cluster at the target" if cell_dist(at, target) < 2 else "own cell, the cluster away")
                        out["dest"][(kind, key)].append(cell_dist(to, target))
            orders = [r for r in recs if r.get("kind") == "decision" and r.get("choice") == "army order" and r.get("side") == "T"
                      and str(r.get("by", "")).startswith(("commit", "intent"))
                      and not str(r.get("by", "")).startswith("intent join")]   # (where the army goes: calm's hops are local,
            # and the join walks a lone unit to its group, wherever the group is)
            def _detached(r):                  # (a detachment's order: its units were not the main intent's when it was
                tags = set(r["in"]["tags"])    # given, whatever they are at the arm's end)
                for f_, ts, det in reversed(started):
                    if f_ <= r["f"] and tags <= ts:
                        return det
                return False
            orders = [r for r in orders if not _detached(r)]
            mine = {u["tag"] for u in after["units"] if u["owner"] == g.slot}
            leased = {t for t, i in ag.tactical.of.items() if ag.tactical.main and i == ag.tactical.main["id"]}
            cells = []
            for r in orders:
                tags = set(r["in"]["tags"])
                if not tags & leased:
                    continue
                to = r["in"]["to"]                     # (tiles, the order's cell centre)
                c = ag.army.tracker.cell(to[0] * 32 + 16, to[1] * 32 + 16)
                cells.append(c)
                if kind != "HOLD" and target is not None and f_sw is not None and r["f"] < f_sw:
                    out["before"].append(cell_dist(c, target) <= 2)        # (before the switch: not the forced intent's)
                elif kind != "HOLD" and target is not None:
                    out["to_target"].append(cell_dist(c, target) <= 2)
                    key = (kind, "switched" if f_sw is not None else "no switch", "before" if f_sw is not None and r["f"] < f_sw else "after")
                    (out["hit"] if cell_dist(c, target) <= 2 else out["miss"])[key] += 1
                    out["by_origin"].setdefault(str(r.get("by")), []).append(cell_dist(c, target) <= 2)
                out["sieged_ordered"] += len(tags & sieged)
            if kind == "HOLD":
                out["hold_orders"].append(sum(1 for r in recs if r.get("kind") == "decision" and r.get("layer") == "commit"
                                              and r.get("choice", "").split(" ")[0] in ("engage", "move")))
            out["sieged_unsieged"] += len((sieged & mine) - still)
            for k_, kw in events:
                if k_ == "lease_conflict":
                    out["conflict_takers"][kw.get("taker")] = out["conflict_takers"].get(kw.get("taker"), 0) + 1
                    if kw.get("taker") == "intent":
                        held = " ".join(sorted(kw.get("held_by", {})))
                        out["intent_over"][held] = out["intent_over"].get(held, 0) + 1
                        if any(h.split(" ")[0] in ("roles", "fight") or h.startswith(("rule:", "hands:"))
                               for h in kw.get("held_by", {})):
                            out["conflicts"] += 1          # (over a fight's or a rule's units: the criterion)
            arms[kind] = tuple(sorted(set(cells)))
            asked[kind] = any(r.get("kind") == "decision" and r.get("layer") == "commit" and r.get("side") == "T" for r in recs)
        m.game.restore()
        ks = list(arms)
        pairs = [(a, b) for i, a in enumerate(ks) for b in ks[i + 1:]]
        out["differ"].append(np.mean([arms[a] != arms[b] for a, b in pairs]))
        out["active"].append(any(asked.values()))
        plan = getattr(g.motor, "plan", {}) or {}
        types = {u["tag"]: u["type"] for u in obs["units"] if u["owner"] == g.slot}
        for key, tags in plan.items():
            ts = {types[t] for t in tags if t in types}
            out["keys"].append((len(ts) <= 1, not (ts & set(AIR_FIGHTERS) and ts - set(AIR_FIGHTERS))))
    _sizer(g, out)
    _unforced(out)
    _print(out)
    if report is not None:
        report.update(out)


def _offline(g, obs, out) -> None:
    """At the moment: the commit model's odds for the main cluster under each intent input, and the role model's
    close-in odds for its units under each (the models alone, nothing played)."""
    from gary.agent.tactical import Tactical  # noqa: F401
    army = [u for u in obs["units"] if u["owner"] == g.slot and u["completed"] and u["type"] in g.army_types]
    clusters = g.army._clusters(army)
    if not clusters:
        return
    group = max(clusters, key=len)
    cx, cy = sum(u["x"] for u in group) / len(group), sum(u["y"] for u in group) / len(group)
    held, age = g.army._commitment(g.army.tracker.cell(cx, cy), False)
    from gary.agent.army import COMMIT_AGE_S
    for k, name in enumerate(INTENTS):
        hk = (0, COMMIT_AGE_S) if name == "HOLD" else (held, age)     # (as play reads HOLD: no commitment in force)
        grid, glob = g.army.tracker.copy().inputs(obs, group, hk, -1, intent=k)
        _, kind = g.army.model.predict(grid, glob)
        out["commit"][name].append(kind[0])
    fight = getattr(g, "fight", None)
    roles = getattr(fight, "roles", None)
    model = getattr(roles, "model", None)
    if model is None or not model.config.get("intent"):
        return
    snap = fight._snapshot(obs) if hasattr(fight, "_snapshot") else None
    if snap is None:
        return
    rows, tags, _, _ = snap
    extra = roles._motion(obs, snap)
    names = list(model.config["roles"])
    if "close_in" not in names:
        return
    from gary.policy.roles import order_budget
    for k, name in enumerate(INTENTS):
        model.intent = k
        p = model.predict(rows, extra, obs["frame"] * 42 / 1000, order_budget(g.hi))
        own = [i for i, t in enumerate(tags[:len(p)]) if t in {u["tag"] for u in army}]
        if own:
            out["roles"][name].append(float(np.mean(p[own, names.index("close_in")])))
    model.intent = -1


def _unforced(out) -> None:
    """The main line's own intents (its records): shares of time, hold lengths, switches a minute; its detachments."""
    from gary.decision_log import LOG
    recs = [r for r in LOG.records if r.get("kind") == "decision" and r.get("layer") == "intent" and r.get("side") == "T"]
    main = [r for r in recs if r["choice"] in INTENTS]
    dets = [r for r in recs if str(r["choice"]).startswith("DEFEND_BASE (")]
    nobody = [r for r in recs if str(r["choice"]).endswith("nobody goes")]
    whole = [r for r in main if "the main defends" in str(r.get("by", ""))]
    spans = Counter()
    holds = {k: [] for k in INTENTS}
    for a, b in zip(main, main[1:] + [{"f": UNTIL}]):
        spans[a["choice"]] += b["f"] - a["f"]
        holds[a["choice"]].append((b["f"] - a["f"]) / 24)
    tot = sum(spans.values()) or 1
    com = [r for r in LOG.records if r.get("kind") == "decision" and r.get("layer") == "commit" and r.get("side") == "T"]
    by_intent = {}
    for k, name in enumerate(INTENTS):
        c = Counter(str(r.get("choice", "")).split(" ")[0] for r in com if (r.get("in") or {}).get("intent") == k)
        if c:
            by_intent[name] = [c["keep"], c["engage"], c["move"]]
    shuffles = sum(1 for r in com if (r.get("in") or {}).get("intent") == INTENTS.index("GATHER")
                   and "near the intent's target" in str(r.get("by")) and r.get("then") == "sent")
    out["unforced"] = {"shares": {k: round(spans[k] / tot, 3) for k in INTENTS},
                       "hold_median_s": {k: round(float(np.median(v)), 1) for k, v in holds.items() if v},
                       "commit_keep_engage_move": by_intent, "gather_moves_at_target": shuffles,
                       "switches_a_minute": round(len(main) / max(1e-9, (UNTIL - (main[0]["f"] if main else 0)) / 1440), 2),
                       "detachments": [(r["f"] // 1440, (r.get("in") or {}).get("units"), (r.get("in") or {}).get("supply"),
                                        (r.get("in") or {}).get("threat"), (r.get("in") or {}).get("army")) for r in dets],
                       "nobody_goes": [(r["f"] // 1440, (r.get("in") or {}).get("threat"), (r.get("in") or {}).get("p_send"))
                                       for r in nobody],
                       "main_defends": [(r["f"] // 1440, (r.get("in") or {}).get("threat"), (r.get("in") or {}).get("size"),
                                         (r.get("in") or {}).get("main_supply")) for r in whole]}


def _sizer(g, out) -> None:
    """The defence's size in made-up states: the pros' medians (train/tactical_intent.py report) are the yardstick."""
    m = g.tactical.model
    base = {"minute": 8.0, "own_army": 30.0, "threat_cells": 1, "loss_home": 0.0, "d_threat_main": 3, "n_clusters": 2}
    out["sizer"] = {th: round(m.defend_size({**base, "threat_sup": th}), 1) for th in (1.0, 4.0, 10.0, 20.0)}
    out["send"] = {th: round(m.p_send({**base, "threat_sup": th}), 2) for th in (1.0, 4.0, 10.0, 20.0)}
    out["send_losses"] = round(m.p_send({**base, "threat_sup": 0.0, "loss_home": 2.0}), 2)
    small = {**base, "minute": 4.0, "own_army": 5.0, "threat_sup": 2.0}
    out["sizer_small"] = round(m.defend_size(small), 1)
    out["send_small"] = round(m.p_send(small), 2)


def _print(out) -> None:
    tt = out["to_target"]
    print(f"moments {out['moments']}, arms {out['moments'] * len(INTENTS)}")
    c1 = np.mean(tt) if tt else float("nan")
    bf = out["before"]
    print(f"1. orders of a forced intent's units to its target after its switch (within 2 cells): {c1:.0%} of {len(tt)}"
          f" ({'PASS' if tt and c1 >= 0.9 else 'FAIL'}); before the switch {np.mean(bf) if bf else 0:.0%} of {len(bf)}"
          f" (not counted); HOLD arms' commit engage/move decisions {out['hold_orders']}")
    print("   by who gave them: " + ", ".join(f"{k} {np.mean(v):.0%} of {len(v)}" for k, v in out["by_origin"].items()))
    d, act = out["differ"], out["active"]
    da = [x for x, a in zip(d, act) if a]
    c2 = np.mean([x >= 0.8 for x in da]) if da else float("nan")
    print(f"2. arms' orders differing pairwise: {np.round(d, 2).tolist()}, the army asked in some arm {act}; army-active "
          f"moments at 80%+: {sum(x >= 0.8 for x in da)} of {len(da)} ({'PASS' if da and c2 >= 0.8 else 'FAIL'}); "
          f"all moments {sum(x >= 0.8 for x in d)} of {len(d)}")
    print(f"3. the intent layer's orders over a fight's or a rule's units in the arms: {out['conflicts']} "
          f"({'PASS' if out['conflicts'] == 0 else 'FAIL'}); its orders over others' leases, by holder {out['intent_over']}; "
          f"all lease conflicts by taker {out['conflict_takers']}")
    s, sd = out.get("sizer", {}), out.get("send", {})
    ok4 = bool(s) and 4.5 <= s[1.0] <= 13.5 and 0.5 <= sd[1.0] <= 0.85 and out["sizer_small"] >= 2.5
    print(f"4. against threats of 1/4/10/20 supply, an army of 30 at 8:00: P(anyone defends) {sd}, the size given a "
          f"defence {s}; losses alone P {out.get('send_losses')}; 2 supply against an army of 5 at 4:00: P "
          f"{out.get('send_small')}, size {out.get('sizer_small')} (half the army or more: the main defends) (the pros: "
          f"nobody 36% against 2 or less, 9 supply given a defence, held out; {'PASS' if ok4 else 'FAIL'})")
    cm = {k: np.mean(v, 0).round(3).tolist() for k, v in out["commit"].items() if v}
    ok5 = bool(cm) and cm["ATTACK"][1] == max(x[1] for x in cm.values()) and cm["HOLD"][0] == max(x[0] for x in cm.values())
    print(f"5. the commit model's keep/engage/move by intent input: {cm} ({'PASS' if ok5 else 'FAIL'})")
    rm = {k: round(float(np.mean(v)), 3) for k, v in out["roles"].items() if v}
    print(f"   the role model's close-in by intent input: {rm or 'no fight at the moments'}"
          + (f" ({'PASS' if rm['RETREAT'] <= min(rm.values()) + 1e-9 else 'FAIL'})" if rm else ""))
    print("unforced main line: " + str(out.get("unforced")))
    dn, ds = out["det_n"], out["det_share"]
    print(f"   detachments at once: max {max(dn) if dn else 0}; their share of the army's supply: peak {max(ds) if ds else 0:.2f}, "
          f"mean while any {np.mean([x for x, n in zip(ds, dn) if n]) if any(dn) else 0:.2f}")
    print("commit questions in the arms: " + str(dict(out["questions"])))
    print("   the main's kind taken after the switch, by forced intent (keep / engage / move): " +
          "; ".join(f"{k} {[c[x] for x in ('keep', 'engage', 'move')]}" for k, c in out["taken"].items()))
    print("   orders to the target, hits / misses by (forced, switch, before/after): " +
          "; ".join(f"{k}: {out['hit'][k]}/{out['miss'][k]}" for k in sorted(set(out['hit']) | set(out['miss']))))
    print("   the main's sent commit orders after the switch, their cell's distance to the target (cells): " +
          "; ".join(f"{k} {why}: {len(v)}, within 2 {np.mean([x <= 2 for x in v]):.0%}, median {np.median(v):.0f}"
                    for (k, why), v in sorted(out["dest"].items())))
    print(f"specialists: orders to sieged tanks in the arms {out['sieged_ordered']}, tanks unsieged during the arms "
          f"{out['sieged_unsieged']}; control-group keys of one type {sum(a for a, _ in out['keys'])}/{len(out['keys'])}, "
          f"flyers never with ground {sum(b for _, b in out['keys'])}/{len(out['keys'])}")


if __name__ == "__main__":
    test_intent_pipe()

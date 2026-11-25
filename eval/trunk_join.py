"""The strategic trunk's games read from their records (docs/REFOCUS.md §3.5 "Execution Join Integrity", Phase 1 step
7b): each directive's start, whether the enemy's tech was real by then (the replay's commands), and each of its items
followed down the trace by ids (gary/decision_log.py link): the macro's decision -> handed, queued, waiting or dropped
-> started (the trunk's fate record).

Denominators, written before step 7b's games (2026-11-24), the first as built:
  per item       each directive item the trunk asked (a decision), once per game: started (a fate record under one of its
                 decisions), or never (the game ran on, or ended first: apart). An item Gary lacked at the start and made
                 before the trunk asked it has no decision: the directive's end (every item had) covers those
The last hop is by count, not by id: a fate fires when Gary's count of the item rises, whoever ordered it (an item
already underway from the macro's own decision gets its fate within seconds and no order of its own).
  per decision   each of the macro's decisions of a directive's item, the ask-again repeats included: what its own
                 children say (handed, queued, waiting, dropped, nothing) and whether a fate followed it
A decision with no child record at all is a pipe drop: the macro took the goal and nothing was written of its end.

Gate 3's execution join (docs/REFOCUS.md Phase 1 gate 3, ">= 95%"; written 2026-11-25, step 9, after step 7b's and 8's
games had been read by the per-item and per-decision counts above, so not blind to them): over every trunk directive
item asked and every card milestone decided (Arm B: options armb, strict), the share carried out, an item started (the
trunk's fate record) or a card milestone's item ordered in the replay within 120 s of its handed order (the replay's
commands), of those whose game ran on 120 s; and apart, the decisions with no logged outcome (a silent drop: no child
record), which count against it.

    python -m eval.trunk_join --rounds TK293a9 TK293a1 TK293a0 TK293a4
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", nargs="+", required=True)
    ap.add_argument("--side", default="T")
    args = ap.parse_args()
    from eval.trunk_dryrun import items_of
    from build_orders import secs
    card_out, card_dec = Counter(), Counter()
    item_out, dec_out, starts = Counter(), Counter(), []
    by_item = defaultdict(Counter)
    for rnd in args.rounds:
        for rec in sorted(glob.glob(str(REPO / "runs" / "league" / rnd / "*" / "*.records.jsonl"))):
            rows = [json.loads(l) for l in open(rec, encoding="utf-8")][1:]
            rows = [r for r in rows if r.get("side") == args.side]
            end = max((r["f"] for r in rows), default=0)
            by_id = {r["id"]: r for r in rows if "id" in r}
            kids = defaultdict(list)
            for r in rows:
                if "parent" in r:
                    kids[r["parent"]].append(r)
            game = Path(rec).parent.name[:12]
            cards = [d for d in rows if d.get("kind") == "decision" and str(d.get("by", "")).startswith("card:")]
            if cards:
                from gary.agent.strategy import replay_items
                _, _, mine = replay_items(rec.replace(".records.jsonl", ".rep"), None, "T", by_s=None)
                for d in cards:
                    ch = [k for k in kids[d.get("id")] if k.get("kind") == "order"]
                    card_dec[ch[-1]["fate"] if ch else "nothing: the game ended first" if end - d["f"] < 30 * 24
                             else "nothing (a pipe drop)"] += 1
                    handed = next((k for k in ch if k["fate"] == "handed"), None)
                    item = d["choice"].rsplit(" (", 1)[0]
                    item = "Command Center" if item == "expand" else item
                    t0 = (handed or d)["f"] * 42 / 1000
                    if end - d["f"] < 120 * 24:
                        card_out["the game ended first"] += 1
                    elif any(i["item"] == item and t0 - 1 <= i["t"] <= t0 + 120 for i in mine):
                        card_out["ordered"] += 1
                    else:
                        card_out["not ordered in 120 s"] += 1
            if not any(r.get("kind") == "strategy_state" and r.get("transition") == "start" for r in rows):
                continue
            Z = items_of(rec.replace(".records.jsonl", ".rep"))["Z"]
            for st in (r for r in rows if r.get("kind") == "strategy_state" and r.get("transition") == "start"):
                t = secs(st["f"])                       # (the replay items' clock: 42 ms a frame, not frame / 24)
                truth = min(Z.get("Lurker Aspect", 1e9), max(Z.get("Hydralisk Den", 1e9), Z.get("Lair", 1e9))) <= t
                ended = next((e for e in kids[st["id"]] if e.get("kind") == "strategy_state"), None)
                sel = by_id.get(st.get("parent"), {})
                starts.append((rnd, game, st["directive"], t, truth, Z.get("Lurker Aspect"), sel.get("p_pro"),
                               sel.get("n"), sel.get("cell"), ended["after_s"] if ended else None))
                decs = [d for d in kids[st["id"]] if d.get("kind") == "decision"]
                first = {}
                for d in decs:
                    item = d["choice"].rsplit(" (", 1)[0]
                    first.setdefault(item, d)
                    ch = [k for k in kids[d["id"]] if k.get("kind") == "order"]
                    fate = [k for k in kids[d["id"]] if k.get("kind") == "fate"]
                    dec_out[(ch[-1]["fate"] if ch else "nothing: the game ended first" if end - d["f"] < 30 * 24
                             else "nothing (a pipe drop)") + (" + started" if fate else "")] += 1
                for item, d in first.items():
                    ok = any(k.get("kind") == "fate" for dd in decs if dd["choice"].rsplit(" (", 1)[0] == item
                             for k in kids[dd["id"]])
                    out = "started" if ok else "never (the game ran on)" if end - d["f"] > 120 * 24 else "never (the game ended first)"
                    item_out[out] += 1
                    by_item[item][out] += 1
    print(f"directive starts: {len(starts)}")
    for rnd, game, d, t, truth, la, p, n, cell, after in starts:
        print(f"  {rnd} {game}: {d} at {int(t) // 60}:{int(t) % 60:02d} (P_pro {p}, n {n}, {cell}); the lurker tech by "
              f"then {'yes' if truth else 'NO (a false start)'}, Lurker Aspect {la}; ended {after} s after"
              if after is not None else
              f"  {rnd} {game}: {d} at {int(t) // 60}:{int(t) % 60:02d} (P_pro {p}, n {n}, {cell}); the lurker tech by "
              f"then {'yes' if truth else 'NO (a false start)'}, Lurker Aspect {la}; not ended")
    n_items = sum(item_out.values())
    print(f"per item ({n_items}): " + ", ".join(f"{k} {v}" for k, v in item_out.most_common()))
    for item, c in by_item.items():
        print(f"  {item}: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    print(f"per decision ({sum(dec_out.values())}): " + ", ".join(f"{k} {v}" for k, v in dec_out.most_common()))
    if card_dec:
        print(f"card decisions ({sum(card_dec.values())}): " + ", ".join(f"{k} {v}" for k, v in card_dec.most_common()))
        print(f"  their items: " + ", ".join(f"{k} {v}" for k, v in card_out.most_common()))
    ran = item_out["started"] + item_out["never (the game ran on)"] + card_out["ordered"] + card_out["not ordered in 120 s"]
    done = item_out["started"] + card_out["ordered"]
    silent = dec_out["nothing (a pipe drop)"] + card_dec["nothing (a pipe drop)"]
    n_dec = sum(dec_out.values()) + sum(card_dec.values())
    if ran:
        print(f"gate 3, the execution join: {done}/{ran} carried out ({done / ran:.1%}; >= 95%), "
              f"{silent} of {n_dec} decisions with no logged outcome")


if __name__ == "__main__":
    main()

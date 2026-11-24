"""The recipe card's tags over played games (docs/REFOCUS.md §3.3, Phase 1 step 6's first pass, 0 games): each game's
told style's card (gary/policy/card.py, its cards file) against the game's records (the macro's decisions, what they
passed over and the money) and its replay (when each item was ordered, as the card's pro times are read). Per round:
the one-off decisions on and off the card (first decisions; asked again apart), and how off-card ones were taken (the
dice at what odds, or a rule); each milestone on time or delayed(odds | money | busy | hands).

    python -m eval.card_tags --rounds RD285a SC291a9 SC291a1 SC291a0 SC291a4 --cards runs/cards/TvZ_T_20261124.json
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from eval import monitor, priority  # noqa: E402

UNTIL = 10 * 60 * 24              # frames: the card's milestones fall before 10:00


def game_tags(job):
    """One game: (round, style, decision tags, milestone tags) or None."""
    rep, rnd, cards, race_letter = job
    sys.argv = ["x", "--race", race_letter]
    from eval.style_adherence import gary_items
    from gary.policy.card import CardTagger, is_one_off, item_of, race_costs
    from gary.race import Race
    race = Race.of(race_letter)
    recs = Path(rep[:-4] + ".records.jsonl")
    if not recs.exists():
        return None
    rows = [json.loads(line) for line in open(recs, encoding="utf-8")][1:]
    rows = [r for r in rows if r.get("side") == race_letter]
    style = next((r["choice"] for r in rows if r.get("layer") == "style"), None)
    card = cards.get(str(style))
    if card is None:
        return None
    try:
        items = gary_items(rep, Path(tempfile.gettempdir()) / "gary_card_cmds")
    except Exception:  # noqa: BLE001
        return None
    if items is None:
        return None
    tagger = CardTagger(card, f"style {style}", race_costs(race))
    end = max((r["f"] for r in rows), default=0)
    events = [(it["frame"], 0, "start", it) for it in items if it["frame"] < UNTIL]
    events += [(r["f"], 1, "decision", r) for r in rows if r.get("kind") == "decision" and r.get("layer") == "macro"
               and r["f"] < UNTIL]
    events += [(int(24 * (m["t"] + m["tol"])), 2, "due", None) for m in card if 24 * (m["t"] + m["tol"]) <= end]
    money = (0, 0)
    dec, mil = [], []
    for f, _, kind, x in sorted(events, key=lambda e: (e[0], e[1])):
        if kind == "start":
            tagger.start(item_of(x["name"]), f)   # (a replay counts each build command: one re-issued counts again)
        elif kind == "decision":
            if x.get("in"):
                money = (x["in"].get("m", money[0]), x["in"].get("gas", money[1]))
            t = tagger.decision(f, x.get("choice"), is_one_off(race, x.get("choice") or ""), x.get("over"))
            if t is not None:
                dec.append({**t, "by": "dice" if x.get("by") == "dice" else "rule", "p": x.get("p")})
        else:
            mil += tagger.check(f, *money)
    return rnd, style, dec, mil


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", nargs="+", required=True)
    ap.add_argument("--cards", required=True)
    ap.add_argument("--race", default="T")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--json", help="write the tags here")
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    from gary.policy.card import load_cards
    cards = load_cards(args.cards)["cards"]
    jobs = [(p, r, cards, args.race) for r in args.rounds
            for p in sorted(glob.glob(str(REPO / "runs" / "league" / r / "*" / "*.rep")))]
    with ProcessPoolExecutor(args.workers) as pool:
        res = [x for x in monitor.track(pool.map(game_tags, jobs), len(jobs), "games") if x is not None]
    if args.json:
        Path(args.json).write_text(json.dumps(res), encoding="utf-8")
    groups = {}
    for rnd, style, dec, mil in res:
        key = rnd[:2] if not rnd.startswith("RD") else rnd
        groups.setdefault(key, []).append((style, dec, mil))
    for key, games in groups.items():
        first = [d for _, dec, _ in games for d in dec if not d["again"]]
        again = sum(1 for _, dec, _ in games for d in dec if d["again"])
        on = [d for d in first if d["tag"] == "on_card"]
        off = [d for d in first if d["tag"] == "off_card"]
        offp = np.array([d["p"] for d in off if d["by"] == "dice" and d["p"] is not None])
        print(f"{key}: {len(games)} games (styles {dict(Counter(s for s, _, _ in games))}); one-off decisions "
              f"{len(first)} (asked again {again}): on the card {len(on)} ({len(on) / max(1, len(first)):.0%}), off "
              f"{len(off)}")
        if len(off):
            print(f"  off the card: by the dice {sum(d['by'] == 'dice' for d in off)} (their odds median "
                  f"{np.median(offp) if len(offp) else float('nan'):.2f}, under 0.10 {np.mean(offp < 0.1) if len(offp) else 0:.0%}), "
                  f"by a rule {sum(d['by'] == 'rule' for d in off)}; most: "
                  + ", ".join(f"{k} {v}" for k, v in Counter(d["item"] for d in off).most_common(8)))
        tags = Counter(m["tag"] for _, _, mil in games for m in mil)
        n = sum(tags.values())
        print(f"  milestones due ({n}): " + ", ".join(f"{k} {v / max(1, n):.0%}" for k, v in tags.most_common()))
        by_feat = {}
        for _, _, mil in games:
            for m in mil:
                by_feat.setdefault(m["milestone"], Counter())[m["tag"]] += 1
        print("  by milestone: " + "; ".join(
            f"{f} " + "/".join(f"{k.replace('delayed', 'd')} {v}" for k, v in c.most_common()) for f, c in by_feat.items()))


if __name__ == "__main__":
    main()

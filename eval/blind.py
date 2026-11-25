"""The blind evaluation pack (docs/REFOCUS.md §3.5 metric 3 and Phase 1 gate 3, step 9): Phase 1's templates
(eval/coach.py) against the pre-Phase-1 way of answering (eval/why.py's listing of the same window, the record kinds
gt1dev wrote before Phase 1), over held-out moments of Phase 1's games, graded by a person on (a) predicting what Gary
did next and (b) usefulness. Written 2026-11-25, before any moment was drawn:

Games      held out: the step 7b and step 8 suite rounds (TK293a0/1/4/9, TB295a0/1/4/9: 32 games), less the two whose
           records were read while the templates were written (TK293a4 Attitude SE 2.1's record kinds, TB295a4 Fighting
           Spirit 1.4's plan beliefs); the templates were written on TC294a4 and the drills.
Moments    30, 6 per question, from at least 10 games, drawn by a seeded generator (--seed) by these rules, each answer
           made only from the records up to the moment (Q3: its minute), the prediction's truth from after it:
  Q1  3:00                                 next: Gary's next building, tech or expansion decision after 3:00 (4 options)
  Q2  3 moments 30-90 s before a directive start (the anti-lurker plan), 3 more at a belief sample of 3:00-9:00 with
      no start within 3 minutes after   next: does Gary start teching to tanks and vessels as a plan within 2 min (y/n)
  Q3  a half minute in 4:00-12:00          next: the next building, tech or expansion decision after the minute (4)
  Q4  a commit decision's moment in 5:00-15:00 with one in the 30 s before
                                           next: the army's next commitment in 60 s: attack, move, or none (holds)
  Q5  the start of a supply block in 3:00-15:00 (a macro decision blocked after one that wasn't)
                                           next: unblocked within 10 s, 10-30 s, or later
Part 1     prediction: each moment with ONE answer, 3 of each question's 6 from the templates and 3 from the baseline
           (drawn), the grader picks the option; accuracy per arm
Part 2     usefulness: each moment with both answers as X and Y (order drawn); each rated 1-5 ("as a player learning
           from this game: does it tell me what Gary believed or decided and why, so that I could act on it?" 1 no help or
           confusing, 3 some, 5 clear and actionable) and the more useful one picked. Part 2 after part 1.
Pass       (gate 3, written now) the templates' prediction accuracy over the baseline's, and their usefulness a mean of
           3.5 or more and preferred in 60% of the moments or more. 15 moments an arm: a difference under about 30
           points of accuracy is within noise, said with the result.
Not blind  the two arms look different (prose and a record listing): the grader can tell them apart; what is blind is
           the outcome (the key) and which moment had which arm in part 1.

    python -m eval.blind --out runs/blind/BE297            (the pack: pack.md, sheet.csv, key.json)
    python -m eval.blind --out runs/blind/BE297 --grade    (sheet.csv filled in: the scores)
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

ROUNDS = ("TK293a0", "TK293a1", "TK293a4", "TK293a9", "TB295a0", "TB295a1", "TB295a4", "TB295a9")
READ = {("TK293a4", "Attitude SE 2.1"), ("TB295a4", "Fighting Spirit 1.4")}
ONE_OFFS = ("Barracks", "Refinery", "Factory", "Academy", "Engineering Bay", "Bunker", "expand", "Starport",
            "Missile Turret", "Comsat Station", "Machine Shop", "Stim Packs", "U-238 Shells",
            "Science Facility", "Control Tower", "Siege Mode", "Infantry Weapons", "Infantry Armor", "Armory")
PER_Q, GAMES_MIN = 6, 10


def games() -> list[tuple[str, str, Path]]:
    out = []
    for rnd in ROUNDS:
        for rec in sorted(glob.glob(str(REPO / "runs" / "league" / rnd / "*" / "*.records.jsonl"))):
            m = Path(rec).parent.name
            if (rnd, m) not in READ:
                out.append((rnd, m, Path(rec)))
    return out


def next_one_off(g, after_f: float) -> str | None:
    from eval.coach import _name, is_building_or_tech
    d = next((d for d in g.where("decision", after_f, 1e12, layer="macro")
              if is_building_or_tech(d.get("choice"))), None)
    return None if d is None else _name(d)


def options(truth: str, rng: random.Random, k: int = 4) -> list[str]:
    pool = [x for x in ONE_OFFS if x != truth]
    opts = rng.sample(pool, k - 1) + [truth]
    rng.shuffle(opts)
    return opts


def draw(seed: int) -> list[dict]:
    """The moments, by the rules above."""
    from eval.coach import Game, blocked
    rng = random.Random(seed)
    pool = games()
    rng.shuffle(pool)
    loaded = {}

    def game(i):
        if i not in loaded:
            loaded[i] = Game(pool[i][2])
        return loaded[i]
    moments, used = [], set()

    def add(i, q, f, truth, opts, note=""):
        rnd, m, rec = pool[i]
        moments.append({"q": q, "round": rnd, "map": m, "records": str(rec.relative_to(REPO)), "minute": round(f / 1440, 4),
                        "truth": truth, "options": opts, "note": note})
        used.add(i)
    # Q2 first (its positives are few): the starts in the held-out games
    starts = [(i, r["f"]) for i in range(len(pool)) for r in game(i).where("strategy_state", transition="start")]
    rng.shuffle(starts)
    for i, f in starts[:3]:
        add(i, 2, f - rng.randint(30, 90) * 24, "yes", ["yes", "no"], "a start follows")
    neg = 0
    for i in rng.sample(range(len(pool)), len(pool)):
        if neg == 3:
            break
        g = game(i)
        pb = [r["f"] for r in g.where(("plan_belief",), 180 * 24, 540 * 24)]
        st = [r["f"] for r in g.where("strategy_state", transition="start")]
        pb = [f for f in pb if not any(0 <= s - f <= 180 * 24 for s in st) and not any(s <= f for s in st)]
        if pb and i not in used:
            add(i, 2, rng.choice(pb) + 24, "no", ["yes", "no"])
            neg += 1
    order = list(range(len(pool)))
    for q in (1, 3, 4, 5):
        n = 0
        rng.shuffle(order)
        # (a game not used yet first, so the moments spread over the games)
        for i in sorted(order, key=lambda j: j in used):
            if n == PER_Q:
                break
            g = game(i)
            if q == 1:
                f = 3 * 1440
                t = next_one_off(g, f)
                if t and g.end_f > 6 * 1440:
                    add(i, 1, f, t, options(t, rng))
                    n += 1
            elif q == 3:
                f = rng.choice(range(8, 24)) * 720
                t = next_one_off(g, f + 1440)
                if t and g.end_f > f + 3 * 1440:
                    add(i, 3, f, t, options(t, rng))
                    n += 1
            elif q == 4:
                # (3 moments with a commitment following, 3 without: most commit decisions keep)
                com = [d for d in g.where("decision", 300 * 24, 900 * 24, layer="commit")]
                want = "go" if sum(1 for m in moments if m["q"] == 4 and m["truth"] != "none (holds)") < 3 else "hold"
                if sum(1 for m in moments if m["q"] == 4 and m["truth"] == "none (holds)") >= 3:
                    want = "go"
                cands = []
                for d in com:
                    f = d["f"] + 1
                    nxt = next((x for x in g.where("decision", f, f + 60 * 24, layer="commit")
                                if str(x["choice"]).startswith(("engage", "move"))), None)   # ("engage to (x,y)")
                    if g.end_f > f + 60 * 24 and (nxt is not None) == (want == "go"):
                        cands.append((f, ("attack" if nxt["choice"].startswith("engage") else "move") if nxt
                                      else "none (holds)"))
                if cands:
                    f, t = rng.choice(cands)
                    add(i, 4, f, t, ["attack", "move", "none (holds)"])
                    n += 1
            else:
                decs = [d for d in g.where("decision", 180 * 24, 900 * 24, layer="macro") if d.get("in")]
                onsets = [b for a, b in zip(decs, decs[1:]) if blocked(b) and not blocked(a)]
                if not onsets:
                    continue
                b = rng.choice(onsets)
                after = next((d for d in g.where("decision", b["f"] + 1, 1e12, layer="macro") if d.get("in")
                              and not blocked(d)), None)
                if after is None:
                    continue
                s = (after["f"] - b["f"]) / 24
                add(i, 5, b["f"], "within 10 s" if s <= 10 else "10-30 s" if s <= 30 else "later than 30 s",
                    ["within 10 s", "10-30 s", "later than 30 s"], f"unblocked after {s:.0f} s")
                n += 1
    assert len({(m["round"], m["map"]) for m in moments}) >= GAMES_MIN, "too few games"
    return moments


def build(out: Path, seed: int) -> None:
    from eval.coach import QUESTIONS, Game, baseline
    rng = random.Random(seed + 1)
    moments = draw(seed)
    rng.shuffle(moments)
    for q in range(1, 6):                         # part 1's arms: 3 and 3 per question
        ms = [m for m in moments if m["q"] == q]
        arms = ["template"] * (len(ms) // 2) + ["baseline"] * (len(ms) - len(ms) // 2)
        rng.shuffle(arms)
        for m, a in zip(ms, arms):
            m["part1"] = a
    for i, m in enumerate(moments, start=1):
        m["id"] = i
        g = Game(REPO / m["records"])
        t, b = QUESTIONS[m["q"]](g, m["minute"]), baseline(g, m["q"], m["minute"])
        m["template"], m["baseline"] = t.text(), b.text()
        m["x"] = rng.choice(["template", "baseline"])
    out.mkdir(parents=True, exist_ok=True)
    head = ("# Gary's blind evaluation pack (Phase 1 step 9)\n\n"
            "Each moment is a question about one of Gary's games (Gary is Terran against a Zerg) and an answer drawn "
            "from that game's records. Do **part 1 first**, without reading part 2.\n\n"
            "**Part 1, prediction:** read the answer, then pick what you think Gary did next. Write the option in "
            "`sheet.csv`, column `prediction`.\n\n"
            "**Part 2, usefulness:** each moment again, with two answers, X and Y. Rate each 1-5 (*as a player "
            "learning from this game: does it tell me what Gary believed or decided and why, so that I could act on "
            "it?* 1 = no help or confusing, 3 = some, 5 = clear and actionable) in `use_x` and `use_y`, and write X or "
            "Y in `prefer`.\n\nThe `watch:` line opens the moment in the viewer (viewer/watch.py; the times in the "
            "answers are Gary's clock, frame / 24, the viewer's the replay's, about 4% later).\n\n")
    next_q = {1: "Which is Gary's next building, tech or expansion decision after 3:00?",
              2: "Does Gary start teching to tanks and Science Vessels as a plan (a Machine Shop, Siege Mode, tanks, a "
                 "Starport, vessels) within the next 2 minutes?",
              3: "Which is Gary's next building, tech or expansion decision after this minute?",
              4: "Gary's army's next commitment in the next 60 s:",
              5: "Gary is supply blocked now. When is it unblocked?"}
    parts = [head, "## Part 1: prediction\n"]
    for m in moments:
        ans = m[m["part1"]]
        parts.append(f"### Moment {m['id']} ({m['round']}, {m['map']}, {int(m['minute'])}:{int(m['minute'] % 1 * 60):02d})\n\n"
                     f"```\n{ans}\n```\n\n**{next_q[m['q']]}** " + " / ".join(m["options"]) + "\n")
    parts.append("\n## Part 2: usefulness\n")
    for m in moments:
        x, y = (m["template"], m["baseline"]) if m["x"] == "template" else (m["baseline"], m["template"])
        parts.append(f"### Moment {m['id']}\n\n**X**\n\n```\n{x}\n```\n\n**Y**\n\n```\n{y}\n```\n")
    (out / "pack.md").write_text("\n".join(parts), encoding="utf-8")
    with open(out / "sheet.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["moment", "question", "options", "prediction", "use_x", "use_y", "prefer"])
        for m in moments:
            w.writerow([m["id"], m["q"], " / ".join(m["options"]), "", "", "", ""])
    key = [{k: v for k, v in m.items() if k not in ("template", "baseline")} for m in moments]
    (out / "key.json").write_text(json.dumps({"seed": seed, "written": "2026-11-25", "moments": key}, indent=1),
                                  encoding="utf-8")
    by_q = {q: sum(1 for m in moments if m["q"] == q) for q in range(1, 6)}
    print(f"{len(moments)} moments ({by_q}) from {len({(m['round'], m['map']) for m in moments})} games: "
          f"{out / 'pack.md'}, {out / 'sheet.csv'} (the key apart: key.json)")


def grade(out: Path) -> None:
    key = {m["id"]: m for m in json.loads((out / "key.json").read_text(encoding="utf-8"))["moments"]}
    rows = list(csv.DictReader(open(out / "sheet.csv", encoding="utf-8")))
    acc = {"template": [0, 0], "baseline": [0, 0]}
    use = {"template": [], "baseline": []}
    prefer = 0
    for r in rows:
        m = key[int(r["moment"])]
        if r["prediction"].strip():
            a = acc[m["part1"]]
            a[0] += r["prediction"].strip().lower() == str(m["truth"]).lower()
            a[1] += 1
        if r["use_x"].strip() and r["use_y"].strip():
            tx = m["x"] == "template"
            use["template"].append(float(r["use_x"] if tx else r["use_y"]))
            use["baseline"].append(float(r["use_y"] if tx else r["use_x"]))
        if r["prefer"].strip():
            prefer += (r["prefer"].strip().upper() == "X") == (m["x"] == "template")
    n_pref = sum(1 for r in rows if r["prefer"].strip())
    for arm in acc:
        k, n = acc[arm]
        u = use[arm]
        print(f"{arm:9s} prediction {k}/{n}" + (f" ({k / n:.0%})" if n else "")
              + (f", usefulness {sum(u) / len(u):.2f} over {len(u)}" if u else ""))
    if n_pref:
        print(f"templates preferred in {prefer}/{n_pref} ({prefer / n_pref:.0%})")
    t, b = acc["template"], acc["baseline"]
    if t[1] and b[1] and use["template"] and n_pref:
        ok = t[0] / t[1] > b[0] / b[1] and sum(use["template"]) / len(use["template"]) >= 3.5 and prefer / n_pref >= 0.6
        print("gate 3's blind evaluation: " + ("passes" if ok else "does not pass"))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(REPO / "runs" / "blind" / "BE297"))
    ap.add_argument("--seed", type=int, default=297)
    ap.add_argument("--grade", action="store_true")
    args = ap.parse_args()
    (grade if args.grade else lambda o: build(o, args.seed))(Path(args.out))


if __name__ == "__main__":
    main()

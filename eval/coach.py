"""Five deterministic answers about a game, from its records (docs/REFOCUS.md §3.5, Phase 1 step 9): no LLM, no
re-simulation, nothing that is not in the records. Each statement cites the record it comes from: [L<line> <time>] (the
records file's line, Gary's clock: frame / 24 as in the game's log) and #<id> on the trace's linked records
(gary/decision_log.py link). Each answer ends with the viewer command for its moment (viewer/watch.py; the viewer's
clock is the replay's, 42 ms a frame).

  1  Why this opening / strategy card?                  the style decision, the card held (or log-only), its milestones
                                                        against Gary's own decisions of them, up to the minute asked
  2  What did you think I was doing at minute M, and    the plan belief's last sample by M (its odds and what it
     from what evidence?                                read: seen, confirmed absent, unscouted) and the trunk's
                                                        branch score on it (P_pro, its cell, the contrast)
  3  Why did you build / tech / expand (or delay) at M?  the macro's decisions in [M, M + 1 min): who chose (the model's
                                                        dice, the card, the trunk, a rule), what was set aside and why,
                                                        each order's fate, a trunk item's chain up to its belief
  4  Why did your army attack / hold / pull back at M?   the commit model's decisions in [M - 30 s, M] (its odds, the
                                                        inputs they rest on), the army's sends, the role layer's orders
                                                        in contact; "no army decision" when there was none
  5  Why did you miss a defense / supply / timing at M?  a supply block at M (the depot's decisions and fates before it,
                                                        who had the hands, the macro's waits), a card milestone late,
                                                        own losses with no army near

--baseline prints instead what eval/why.py shows for the same question and window (the pre-Phase-1 way of answering:
its records' kinds only, decision, order, hands, note, seen, belief, death), for the blind evaluation (eval/blind.py).

    python -m eval.coach runs/league/TK293a4/"Attitude SE 2.1"/<game>.records.jsonl --ask 2 --minute 7.5
    python -m eval.coach <game> --ask all --minute 6
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PRE_PHASE1 = ("decision", "order", "hands", "note", "seen", "belief", "death")    # the record kinds before Phase 1
UNITS_T = {"SCV", "Marine", "Firebat", "Medic", "Ghost", "Vulture", "Siege Tank", "Goliath", "Wraith", "Dropship",
           "Science Vessel", "Battlecruiser", "Valkyrie", "Nuclear Missile"}
TECH_SEEN = ("Lair", "Spire", "Hydralisk Den", "Queen's Nest", "Hive", "Evolution Chamber", "Lurker", "Mutalisk",
             "Hydralisk", "Defiler Mound", "Greater Spire")
MAX_LINES = 14             # an answer's decisions listed at most (the rest counted)


def clock(f: float) -> str:
    s = f / 24
    return f"{int(s // 60)}:{int(s % 60):02d}"


def rep_s(f: float) -> float:
    """The replay's clock (the viewer's): 42 ms a frame."""
    return f * 42 / 1000


@dataclass
class Answer:
    q: int
    title: str
    at_f: int
    lines: list[str] = field(default_factory=list)
    cites: list[dict] = field(default_factory=list)
    viewer: str = ""

    def say(self, text: str, *recs: dict) -> None:
        refs = " ".join(self.ref(r) for r in recs if r)
        self.lines.append(text + (f" {refs}" if refs else ""))

    def ref(self, r: dict) -> str:
        self.cites.append({"line": r["_line"], "f": r["f"], **({"id": r["id"]} if "id" in r else {})})
        return f"[{'#' + str(r['id']) + ' ' if 'id' in r else ''}L{r['_line']} {clock(r['f'])}]"

    def text(self) -> str:
        return "\n".join([f"Q{self.q} {self.title}"] + [f"  {s}" for s in self.lines]
                         + ([f"  watch: {self.viewer}"] if self.viewer else []))


class Game:
    """One game's records (with their file lines), its trace, replay and POV paths."""

    def __init__(self, path: str | Path, side: str = "T"):
        p = Path(path)
        if p.suffix == ".rep":
            p = p.with_name(p.stem + ".records.jsonl")
        self.path, self.side = p, side
        self.rows: list[dict] = []
        for i, s in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            r = json.loads(s)
            if "f" in r:
                r["_line"] = i
                self.rows.append(r)
        self.mine = [r for r in self.rows if r.get("side") == side]
        self.by_id = {r["id"]: r for r in self.mine if "id" in r}
        base = str(p)[:-len(".records.jsonl")]
        self.rep, self.pov, self.trace_path = Path(base + ".rep"), Path(base + ".pov.jsonl"), Path(base + ".trace.jsonl")
        self._trace = None
        self.end_f = max((r["f"] for r in self.rows), default=0)

    def trace(self) -> list[dict]:
        if self._trace is None:
            self._trace = []
            if self.trace_path.exists():
                for s in self.trace_path.read_text(encoding="utf-8").splitlines()[1:]:
                    r = json.loads(s)
                    if "frame" in r:
                        self._trace.append(r)
        return self._trace

    def where(self, kind: str | tuple, f0: float = 0, f1: float = 1e12, **eq) -> list[dict]:
        kinds = (kind,) if isinstance(kind, str) else kind
        return [r for r in self.mine if r["kind"] in kinds and f0 <= r["f"] < f1
                and all(r.get(k) == v for k, v in eq.items())]

    def viewer(self, f: float, q: int) -> str:
        rel = lambda x: str(x.relative_to(REPO)) if x.is_relative_to(REPO) else str(x)
        s = max(0, int(rep_s(f)) - 10)
        pov = f' --pov "{rel(self.pov)}"' if self.pov.exists() else ""
        return f'python viewer/watch.py "{rel(self.rep)}"{pov} --record q{q}.mp4 --from {s} --to {s + 40}'


def _name(r: dict) -> str:
    return (r.get("choice") or "").rsplit(" (", 1)[0]


def is_building_or_tech(choice: str | None) -> bool:
    """A macro decision of a building (but a depot), research, an upgrade or an expansion (the predictions' "next")."""
    if not choice:
        return False
    c = choice.rsplit(" (", 1)[0]
    return c not in UNITS_T and c != "Supply Depot"


def _who(by: str) -> str:
    """Who chose, in words, from a decision's by."""
    if by.startswith("trunk:"):
        return "the strategic trunk's directive " + by[len("trunk: "):]
    if by.startswith("card:"):
        return "the card's milestone (" + by[len("card: "):] + ")"
    if by in ("dice", "favorite", "draw"):
        return f"the macro model's {'dice' if by == 'dice' else by}"
    if by.startswith("rule:"):
        return by[len("rule: "):] + " (a rule)"
    return by


def _fates(g: Game, d: dict, f1: float) -> list[dict]:
    """A macro decision's orders: by the trace's ids where it has them, else the same item's order records within 40 s
    (the macro's own: handed, queued, waiting, dropped) and the executor's (dropped: couldn't be built)."""
    if "id" in d:
        kids = [r for r in g.mine if r.get("parent") == d["id"]]
        if kids:
            return kids
    name = _name(d)
    out = []
    for r in g.where("order", d["f"], min(f1, d["f"] + 40 * 24)):
        what = r["what"].rsplit(" (", 1)[0]
        if r.get("fate") != "sent" and what == name and r.get("by") in ("macro", "executor", "card"):
            out.append(r)
        elif r.get("fate") == "sent" and what in (f"place {name}", f"research {name}", f"upgrade {name}"):
            # (the order to the game: the building placed, the research or upgrade started)
            out.append({**r, "fate": "placed" if what.startswith("place") else "ordered", "why": f"at {clock(r['f'])}"})
            break
    return out


def _chain(g: Game, r: dict) -> list[dict]:
    """A linked record's ancestors (parent first)."""
    out, seen = [], set()
    while "parent" in r and r["parent"] in g.by_id and r["parent"] not in seen:
        seen.add(r["parent"])
        r = g.by_id[r["parent"]]
        out.append(r)
    return out


def _table(name: str | None) -> dict | None:
    if not name:
        return None
    p = REPO / "runs" / "selector" / name
    return json.loads(p.read_text(encoding="utf-8"))["meta"] if p.exists() else None


def _cell_words(cell: str | None, meta: dict | None) -> str:
    """A table cell's key in words: the belief's bucket, looked, each chain's items had, the minute bucket."""
    if not cell:
        return ""
    kv = dict(x.split("=") for x in cell.split("|"))
    out = []
    if meta:
        b = meta["buckets"]
        i = int(kv.get("belief", 0))
        lo, hi = ([0.0] + b)[i], (b + [1.0])[i]
        out.append(f"P({meta['tech']}) {lo:.0%}-{hi:.0%}")
        if "looked" in kv:
            out.append("looked" if kv["looked"] == "1" else "not looked")
        for letter, chain in zip("abcdefgh", meta.get("chains", [])):
            if letter in kv:
                k = int(kv[letter])
                out.append(f"had {', '.join(chain[:k])}" if k else f"no {chain[0]}")
        if "minute" in kv:
            m = [x / 60 for x in meta["minutes"]]
            i = int(kv["minute"])
            out.append("before %g:00" % m[0] if i == 0 else f"after {m[-1]:g}:00" if i == len(m) else
                       f"{m[i - 1]:g}:00-{m[i]:g}:00")
    return "; ".join(out) or cell


# --- Q1 ------------------------------------------------------------------------------------------------------------

def q1(g: Game, minute: float | None = None) -> Answer:
    f1 = int((minute if minute is not None else 8.0) * 1440)
    a = Answer(1, "Why this opening / strategy card?", f1)
    st = next(iter(g.where("decision", layer="style")), None)
    if st:
        how = {"roll": "rolled by the pros' shares of the styles in this matchup (styleroll)",
               "told": "told by name (--style)", "chosen": "chosen by the selector"}.get(st["by"], st["by"])
        from gary.styles import catalog
        cat = catalog("TvZ", g.side) or {"names": {}, "shares": {}}
        name, share = cat["names"].get(st["choice"]), cat["shares"].get(st["choice"])
        a.say(f"Gary played style {st['choice']}{f' ({name})' if name else ''}, {how}"
              + (f": {share:.0%} of the modern pros' games" if share else "") + ".", st)
    held = next(iter(g.where("strategy_state", transition="card")), None)
    tags = g.where("card")
    card, card_id = None, None
    if held:
        card = [{"item": i, "n": n, "t": t, "tol": tol} for i, n, t, tol in held["milestones"]]
        card_id = held["card_id"]
        a.say(f"It held the card {card_id} ({held['adherence']}: "
              + ("every off-card one-off masked and each milestone the goal in its window"
                 if held["adherence"] == "strict" else "due milestones emitted, off-card low-odds one-offs masked")
              + f"), from {held['source'] or 'the style'}.", held)
    elif tags:
        card_id = tags[0]["card"]
        try:
            from gary.agent.strategy import from_style
            card = list(from_style("TvZ", "T", int(card_id.rsplit(" ", 1)[1])).card)
        except Exception:
            card = None
        a.say(f"Its card {card_id} was log-only: it moved nothing, the macro model's own decisions were tagged "
              "against it (on the card, off it, or delayed by money, a busy building or the hands).", tags[0])
    else:
        a.say("No card in this game's records: the macro model decided the opening alone.")
    if card:
        decs = [d for d in g.where("decision", 0, f1, layer="macro") if d.get("choice")]
        counts: dict[str, int] = {}
        first: dict[tuple, dict] = {}
        for d in decs:
            n = _name(d)
            n = "Command Center" if n == "expand" else n
            counts[n] = counts.get(n, 0) + 1
            first.setdefault((n, counts[n]), d)
        shown = 0
        for m in card:
            if m["t"] * 1000 / 42 > f1 * 1.0 and shown >= 4:
                break
            d = first.get((m["item"], m["n"]))
            due = f"{int(m['t']) // 60}:{int(m['t']) % 60:02d}"
            if d is None:
                a.say(f"{m['item']} #{m['n']} (the pros' median {due}, 9 in 10 within {m['tol']:.0f} s): "
                      f"not decided by {clock(f1)}.")
            else:
                tag = next((t for t in tags if t["f"] == d["f"] and t.get("item") == m["item"]), None)
                a.say(f"{m['item']} #{m['n']} (the pros' median {due}): decided at {clock(d['f'])} by {_who(d['by'])}"
                      + (f" at {d['p']:.0%}" if "p" in d else "")
                      + (f"; the card's tag: {tag['tag']}" if tag else "") + ".", d, tag)
            shown += 1
        late = [t for t in tags if "milestone" in t and t["f"] < f1 and t["tag"] != "on time"]
        for t in late[:4]:
            a.say(f"milestone {t['milestone']} {t['tag']} (due {t['due_s']} s).", t)
    a.viewer = g.viewer(min(f1, 180 * 24), 1)
    return a


# --- Q2 ------------------------------------------------------------------------------------------------------------

def q2(g: Game, minute: float) -> Answer:
    f = int(minute * 1440)
    a = Answer(2, f"What did you think the Zerg was doing at {clock(f)}, and from what evidence?", f)
    pb = [r for r in g.where(("plan_belief", "plan"), 0, f + 1)]
    if not pb:
        a.say(f"No plan belief by {clock(f)} (its first sample is at 2:30).")
    else:
        b = max(pb, key=lambda r: (r["f"], r["kind"] == "plan_belief"))
        odds = ", ".join(f"{k} {p:.0%}" for k, p in b["odds"][:3])
        tech = ", ".join(f"{k} {p:.0%}" for k, p in sorted(b["tech"].items(), key=lambda kv: -kv[1]) if p >= 0.02)
        a.say(f"At {clock(b['f'])} the plan belief ({b['model']}) gave {odds}; by tech, {tech}"
              + ("" if b["kind"] == "plan_belief" else " (log-only)") + ".", b)
        ev = b.get("evidence") or {}
        seen = [r for r in g.where("seen", 0, f + 1) if r.get("type") in TECH_SEEN
                or any(t in TECH_SEEN for t in (r.get("types") or {}))]
        firsts: dict[str, dict] = {}
        for r in seen:
            for t in ([r["type"]] if r.get("type") else [t for t in r["types"] if t in TECH_SEEN]):
                firsts.setdefault(t, r)
        if firsts:
            a.say("Seen: " + "; ".join(f"{t} at {clock(r['f'])} ({r['near']})" for t, r in firsts.items()) + ".",
                  *firsts.values())
        if ev.get("plan_tech_first_f") is not None:
            a.say(f"The plan's tech was first seen at {clock(ev['plan_tech_first_f'])}.")
        if ev:
            if not ev.get("main_known"):
                a.say("Unscouted: Gary did not yet know where the Zerg's main was.")
            elif ev.get("main_look_f") is None:
                a.say("Unscouted: the main was known but never looked at.")
            elif b.get("looked"):
                if not firsts:
                    a.say(f"Confirmed absent: Gary looked at the main at {clock(ev['main_look_f'])} "
                          f"(covering {ev['main_cover']:.0%} of it) and saw none of the plan's tech.")
                else:
                    a.say(f"Looked: the main last at {clock(ev['main_look_f'])} (cover {ev['main_cover']:.0%}).")
            else:
                a.say(f"Not looked enough to count (the belief's split): the main last seen at "
                      f"{clock(ev['main_look_f'])}, cover {ev['main_cover']:.0%}; what was not seen there is unknown, "
                      "not absent.")
        sel = [r for r in g.where("branch_select", 0, f + 1) if r.get("parent") == b.get("id") and "p_pro" in r]
        for s in sel:
            meta = _table(s.get("table"))
            took = s["chosen"] != "none"
            a.say(f"On it the trunk scored {s['branch']}: the pros in the cell \"{_cell_words(s['cell'], meta)}\" "
                  f"({s['n']} games) start it within 2 minutes in {s['p_pro']:.0%} ({s['interval'][0]:.0%}-"
                  f"{s['interval'][1]:.0%}); with a low belief (\"{_cell_words(s.get('contrast_cell'), meta)}\") "
                  f"{s['contrast_p']:.0%}, at most {s['contrast_hi']:.0%}. "
                  + ("Over the threshold of {:.0%} and clear of the contrast: started.".format(s["threshold"]) if took
                     else f"Not started: {'under the threshold' if s['p_pro'] < s['threshold'] else 'not clear of the contrast'}"
                          f" ({s['threshold']:.0%})."), s)
            if took:
                st = next((r for r in g.mine if r.get("parent") == s["id"] and r["kind"] == "strategy_state"), None)
                if st:
                    a.say(f"The directive {st['directive']}: " + ", ".join(f"{n} x{k}" if k > 1 else n
                                                                         for n, k in st["items"]) + ".", st)
        active = [r for r in g.where("strategy_state", 0, f + 1, transition="start")]
        if active and not any(s["chosen"] != "none" for s in sel):
            a.say(f"Already under way: {active[-1]['directive']} since {clock(active[-1]['f'])}.", active[-1])
    a.viewer = g.viewer(f, 2)
    return a


# --- Q3 ------------------------------------------------------------------------------------------------------------

def q3(g: Game, minute: float) -> Answer:
    f0, f1 = int(minute * 1440), int((minute + 1) * 1440)
    a = Answer(3, f"Why did you build, tech or expand (or wait) at {clock(f0)}-{clock(f1)}?", f0)
    decs = g.where("decision", f0, f1, layer="macro")
    tags = {(t["f"], t.get("item")): t for t in g.where("card", f0, f1) if "item" in t}
    if not decs:
        a.say("The macro decided nothing in this minute.")
    units: dict[str, int] = {}
    listed = 0
    for d in decs:
        c = d.get("choice")
        if c is None:
            if d.get("then") and listed < MAX_LINES:
                a.say(f"{clock(d['f'])}: nothing decided: {d['then']}.", d)
                listed += 1
            continue
        if not is_building_or_tech(c) and not d["by"].startswith(("trunk:", "card:")):
            units[_name(d)] = units.get(_name(d), 0) + 1
            continue
        if listed >= MAX_LINES:
            continue
        listed += 1
        sa = [f"{n}: {why}" for n, why in (d.get("over") or [])[:3]]
        fates = _fates(g, d, f1 + 40 * 24)
        last = fates[-1] if fates else None
        tag = tags.get((d["f"], _name(d)))
        a.say(f"{clock(d['f'])}: {c} by {_who(d['by'])}" + (f" ({d['p']:.0%})" if "p" in d else "")
              + (f", money {d['in']['m']}/{d['in']['gas']}" if d.get("in") else "")
              + (f"; set aside first: {'; '.join(sa)}" if sa else "")
              + (f"; then {last['fate']}" + (f": {last['why']}" if last.get("why") else "") if last else "; no order of it yet")
              + (f"; the card (log-only): {tag['tag']}" if tag else "") + ".", d, last, tag)
        for anc in _chain(g, d):
            if anc["kind"] == "strategy_state" and anc.get("transition") == "start":
                a.say(f"   it is {anc['directive']}'s item, started at {clock(anc['f'])} (P_pro {anc['p_pro']:.0%} of "
                      f"{anc['n']} games)", anc)
            elif anc["kind"] == "branch_select":
                a.say(f"   on the branch score of {clock(anc['f'])}: cell \"{_cell_words(anc['cell'], _table(anc.get('table')))}\"", anc)
            elif anc["kind"] == "plan_belief":
                lf = anc["tech"].get("lurker first")
                a.say(f"   from the belief of {clock(anc['f'])}" + (f": lurker first {lf:.0%}" if lf is not None else "")
                      + (", looked" if anc.get("looked") else ", not looked"), anc)
            elif anc["kind"] == "strategy_state" and anc.get("transition") == "card":
                a.say(f"   the card {anc['card_id']} ({anc['adherence']})", anc)
    if units:
        a.say("Units and depots, by the macro model's dice: " + ", ".join(f"{n} x{k}" for n, k in sorted(units.items(), key=lambda kv: -kv[1])) + ".")
    delayed = [t for t in g.where("card", f0, f1) if str(t.get("tag", "")).startswith("delayed")]
    if delayed:
        a.say("Delayed by the card's reading (log-only): " + "; ".join(f"{t['item']} {t['tag']}" for t in delayed[:4]) + ".",
              *delayed[:4])
    waits = [w for w in g.trace() if w.get("kind") == "wait" and w.get("layer") == "macro" and f0 <= w["frame"] < f1]
    if waits:
        s = sum(w["frames"] for w in waits) / 24
        a.say(f"The macro waited {s:.0f} s for the hands in this minute ({len(waits)} times; they were on "
              + ", ".join(sorted({h for w in waits for h in w.get('hands_on', [])})) + ").")
    a.viewer = g.viewer(f0, 3)
    return a


# --- Q4 ------------------------------------------------------------------------------------------------------------

def q4(g: Game, minute: float) -> Answer:
    f = int(minute * 1440)
    f0 = f - 30 * 24
    a = Answer(4, f"Why did your army attack, hold or pull back at {clock(f)}?", f)
    com = g.where("decision", f0, f + 1, layer="commit")
    if not com:
        a.say(f"No army decision in {clock(f0)}-{clock(f)}: the commit model was not asked (no cluster due).")
    for d in com[-4:]:
        top = ", ".join(f"{n} {p:.0%}" for n, p in d.get("top", []))
        why = ", ".join(f"{gname} (without it {q:.0%})" for gname, q in (d.get("why") or [])[:3])
        ins = d.get("in") or {}
        a.say(f"{clock(d['f'])}: the commit model drew {d['choice']} ({d.get('p', 0):.0%}; {top}) for {ins.get('units')} "
              f"units at {ins.get('at')}, commitment then {ins.get('commitment')}"
              + (f"; its odds rest most on {why}" if why else "") + (f"; {d['then']}" if d.get("then") else "") + ".", d)
    sends = [r for r in g.where("note", f0, f + 1) if r["text"].startswith("army (")]
    for r in sends[-3:]:
        a.say(f"{clock(r['f'])}: {r['text']}.", r)
    hunt = g.where("decision", f0, f + 1, layer="hunt advice")
    if hunt:
        a.say(f"The hunt's advice (logged, not carried out in this build): {hunt[-1]['choice']}.", hunt[-1])
    roles: dict[str, int] = {}
    for r in g.where("note", f0, f + 1):
        if r["text"].startswith("fight: ") and "->" in r["text"]:
            role = r["text"].rsplit("-> ", 1)[1]
            roles[role] = roles.get(role, 0) + 1
    if roles:
        a.say("In contact, the role model's orders: " + ", ".join(f"{k} x{v}" for k, v in sorted(roles.items(), key=lambda kv: -kv[1])) + ".")
    deaths = g.where("death", f0, f + 1)
    if deaths:
        alone = sum(1 for d in deaths if d.get("alone"))
        a.say(f"Lost {len(deaths)} fighters ({alone} alone).", deaths[-1])
    conf = [w for w in g.trace() if w.get("kind") == "lease_conflict" and f0 <= w["frame"] <= f]
    if conf:
        a.say(f"{len(conf)} lease conflicts (a layer's order on units another layer held): "
              + "; ".join(f"{w['taker']} {w['intent']} over {', '.join(w['held_by'])}" for w in conf[:3]) + ".")
    a.viewer = g.viewer(f, 4)
    return a


# --- Q5 ------------------------------------------------------------------------------------------------------------

def blocked(d: dict) -> bool:
    s = (d.get("in") or {}).get("supply")
    if not s:
        return False
    u, m = (float(x) for x in s.split("/"))
    return u >= m and m < 200


def q5(g: Game, minute: float) -> Answer:
    f = int(minute * 1440)
    a = Answer(5, f"Why did you miss a defense, supply or timing at {clock(f)}?", f)
    found = False
    decs = g.where("decision", f - 10 * 24, f + 1, layer="macro")
    blk = next((d for d in reversed(decs) if blocked(d)), None)
    if blk:
        found = True
        a.say(f"Supply blocked: {blk['in']['supply']} at {clock(blk['f'])}, {blk['in']['m']} minerals.", blk)
        dep = [d for d in g.where("decision", f - 90 * 24, f + 1, layer="macro") if _name(d) == "Supply Depot"]
        if not dep:
            a.say("No depot decided in the 90 s before it.")
        for d in dep[-3:]:
            fates = _fates(g, d, f + 1)
            a.say(f"{clock(d['f'])}: a depot by {_who(d['by'])}" + (f" ({d['p']:.0%})" if "p" in d else "")
                  + (f", then {fates[-1]['fate']}" + (f": {fates[-1]['why']}" if fates[-1].get('why') else "")
                     if fates else ", no order of it by then") + ".", d, fates[-1] if fates else None)
        placed = [r for r in g.where("order", f - 90 * 24, f + 1) if r["what"].startswith("place Supply Depot")]
        if placed:
            a.say(f"Last depot placed at {clock(placed[-1]['f'])}.", placed[-1])
        hands: dict[str, float] = {}
        h = [r for r in g.where("hands", 0, f + 1)]
        cur = None
        for r in h:
            if r["f"] < f - 30 * 24:
                cur = r
                continue
            if cur is not None:
                k = cur["owner"].split(" (")[0]
                hands[k] = hands.get(k, 0) + (r["f"] - max(cur["f"], f - 30 * 24)) / 24
            cur = r
        if cur is not None:
            k = cur["owner"].split(" (")[0]
            hands[k] = hands.get(k, 0) + (f - max(cur["f"], f - 30 * 24)) / 24
        if hands:
            a.say("The hands in the 30 s before: " + ", ".join(f"{k} {v:.0f} s" for k, v in sorted(hands.items(), key=lambda kv: -kv[1]) if v >= 1) + ".")
        waits = [w for w in g.trace() if w.get("kind") == "wait" and f - 30 * 24 <= w["frame"] <= f]
        if waits:
            a.say("The macro waited for the hands: " + "; ".join(f"{w['wanted'] or 'its next step'} {w['frames'] / 24:.1f} s (hands on "
                                                                  f"{', '.join(w.get('hands_on', []))})" for w in waits[:3]) + ".")
    late = [t for t in g.where("card", f - 30 * 24, f + 1) if "milestone" in t and t.get("tag") not in ("on time",)]
    for t in late[:3]:
        found = True
        a.say(f"The card's milestone {t['milestone']} (due {t['due_s']} s): {t['tag']}.", t)
    drops = [r for r in g.where("order", f - 30 * 24, f + 1, fate="dropped") if r.get("by") in ("macro", "executor", "card")]
    for r in drops[-3:]:
        found = True
        a.say(f"{clock(r['f'])}: {r['what']} dropped: {r.get('why', '')}.", r)
    deaths = g.where("death", f - 30 * 24, f + 1)
    if deaths:
        found = True
        alone = [d for d in deaths if d.get("alone")]
        a.say(f"Lost {len(deaths)} fighters in the 30 s before ({len(alone)} with no other fighter within 6 tiles).",
              deaths[-1])
    if not found:
        a.say(f"No supply block, late milestone, dropped build or loss in the records at {clock(f - 720)}-{clock(f)}.")
    a.viewer = g.viewer(f, 5)
    return a


QUESTIONS = {1: q1, 2: q2, 3: q3, 4: q4, 5: q5}


# --- the baseline: eval/why.py's listing of the same window -----------------------------------------------------

# Each question's eval/why.py view (the pre-Phase-1 way of answering it): its window, the decision layers and record
# kinds a reader would ask it for, and its default order lines (eval/why.py --orders fates: every order that wasn't
# simply sent, and the production orders sent), with its hands column; trimmed to the CAP records nearest the moment.
BASE_VIEW = {
    1: {"win": (0, 0), "layers": ("style", "macro"), "kinds": (), "notes": ()},
    2: {"win": (-120, 0), "layers": (), "kinds": ("seen", "belief"), "notes": ()},
    3: {"win": (0, 60), "layers": ("macro",), "kinds": (), "notes": ()},
    4: {"win": (-30, 0), "layers": ("commit", "hunt advice"), "kinds": ("death",), "notes": ("army (", "fight: ")},
    5: {"win": (-30, 0), "layers": ("macro",), "kinds": ("death",), "notes": ()},
}
BASE_CAP = 16


def baseline(g: Game, q: int, minute: float, cap: int = BASE_CAP) -> Answer:
    """What eval/why.py shows for the question's window (its own lines, through eval/why.py show), over the pre-Phase-1
    record kinds only, trimmed to the cap records nearest the moment (Q1: up to it; Q3: the minute's middle)."""
    import contextlib
    import io
    from types import SimpleNamespace as NS
    from eval.why import PRODUCTION, show
    f = int(minute * 1440)
    v = BASE_VIEW[q]
    f0, f1 = (0, f + 1) if q == 1 else (max(0, f + v["win"][0] * 24), f + v["win"][1] * 24 + 1)
    titles = {1: "Why this opening / strategy card?", 2: f"What did you think the Zerg was doing at {clock(f)}, and from what evidence?",
              3: f"Why did you build, tech or expand (or wait) at {clock(f)}-{clock(f + 1440)}?",
              4: f"Why did your army attack, hold or pull back at {clock(f)}?",
              5: f"Why did you miss a defense, supply or timing at {clock(f)}?"}
    a = Answer(q, titles[q], f)

    def keep(r):
        k = r["kind"]
        if k not in PRE_PHASE1:
            return False
        if k == "hands":
            return True                                     # (why.py's hands column)
        if k == "decision":
            return r["layer"] in v["layers"]
        if k == "order":
            return r["fate"] != "sent" or r["what"].startswith(PRODUCTION)
        if k == "note":
            return bool(v["notes"]) and r["text"].startswith(v["notes"])
        return k in v["kinds"]
    rows = [r for r in g.mine if r["f"] < f1 and keep(r)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        show(rows, f0, f1, NS(side=g.side, slot=None, layer=None, orders="fates", notes="on"))
    groups = []                                             # (frame, the record's lines)
    for s in buf.getvalue().splitlines():
        if not s.strip() or s.startswith(("decisions:", "orders:")):
            continue
        head = s.lstrip()
        if head[:1].isdigit() and ":" in head.split(" ", 1)[0]:
            mm, ss = head.split(" ", 1)[0].split(":")
            groups.append([int((int(mm) * 60 + float(ss)) * 24), [s.rstrip()]])
        elif groups:
            groups[-1][1].append(s.rstrip())
    at = (f0 + f1) / 2 if q == 3 else f
    if len(groups) > cap:
        near = sorted(range(len(groups)), key=lambda i: abs(groups[i][0] - at))[:cap]
        kept = sorted(near)
        a.lines.append(f"(the {cap} records nearest {clock(at)} of {len(groups)} in {clock(f0)}-{clock(f1)})")
        groups = [groups[i] for i in kept]
    for _, ls in groups:
        a.lines.extend(ls)
    if not groups:
        a.lines.append("(no records of these layers in the window)")
    a.viewer = g.viewer(f, q)
    return a


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("game", help="a .records.jsonl or its .rep")
    ap.add_argument("--ask", default="all", help="1-5, or all")
    ap.add_argument("--minute", type=float, default=6.0)
    ap.add_argument("--side", default="T")
    ap.add_argument("--baseline", action="store_true", help="eval/why.py's listing of the same window instead")
    ap.add_argument("--json", action="store_true", help="the answers with their citations as JSON")
    args = ap.parse_args()
    g = Game(args.game, args.side)
    qs = range(1, 6) if args.ask == "all" else [int(args.ask)]
    out = [baseline(g, q, args.minute) if args.baseline else QUESTIONS[q](g, args.minute) for q in qs]
    if args.json:
        print(json.dumps([{"q": a.q, "title": a.title, "lines": a.lines, "cites": a.cites, "viewer": a.viewer}
                          for a in out], indent=1))
    else:
        print("\n\n".join(a.text() for a in out))


if __name__ == "__main__":
    main()

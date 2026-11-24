"""Pre-game strategy (docs/REFOCUS.md §3.2, Phase 1 step 8; G3 "Steerable"): a StrategySpec, the card a side plays and
how strictly, from one of three sources, all before the game (no language model, nothing here runs in the game loop):

  from_style     a style of the catalogue (gary/styles.py) and its card (gary/policy/card.py, the pros' milestones)
  from_replay    a replay's player: its one-off items by CARD_BY_S as milestones at their times, each with the tolerance
                 of the same milestone on the nearest style's card (else that card's median); the style is that card's
                 (the macro model is conditioned on a style), or the one given
  compile_prompt a text request ("standard bio vs hatch-first 2-hatch muta, drill") read against the catalogue's names:
                 each side's style where exactly one matches, else the request back with what matched ("ambiguous": the
                 candidates and their shares) or what did not ("unsupported"); "drill", "practice" or "strict" ask for
                 adherence "strict". Units are production, not a card's milestones: named, they are said to be ignored.

    python -m gary.agent.strategy compile "practice standard bio vs hatch first 2 hatch muta" --out spec.json
    python -m gary.agent.strategy from-replay path/to/game.rep --player NAME --out spec.json
    python -m eval.match --a gt1dev --b gz1dev --map ... --strategy "..."      (or --from-replay PATH)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CARDS = {"TvZ_T": "runs/cards/TvZ_T_20261124.json"}     # (gary/agent/manifests.py SHADOW's)
CARD_BY_S = 8 * 60                                      # a card's milestones: one-offs by then (the cards' own horizon)
CAP_S = 300                                             # the nearest card: a milestone's distance counted up to this


@dataclass(frozen=True)
class StrategySpec:
    race: str
    matchup: str
    style: int | None                                   # the macro model's style (the card's)
    style_name: str | None
    card_id: str
    card: tuple[dict, ...]                              # milestones {item, n, t, tol}, t on the replay's clock (s)
    adherence_mode: str                                 # "strict" (drills) or "reactive"
    source: str                                         # "style", "replay: <name>", "prompt: <text>"
    opponent_style: int | None = None
    opponent_style_name: str | None = None
    status: str = "ok"                                  # "ok", "ambiguous", "unsupported"
    notes: tuple[str, ...] = field(default_factory=tuple)
    covers: tuple | None = None                         # (item, n) the card speaks of (a style's: the key items);
                                                        # None: every one-off (a replay's card)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=1), encoding="utf-8")

    @staticmethod
    def load(path: str | Path) -> "StrategySpec":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        d["card"] = tuple(d["card"])
        d["notes"] = tuple(d.get("notes", ()))
        d["covers"] = None if d.get("covers") is None else tuple(tuple(c) for c in d["covers"])
        return StrategySpec(**d)


def _cards(matchup: str, race: str) -> dict:
    from gary.policy.card import load_cards
    p = CARDS.get(f"{matchup}_{race}")
    if p is None or not (REPO / p).exists():
        return {}
    return {int(k): v for k, v in load_cards(REPO / p)["cards"].items()}


def _name(matchup: str, race: str, style: int | None) -> str | None:
    from gary.styles import catalog
    c = catalog(matchup, race)
    return c["names"].get(style) if c and style is not None else None


def covered(race: str) -> tuple:
    """The (item, n) a style's card speaks of: the taxonomy's key one-offs (gary/policy/card.py build_cards)."""
    sys.path.insert(0, str(REPO / "taxonomy"))
    from discover import KEY_ITEMS
    from gary.policy.card import NOT_ONE_OFF, item_of
    return tuple(sorted({(item_of(n), k) for f, n, k in KEY_ITEMS.get(race, ()) if f not in NOT_ONE_OFF.get(race, ())}))


def from_style(matchup: str, race: str, style: int, mode: str = "reactive", source: str = "style",
               notes: tuple = ()) -> StrategySpec:
    card = _cards(matchup, race).get(int(style), [])
    p = CARDS.get(f"{matchup}_{race}", "none")
    return StrategySpec(race, matchup, int(style), _name(matchup, race, style), f"{Path(p).stem} style {style}",
                        tuple(card), mode, source, notes=tuple(notes) + (() if card else (f"no card for style {style}",)),
                        covers=covered(race) if card else None)


# --- a replay's card ------------------------------------------------------------------------------------------------

def replay_items(path: str | Path, player: str | None, race: str | None,
                 by_s: float | None = CARD_BY_S) -> tuple[str, str, list[dict]]:
    """(player name, race, its one-off items by by_s (None: the whole game) as {item, n, t}) from a replay's commands."""
    import hashlib
    import tempfile
    sys.path.insert(0, str(REPO / "ingest"))
    from build_orders import extract_player
    from cmdcache import P, load_game
    from inventory import find_screp
    from gary.policy.card import item_of
    from gary.race import Race
    path = Path(path)
    game = load_game(find_screp(None), path, hashlib.sha1(path.read_bytes()).hexdigest(),
                     Path(tempfile.gettempdir()) / "gary_strategy_cmds")
    ps = [p for p in game["players"] if not p["observer"]]
    pick = [p for p in ps if (player is None or p["name"] == player) and (race is None or p["race"] == race)]
    if len(pick) != 1:
        raise ValueError(f"{len(pick)} players match (player {player!r}, race {race!r}) of "
                         f"{[(p['name'], p['race']) for p in ps]}: name one with --player")
    p = pick[0]
    r = Race.of(p["race"])
    from gary.policy.army import is_building
    techs = {item_of(n) for n in (*r.tech_names.values(), *r.upgrade_names.values())}
    buildings = {item_of(n) for k, n in r.names.items() if is_building(k)}
    production = {"Supply Depot", "Missile Turret", "Pylon", "Photon Cannon", "Creep Colony", "Sunken Colony",
                  "Spore Colony"}                       # (production and defense: no card's, gary/policy/card.py)
    replay = {"Tank Siege Mode": "Siege Mode"}
    items, count = [], {}
    for it in sorted(extract_player([c for c in game["cmds"] if c[P] == p["id"]], p["race"])[0], key=lambda i: i["t"]):
        if by_s is not None and it["t"] > by_s:
            break
        name = item_of(replay.get(it["name"], it["name"]))
        if name in production or not (name in buildings or name in techs):
            continue
        count[name] = count.get(name, 0) + 1
        items.append({"item": name, "n": count[name], "t": float(it["t"])})
    return p["name"], p["race"], items


def nearest_style(items: list[dict], cards: dict) -> tuple[int | None, float]:
    """The style whose card is nearest the items: each card milestone's distance (up to CAP_S, CAP_S if missing), and
    CAP_S for each item off the card, over both counts."""
    best, score = None, float("inf")
    have = {(i["item"], i["n"]): i["t"] for i in items}
    for s, card in cards.items():
        on = {(m["item"], m["n"]) for m in card}
        d = sum(min(abs(have[(m["item"], m["n"])] - m["t"]), CAP_S) if (m["item"], m["n"]) in have else CAP_S
                for m in card) + CAP_S * sum(1 for k in have if k not in on)
        d /= max(1, len(card) + len(have))
        if d < score:
            best, score = s, d
    return best, score


def from_replay(path: str | Path, matchup: str = "TvZ", player: str | None = None, race: str | None = None,
                style: int | None = None, mode: str = "strict") -> StrategySpec:
    import numpy as np
    name, race, items = replay_items(path, player, race)
    cards = _cards(matchup, race)
    notes = []
    if style is None:
        style, d = nearest_style(items, cards)
        notes.append(f"style {style} ({_name(matchup, race, style)}): the nearest card, {d:.0f} s a milestone")
    ref = {(m["item"], m["n"]): m for m in cards.get(style, [])}
    default_tol = float(np.median([m["tol"] for m in ref.values()])) if ref else 60.0
    card = []
    for i in items:
        m = ref.get((i["item"], i["n"]))
        card.append({"feat": None, "item": i["item"], "n": i["n"], "t": i["t"],
                     "tol": m["tol"] if m else default_tol, "mad": m["mad"] if m else None, "share": None})
    if not ref:
        notes.append(f"no card for style {style}: every tolerance {default_tol:.0f} s")
    else:
        notes.append(f"tolerances of the style's card where it has the milestone, else its median {default_tol:.0f} s")
    return StrategySpec(race, matchup, style, _name(matchup, race, style), f"replay {Path(path).stem} ({name})",
                        tuple(card), mode, f"replay: {Path(path).name}", notes=tuple(notes))


# --- a text request -------------------------------------------------------------------------------------------------

STRICT_WORDS = r"\b(drill|drills|practi[cs]e|strict|exactly)\b"
SIDES = r"\b(?:vs\.?|versus|against)\b"
# each side's words -> a part of the catalogue's names (a style is one whose name holds every part read)
FEATURES = {
    "T": [(r"\b(bio|marines? and medics?|1[- ]?rax(?: fe)?|rax fe|one[- ]barracks)\b", "standard bio"),
          (r"\bvultures?\b", "vultures"),
          (r"\b(starport|wraiths?|valk(?:yrie)?s?|2[- ]?port)\b", "Starport"),
          (r"\b(two[- ]barracks|2[- ]?rax|bbs|proxy)\b", "two-Barracks")],
    "Z": [(r"\b(pool[- ]first|(?:4|5|9|12)[- ]?pool|overpool)\b", "pool first"),
          (r"\b(hatch(?:ery)?[- ]first|12[- ]?hatch)\b", "hatchery first"),
          (r"(?<![\d])\b(2|two)[- ]?hatch(?:es|eries|ery)?\b", "2 hatcheries"),
          (r"(?<![\d])\b(3|three)[- ]?hatch(?:es|eries|ery)?\b", "3 hatcheries"),
          (r"\b(mutas?|mutalisks?|spire)\b", "spire first"),
          (r"\blurkers?\b", "lurker first"),
          (r"\bhydras?\b|\bhydralisks?\b", "hydralisks"),
          (r"\b(lings?|zerglings?)\b", "zergling pressure")],
}
UNITS = r"\b(tanks?|vessels?|goliaths?|firebats?|medics?|scvs?|drones?|defilers?|ultras?|ultralisks?|guardians?)\b"
STOP = {"a", "an", "the", "and", "with", "then", "into", "to", "of", "my", "me", "i", "want", "play", "build", "opening",
        "game", "games", "times", "time", "please", "vs", "versus", "against", "fe", "+", "on", "in", "for", "it"}


def _side(text: str, matchup: str, race: str) -> tuple[list[int], list[str], list[str]]:
    """The styles matching a side's words (every part read in the name), the parts read, the words not understood."""
    from gary.styles import catalog
    c = catalog(matchup, race)
    parts, rest = [], text.lower()
    for pat, part in FEATURES.get(race, []):
        if re.search(pat, rest):
            parts.append(part)
            rest = re.sub(pat, " ", rest)
    rest = re.sub(UNITS, " ", rest)
    rest = re.sub(STRICT_WORDS, " ", rest)
    left = [w for w in re.findall(r"[a-z0-9\-+']+", rest) if w not in STOP and not w.isdigit()]
    if c is None or not parts:
        return [], parts, left
    hits = [k for k, n in c["names"].items() if all(p.lower() in n.lower() for p in parts)]
    return hits, parts, left


def compile_prompt(text: str, matchup: str = "TvZ", race: str = "T") -> StrategySpec:
    from gary.styles import catalog
    enemy = matchup.replace("v", "").replace(race, "", 1) or race
    mode = "strict" if re.search(STRICT_WORDS, text.lower()) else "reactive"
    own_text, *opp = re.split(SIDES, text, maxsplit=1, flags=re.I)
    opp_text = opp[0] if opp else ""
    notes, status = [], "ok"
    units = sorted(set(m.group(0) for m in re.finditer(UNITS, text.lower())))
    if units:
        notes.append(f"units are production, not a card's milestones: {', '.join(units)} ignored")
    style, oppstyle = None, None
    for label, txt, r in (("yours", own_text, race), ("the opponent's", opp_text, enemy)):
        hits, parts, left = _side(txt, matchup, r)
        c = catalog(matchup, r)
        if left:
            notes.append(f"{label}: not understood: {' '.join(left)}")
        if not parts and left:
            status = "unsupported"
            notes.append(f"{label}: no style of the catalogue read from it")
            continue
        if not parts:
            if label == "yours":
                if c is not None:
                    k = max(c["shares"], key=c["shares"].get)
                    notes.append(f"yours: no build named: the pros' commonest, {c['names'][k]} ({c['shares'][k]:.0%})")
                    style = k
            continue
        if len(hits) == 1:
            if label == "yours":
                style = hits[0]
            else:
                oppstyle = hits[0]
        elif not hits:
            status = "unsupported"
            notes.append(f"{label}: no style of the catalogue is {' + '.join(parts)}")
        else:
            status = "ambiguous" if status == "ok" else status
            notes.append(f"{label}: {' + '.join(parts)} is " + "; ".join(
                f"{k} {c['names'][k]} ({c['shares'].get(k, 0):.1%})" for k in hits))
    if style is None:
        return StrategySpec(race, matchup, None, None, "none", (), mode, f"prompt: {text}", oppstyle,
                            _name(matchup, enemy, oppstyle), "unsupported" if status == "ok" else status, tuple(notes))
    spec = from_style(matchup, race, style, mode, f"prompt: {text}", tuple(notes))
    return StrategySpec(**{**asdict(spec), "card": spec.card, "notes": spec.notes, "covers": spec.covers,
                           "opponent_style": oppstyle,
                           "opponent_style_name": _name(matchup, enemy, oppstyle), "status": status})


def describe(spec: StrategySpec) -> str:
    lines = [f"{spec.status}: {spec.race} in {spec.matchup}, style {spec.style} ({spec.style_name}), {spec.adherence_mode}; "
             f"card {spec.card_id} ({len(spec.card)} milestones); from {spec.source}"]
    if spec.opponent_style is not None:
        lines.append(f"  the opponent: style {spec.opponent_style} ({spec.opponent_style_name})")
    for m in spec.card:
        lines.append(f"  {m['item']} #{m['n']} at {int(m['t']) // 60}:{int(m['t']) % 60:02d} +- {m['tol']:.0f} s")
    lines += [f"  note: {n}" for n in spec.notes]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compile")
    c.add_argument("text")
    r = sub.add_parser("from-replay")
    r.add_argument("path")
    r.add_argument("--player")
    r.add_argument("--race")
    r.add_argument("--style", type=int)
    r.add_argument("--mode", default="strict")
    for p in (c, r):
        p.add_argument("--matchup", default="TvZ")
        p.add_argument("--out")
    c.add_argument("--race", default="T")
    args = ap.parse_args()
    if args.cmd == "compile":
        spec = compile_prompt(args.text, args.matchup, args.race)
    else:
        spec = from_replay(args.path, args.matchup, args.player, args.race, args.style, args.mode)
    print(describe(spec))
    if args.out:
        spec.save(args.out)
    if spec.status != "ok":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

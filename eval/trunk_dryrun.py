"""The trunk's rule replayed over played games, 0 games (docs/REFOCUS.md Phase 1 step 7b): when would option `trunk` have
started each directive, and was the Zerg's tech what it said? A game with the trunk is the same game as without it
until the first goal of a directive, so the rule run over the rounds without it (the belief from the re-simulated
view, train/plan_belief.py gary_game; the looked state from the sighting states, sight_job; the own state from the
replay's commands, eval/answer_time.py) predicts each start before the games are played.

Per game: the Zerg's plan (the pros' rule), the first moment the rule starts PREP_VS_LURKER (its P_pro, cell, n), the
Zerg's lurker tech by then in truth (a Hydralisk Den with a Lair, or Lurker Aspect, ordered by then: else a false
start), the delay from Lurker Aspect, and the round's own Siege Mode.

    python -m eval.trunk_dryrun --rounds NA292a9 NA292a1 NA292a0 NA292a4
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))
sys.path.insert(0, str(REPO / "taxonomy"))

from eval import monitor, priority  # noqa: E402

BRANCH = "PREP_VS_LURKER"


def items_of(rep: str) -> dict:
    """{T: {name: first second}, Z: {...}} from the replay's commands (units read from the raw Train commands)."""
    from build_orders import extract_player
    from cmdcache import P, load_game
    from inventory import find_screp
    from eval.answer_time import LATE_UNITS, trains
    game = load_game(find_screp(None), Path(rep), hashlib.sha1(rep.encode()).hexdigest(),
                     Path(tempfile.gettempdir()) / "gary_answer_cmds")
    ps = {p["race"]: p for p in game["players"] if not p["observer"]}
    out = {}
    for r in "TZ":
        its = extract_player([c for c in game["cmds"] if c[P] == ps[r]["id"]], r)[0]
        if r == "T":
            its = [i for i in its if i["name"] not in LATE_UNITS] + trains(game["cmds"], ps["T"]["id"], LATE_UNITS)
        first = {}
        for i in sorted(its, key=lambda i: i["t"]):
            first.setdefault(i["name"], i["t"])
        out[r] = first
    return out


def one(job):
    from train.plan_belief import gary_game, sight_job
    rep, race, enemy, map_name, matchup = job
    g = gary_game(job)
    if g is None:
        return None
    sg = sight_job((rep, rep, race, enemy, g[6]))
    return rep, g, sg, items_of(rep)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", nargs="+", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--table", help="the pro table (default: the manifest's TRUNK)")
    ap.add_argument("--contrast", nargs="+", default=[None], help="contrast levels to compare (same, finest; default: the table's)")
    priority.add_argument(ap)
    args = ap.parse_args()
    priority.apply(args.priority)
    import numpy as np
    from gary.agent.contracts import OwnContext, PlanBelief as Belief, SightingView
    from gary.agent.manifests import TRUNK
    from gary.agent.selector import ProFrequencyScorer
    from gary.agent.contracts import CandidateBranch, StrategyState, NotEnoughEvidence
    from gary.policy.plan_belief import PlanBelief, is_looked, tech_of
    from train.plan_belief import sight_at
    from ladder_maps import clean_name
    model = PlanBelief(REPO / TRUNK["plan_belief"]["TvZ_T"])
    scorer = ProFrequencyScorer({BRANCH: Path(args.table) if args.table else REPO / TRUNK["tables"]["TvZ_T"][BRANCH]})
    meta0 = dict(scorer.tables[BRANCH]["meta"])
    jobs = [(str(p), "T", "Z", p.parent.name, "TvZ") for r in args.rounds
            for p in sorted((REPO / "runs" / "league" / r).rglob("*.rep"))]
    with ProcessPoolExecutor(args.workers) as pool:
        res = list(monitor.track(pool.map(one, jobs), len(jobs), "games"))
    from build_orders import secs
    reads = []
    for job, r in zip(jobs, res):
        if r is None or r[2] is None:
            print(f"  {job[0]}: not read")
        else:
            reads.append(r)
    replay = {"Siege Mode": "Tank Siege Mode"}
    for mode in args.contrast:
        scorer.tables[BRANCH]["meta"] = {**meta0, **({"contrast_level": mode} if mode else {})}
        meta = scorer.tables[BRANCH]["meta"]
        chains = meta.get("chains") or (("Factory", "Machine Shop", "Siege Mode"),)
        print(f"== contrast {meta.get('contrast_level', 'same')} ({Path(scorer.tables[BRANCH]['name']).name})")
        rows = []
        for rep, g, sg, items in reads:
            Xs, idx, plan, m = g[0], g[1], g[4], clean_name(g[5])
            T, Z = items["T"], items["Z"]
            start, never = None, None
            for k, t in enumerate(idx):
                t = int(t)
                rt = secs(24 * t)                    # (the replay items' clock: 42 ms a frame, the sample's at frame 24 t)
                have = {n for ch in chains for n in ch if T.get(replay.get(n, n), 1e9) <= rt}
                if "chains" not in meta and "Siege Mode" in have:
                    never = "Siege Mode had"
                    break
                odds = model.odds(Xs[k], m)
                tech = {}
                for name, p in odds.items():
                    tech[tech_of(name)] = tech.get(tech_of(name), 0.0) + p
                f = sight_at(sg, t)
                view = SightingView({}, {}, frozenset(), {}, is_looked(f), None)
                b = Belief(t * 24, odds, tech, view, {}, 0, "")
                units = {n: 1 for n in have if n != "Siege Mode"}
                res_ = frozenset({"Siege Mode"} & have)
                ctx = OwnContext(t * 24, "T", "Z", "TvZ", m, units, res_, 0, 0, 0, 0)
                s = scorer.score(b, StrategyState(None, [], "reactive"), ctx, [CandidateBranch(BRANCH, {})])[BRANCH]
                if isinstance(s, NotEnoughEvidence) and "every chain had" in s.why:
                    never = "every chain had"
                    break
                if not isinstance(s, NotEnoughEvidence) and s.take:
                    start = (rt, s, tech.get("lurker first", 0.0), view.looked,
                             "".join(str(sum(n in have for n in ch)) for ch in chains))
                    break
            lurk_t = Z.get("Lurker Aspect")
            den_lair = max(Z.get("Hydralisk Den", 1e9), Z.get("Lair", 1e9))
            truth = start is not None and (min(lurk_t or 1e9, den_lair) <= start[0])
            rows.append((plan, start, truth, lurk_t))
            tag = Path(rep).parent.parent.name + "/" + Path(rep).parent.name[:12]
            sm = T.get("Tank Siege Mode")
            if start is None:
                print(f"  {tag:30s} {plan}: no start ({never or 'ran to 10:00'}; Siege Mode at {sm})")
            else:
                t, s, pl, lk, pos = start
                print(f"  {tag:30s} {plan}: start {t // 60}:{t % 60:02d} chains {pos} P_pro {s.p:.2f} n {s.n} {s.cell} "
                      f"(backoff {s.level}) vs {s.base_cell} hi {s.base_hi}, P(lurker) {pl:.2f} "
                      f"{'looked' if lk else 'unlooked'}; lurker tech by then {'yes' if truth else 'NO'}; "
                      f"Lurker Aspect {lurk_t}, the round's Siege Mode {sm}")
        lur = [r for r in rows if r[3] is not None]
        non = [r for r in rows if r[3] is None]
        print(f"lurker games (Lurker Aspect researched): {len(lur)}, started {sum(r[1] is not None for r in lur)}; "
              f"other games {len(non)}, started {sum(r[1] is not None for r in non)}, of all starts false (no lurker tech "
              f"by then) {sum(1 for r in rows if r[1] is not None and not r[2])}")
        lag = [r[1][0] - r[3] for r in lur if r[1] is not None]
        if lag:
            print(f"  start after Lurker Aspect: {sorted(lag)} s (median {np.median(lag):+.0f})")

if __name__ == "__main__":
    main()

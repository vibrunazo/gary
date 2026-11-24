"""The strategy selector (ARCHITECTURE.md §6.8; docs/CONTROL.md step 7): which build style to play.

A symbolic decision learned by counting outcomes, the per-game choice the architecture gives the
learning where single decisions drown in chaos (a pair of branches of the same moment differs by sd
848 net value; a build style is worth hundreds over a game). Options: the build styles the macro
model knows (taxonomy clusters, gary/policy/macro.py's style input: 1 standard bio, 2 Factory and
vultures, 3 Factory and Starport, 4 two-Barracks marines) and none (the model unsteered). Context:
the map. The table: each option's games won, lost and still going at the time limit, per map
(TABLE, from eval/vs_rush.py's games: eval/selector_table.py).

Each option's score is a Beta posterior over (won + half the undecided) / games. In play the best
expected score; in training a draw from each (Thompson sampling), so options still in doubt keep
being tried. A map with few games borrows from all maps.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from pathlib import Path

OPTIONS = [None, 1, 2, 3, 4]
BORROW = 20                          # a map's cell with fewer games than this leans on all maps'


def table_path() -> Path:
    root = Path(os.environ.get("GARY_DATA", Path(__file__).resolve().parents[2] / "data"))
    return root / "interim" / "selector" / "tvz_styles.json"


def map_key(mapinfo) -> str:
    """The same map in any game or replay: its size and start locations (as gary/terrain.py's cache)."""
    return hashlib.sha1(json.dumps([list(mapinfo.size), sorted(map(list, mapinfo.starts))]).encode()).hexdigest()[:16]


def _name(option) -> str:
    return "none" if option is None else str(option)


class StrategySelector:
    def __init__(self, table: dict | None = None):
        self.table = table if table is not None else (json.loads(table_path().read_text(encoding="utf-8"))
                                                      if table_path().exists() else {})

    def counts(self, key: str, option) -> tuple[float, float]:
        """(good, bad): won + half the undecided, lost + half the undecided; this map's, or all maps'
        scaled down to BORROW games where this map has few."""
        def cell(c):
            w, l, t = c.get("won", 0), c.get("lost", 0), c.get("time", 0)
            return w + t / 2, l + t / 2
        here = cell(self.table.get(key, {}).get(_name(option), {}))
        if sum(here) >= BORROW:
            return here
        allg = [cell(m.get(_name(option), {})) for m in self.table.values()]
        g, b = sum(a for a, _ in allg), sum(b for _, b in allg)
        n = g + b
        k = max(0.0, BORROW - sum(here)) / n if n else 0.0
        return here[0] + g * k, here[1] + b * k

    def choose(self, key: str, explore: bool = False, rng: random.Random | None = None):
        """The option: the best expected score, or (explore) the best of a draw from each posterior."""
        rng = rng or random.Random()
        best, best_v = None, -1.0
        for o in OPTIONS:
            g, b = self.counts(key, o)
            v = rng.betavariate(g + 1, b + 1) if explore else (g + 1) / (g + b + 2)
            if v > best_v:
                best, best_v = o, v
        return best

    def add(self, key: str, option, result: str) -> None:
        """One game's outcome: "won", "lost" or "time"."""
        c = self.table.setdefault(key, {}).setdefault(_name(option), {})
        c[result] = c.get(result, 0) + 1

    def save(self) -> None:
        table_path().parent.mkdir(parents=True, exist_ok=True)
        table_path().write_text(json.dumps(self.table, indent=1), encoding="utf-8")


class ProFrequencyScorer:
    """The trunk's branch scorer (docs/REFOCUS.md §3.2, Phase 1 step 7b; contracts.BranchScorerProvider
    "pro_freq_table"): P_pro(branch | belief, context), what pros do, from the tables of train/pro_branch.py, pinned
    files. A cell under the table's support floor (min_n modern games) leans on its parent by the table's written
    backoff; none at the root: not enough evidence. The branch is taken where P_pro reaches the table's threshold and
    its interval is clear of the contrast cell's (the same cell with a low belief): the share of the choice the
    belief makes, not the base rate (BranchScore.take). The pros' win rate in the cell rides along as context only, never
    decided on (§3.2: survivor bias, and the style-4 lesson of the table above)."""

    def __init__(self, tables: dict[str, str | Path]):
        self.tables = {}                           # branch -> {"meta", "cells"}
        for branch, path in tables.items():
            t = json.loads(Path(path).read_text(encoding="utf-8"))
            self.tables[branch] = {**t, "name": Path(path).name}

    @staticmethod
    def fields(meta: dict, belief, ctx) -> dict:
        """The cell's fields for a moment, as train/pro_branch.py reads the pros' (the race's names of its stages)."""
        import numpy as np
        p = belief.tech_probs.get(meta["tech"], 0.0)
        stage = 2 if ctx.units.get("Machine Shop", 0) else 1 if ctx.units.get("Factory", 0) else 0
        return {"belief": int(np.searchsorted(meta["buckets"], p, side="right")),
                "looked": int(bool(belief.sightings.looked)) if belief.sightings is not None else 0,
                "stage": stage, "minute": int(np.searchsorted(meta["minutes"], ctx.frame / 24, side="right"))}

    def score(self, belief, strategy, ctx, candidates):
        from gary.agent.contracts import BranchScore, NotEnoughEvidence
        out = {}
        for c in candidates:
            t = self.tables.get(c.name)
            if t is None:
                out[c.name] = NotEnoughEvidence("pro_freq_table", f"no table for {c.name}")
                continue
            meta, cells = t["meta"], t["cells"]
            f = self.fields(meta, belief, ctx)
            for level, keys in enumerate(meta["backoff"]):
                key = "|".join(f"{k}={f[k]}" for k in keys)
                cell = cells.get(key)
                if cell is not None and cell["games"] >= meta["min_n"]:
                    base = cells.get("|".join(f"{k}={({**f, **meta.get('contrast', {})})[k]}" for k in keys))
                    out[c.name] = BranchScore(cell["p"], cell["lo"], cell["hi"], cell["games"], key, level,
                                              cell["pro_won_if_taken"], cell["pro_won_if_not"],
                                              base["p"] if base else None, base["hi"] if base else None,
                                              cell["p"] >= meta["threshold"] and base is not None and cell["lo"] > base["hi"])
                    break
            else:
                root = cells.get("|".join(f"{k}={f[k]}" for k in meta["backoff"][-1]))
                out[c.name] = NotEnoughEvidence("pro_freq_table", f"{c.name}: n {root['games'] if root else 0} under "
                                                                  f"{meta['min_n']} at the root cell")
        return out

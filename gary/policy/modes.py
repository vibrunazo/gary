"""A unit's situation as the judge reads it (eval/judge.py), and the models of a mode's entry and exit on it.

The situation: the fight around one unit with every own unit's mode hidden (no type, order, cooldown or motion): the
enemy near it by range and kind, its own side near it, the terrain, the minute, and its recent past (HISTORY: the
enemy near it 2 and 5 s before, how long the enemy has been near, how long it has been in the fight). The judge asks
of it whether a pro's unit would be in a mode there. The mode models ask the two questions that get a unit there: of
a unit out of the mode, the odds a pro's is in it half a second later, and of one in it, the odds it has left
(train/modes.py, from the pros' own transitions). The role model (gary/policy/roles.py) names a siege among fourteen
decisions from the unit's own state as well, and its odds of one are flat over the situations where the pros' are
steep: a pro's tank sieges in 0.7% of its half seconds in the fifth of situations the judge finds least likely and
7.1% in the likeliest, a draw from the role model's odds in 0.9% and 2.3% (RD264a, docs/PROGRESS.md 2026-11-13).
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

TILE = 32.0
FAR = 40.0                      # tiles: no such unit in the snapshot
KINDS = 8                       # the enemy's commonest fighter types, each its supply within 12 tiles


def tables():
    from gary.policy.army import ARMY_SUPPLY, STATIC_SUPPLY, is_building
    from gary.races import FLYERS
    sup = np.asarray(ARMY_SUPPLY, np.float32) / 2
    air = np.zeros(228, bool)
    air[list(FLYERS)] = True
    build = np.array([is_building(t) for t in range(228)])
    static = np.zeros(228, bool)
    static[list(STATIC_SUPPLY)] = True
    return sup, air, build, static


def enemy_kinds(rows: np.ndarray, count: np.ndarray) -> list[int]:
    """The enemy's commonest fighter types in a dataset."""
    sup, _, build, _ = tables()
    valid = np.arange(rows.shape[1])[None, :] < count[:, None]
    t = rows[:, :, 0][valid & (rows[:, :, 1] == 0)]
    t = t[(t >= 0) & (t < 228)]
    n = np.bincount(t[(sup[t] > 0) & ~build[t]], minlength=228)
    return [int(i) for i in np.argsort(-n)[:KINDS] if n[i] > 0]


def names(kinds: list[int]) -> list[str]:
    return (["minute", "hp", "targeted"] + [f"terrain{i}" for i in range(8)]
            + [f"enemy ground within {r}" for r in (4, 8, 12, 16)] + [f"enemy air within {r}" for r in (8, 16)]
            + ["nearest enemy ground", "nearest enemy air", "nearest enemy building", "enemy static within 12",
               "own fighters within 4", "own fighters within 8", "own in the mode's types within 6",
               "nearest own building", "own buildings within 8", "enemy supply seen", "own supply seen"]
            + [f"enemy type {k} within 12" for k in kinds])


HISTORY = ["enemy ground within 8, 2 s ago", "enemy ground within 8, 5 s ago", "nearest enemy ground, 2 s ago",
           "nearest enemy ground, 5 s ago", "seconds with enemy ground within 12", "seconds in the moments"]
AGO = (2.0, 5.0)
SPELL_MAX = 60.0


def history(X: np.ndarray, names: list[str], game: np.ndarray, tag: np.ndarray, time: np.ndarray) -> np.ndarray:
    """(n, len(HISTORY)): the unit's own recent past, from the moments of the same game and unit: the enemy near it
    AGO seconds before (the latest moment at or before then, within 10 s: else now's value), how long enemy ground
    has been within 12 tiles without a break (capped), and how long it has been in the moments at all. (The
    instant says only part of a pro's choice: a tank sieges as the enemy comes, and unsieges once it is gone.)"""
    e8, e12, near = (names.index("enemy ground within 8"), names.index("enemy ground within 12"),
                     names.index("nearest enemy ground"))
    out = np.zeros((len(X), len(HISTORY)), np.float32)
    order = np.lexsort((time, tag, game))
    g, t, tm = game[order], tag[order], time[order]
    cut = np.flatnonzero((g[1:] != g[:-1]) | (t[1:] != t[:-1])) + 1
    for a, b in zip(np.r_[0, cut], np.r_[cut, len(order)]):
        idx = order[a:b]
        tt = tm[a:b]
        x8, x12, xn = X[idx, e8], X[idx, e12], X[idx, near]
        for j, ago in enumerate(AGO):
            k = np.searchsorted(tt, tt - ago, side="right") - 1
            ok = (k >= 0) & (tt - tt[np.clip(k, 0, None)] <= ago + 10)
            kk = np.where(ok, k, np.arange(len(tt)))
            out[idx, j] = x8[kk]
            out[idx, 2 + j] = xn[kk]
        since = tt[0]
        last_clear = -np.inf
        for i in range(len(tt)):
            if i and tt[i] - tt[i - 1] > 10:              # (a gap: a new spell of moments)
                since, last_clear = tt[i], -np.inf
            if x12[i] <= 0:
                last_clear = tt[i]
            out[idx[i], 4] = min(tt[i] - (last_clear if last_clear > -np.inf else since), SPELL_MAX)
            out[idx[i], 5] = min(tt[i] - since, SPELL_MAX)
    return out


def features(rows: np.ndarray, extra: np.ndarray, count: np.ndarray, time: np.ndarray, tags: np.ndarray, types: set,
             kinds: list[int], into: int = -1, batch: int = 2000):
    """(X, y, snapshot index, unit tag) for every own unit of the judged types: the situation around it, modes
    hidden; y: whether its type is the state's (into; an event's y comes from the commands instead)."""
    sup, air, build, static = tables()
    width = rows.shape[1]
    X, Y, S, T = [], [], [], []
    has = np.isin(rows[:, :, 0], sorted(types)) & (rows[:, :, 1] == 1)
    has &= np.arange(width)[None, :] < count[:, None]
    snaps = np.flatnonzero(has.any(1))
    notself = ~np.eye(width, dtype=bool)[None]
    for a in range(0, len(snaps), batch):
        idx = snaps[a:a + batch]
        r = rows[idx].astype(np.float32)
        t = np.clip(rows[idx, :, 0].astype(np.int64), 0, 227)
        valid = np.arange(width)[None, :] < count[idx][:, None]
        own, foe = valid & (rows[idx, :, 1] == 1), valid & (rows[idx, :, 1] == 0)
        mine = has[idx]                                           # (the judged units)
        fighter = (sup[t] > 0) & ~build[t] & (r[:, :, 10] > 0)
        eg, ea = foe & fighter & ~air[t], foe & fighter & air[t]
        eb, es = foe & build[t], foe & static[t]
        of = own & fighter & ~mine
        ob = own & build[t]
        d = np.sqrt(((r[:, :, None, 2:4] - r[:, None, :, 2:4]) ** 2).sum(-1)) / TILE      # (snapshot, unit, other)
        s = sup[t][:, None, :]
        one = np.ones_like(s)

        def within(mask, radius, weight=s):
            return ((mask[:, None, :] & (d <= radius)) * weight).sum(-1)

        def nearest(mask):
            return np.where(mask[:, None, :], d, FAR).min(-1).clip(max=FAR)

        def whole(v):
            return np.broadcast_to(v[:, None], t.shape)

        cols = [whole(time[idx] / 60.0), r[:, :, 4], extra[idx, :, 2].astype(np.float32)]
        cols += [extra[idx, :, 6 + i].astype(np.float32) for i in range(8)]
        cols += [within(eg, x) for x in (4, 8, 12, 16)] + [within(ea, x) for x in (8, 16)]
        cols += [nearest(eg), nearest(ea), nearest(eb), within(es, 12, one)]
        cols += [within(of, 4), within(of, 8), ((mine[:, None, :] & (d <= 6) & notself) * one).sum(-1)]
        cols += [nearest(ob), within(ob, 8, one)]
        cols += [whole(((eg | ea) * sup[t]).sum(1)), whole(((own & fighter) * sup[t]).sum(1))]
        cols += [within(foe & fighter & (t == k), 12) for k in kinds]
        f = np.stack(cols, -1)
        X.append(f[mine].astype(np.float32))
        Y.append((rows[idx, :, 0] == into)[mine])
        S.append(np.broadcast_to(idx[:, None], t.shape)[mine])
        T.append(np.asarray(tags[idx])[mine].astype(np.int64))
    if not X:
        return (np.zeros((0, len(names(kinds))), np.float32), np.zeros(0, bool), np.zeros(0, np.int64),
                np.zeros(0, np.int64))
    return np.concatenate(X), np.concatenate(Y), np.concatenate(S), np.concatenate(T)


# race -> state -> (the type out of the mode, the type in it, the role that enters it, the role that leaves it)
STATES = {"T": {"siege": (5, 30, "siege", "unsiege")}}
TURN_S = 0.5                    # the models' odds are over this long (the datasets' half second)
NEXT_S = 0.6                    # a unit's next moment this soon is its next half second
KEEP_S = 75.0                   # Situations: a unit's past kept this long (HISTORY looks back SPELL_MAX and 10 s)


def transitions(m: dict, state: tuple, kinds: list[int]):
    """A dataset's unit-moments that have a next half second, as (X with HISTORY, in the mode now, in it then, game)."""
    out, into = state[0], state[1]
    X, y, s, tag = features(m["rows"], m["extra"], m["count"], m["time"], m["tags"], {out, into}, kinds, into)
    game, time = m["game"][s], m["time"][s]
    X = np.concatenate([X, history(X, names(kinds), game, tag, time)], 1)
    order = np.lexsort((time, tag, game))
    X, y, game, tag, time = X[order], y[order].astype(np.int8), game[order], tag[order], time[order]
    nxt = np.zeros(len(y), bool)
    then = np.zeros(len(y), np.int8)
    nxt[:-1] = (game[1:] == game[:-1]) & (tag[1:] == tag[:-1]) & (time[1:] - time[:-1] <= NEXT_S)
    then[:-1] = y[1:]
    return X[nxt], y[nxt], then[nxt], game[nxt]


class ModeModel:
    """A state's two models (train/modes.py): the odds a unit out of the mode enters it in the next half second, and
    that one in it leaves."""

    def __init__(self, path: str | Path):
        with open(path, "rb") as f:
            d = pickle.load(f)
        self.enter, self.leave, self.kinds, self.state, self.path = d["enter"], d["leave"], d["kinds"], d["state"], str(path)

    def odds(self, X: np.ndarray, in_mode: np.ndarray) -> np.ndarray:
        """Per unit: the odds it changes mode in the next half second (enters if out of it, leaves if in it)."""
        out = np.zeros(len(X))
        in_mode = np.asarray(in_mode, bool)
        if (~in_mode).any():
            out[~in_mode] = self.enter.predict_proba(X[~in_mode])[:, 1]
        if in_mode.any():
            out[in_mode] = self.leave.predict_proba(X[in_mode])[:, 1]
        return out


def latest(matchup: str, race: str, state: str) -> Path | None:
    """The newest mode model of the state for this race in this matchup (runs/modes/<matchup>_<race>_<state>_*.pkl)."""
    found = sorted(Path("runs/modes").glob(f"{matchup}_{race}_{state}_*.pkl"))
    return found[-1] if found else None


class Situations:
    """The situations of a game's units as it is played: each turn's snapshot read as the datasets' moments are
    (features), each unit's recent past kept for its HISTORY (the same code as the datasets': history)."""

    def __init__(self, kinds: list[int]):
        self.kinds = kinds
        self.names = names(kinds)
        self.cols = [self.names.index(c) for c in ("enemy ground within 8", "enemy ground within 12", "nearest enemy ground")]
        self.short = ["enemy ground within 8", "enemy ground within 12", "nearest enemy ground"]
        self.past: dict[int, list[tuple]] = {}        # tag -> [(time, within 8, within 12, nearest)]

    def read(self, rows: np.ndarray, extra: np.ndarray, tags: list[int], time_s: float, types: set) -> dict[int, np.ndarray]:
        """tag -> its situation with HISTORY, for the snapshot's own units of these types."""
        n = len(rows)
        X, _, _, tag = features(rows[None], extra[None, :n, :14], np.array([n]), np.array([time_s], np.float32),
                                np.asarray(tags, np.int64)[None], types, self.kinds)
        out = {}
        for x, t in zip(X, tag):
            past = [p for p in self.past.get(int(t), []) if time_s - p[0] <= KEEP_S and p[0] < time_s]
            past.append((time_s, *x[self.cols]))
            self.past[int(t)] = past
            a = np.array(past, np.float32)
            h = history(a[:, 1:], self.short, np.zeros(len(a), np.int64), np.zeros(len(a), np.int64), a[:, 0])
            out[int(t)] = np.concatenate([x, h[-1]])
        if len(self.past) > 400:                      # (the dead)
            self.past = {t: p for t, p in self.past.items() if time_s - p[-1][0] <= KEEP_S}
        return out

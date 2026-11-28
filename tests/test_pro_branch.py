"""train/pro_branch.py's PREP_VS_MUTA helpers without data (fast): the ring's position against the bases standing, and
the turret caps' quantile by the minute.

Run: python -m pytest tests/test_pro_branch.py   (or plain: python tests/test_pro_branch.py)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ingest"))

import train.pro_branch as pb  # noqa: E402

M = 24 * 60                                         # frames a minute


def test_ring_position_counts_turrets_against_the_bases():
    g = {"Engineering Bay": 4 * M, "turrets": [5 * M, 6 * M, 7 * M], "cc": [3 * M]}
    assert pb.ring_position(g, 3.5 * M) == 0          # no Engineering Bay yet
    assert pb.ring_position(g, 4.5 * M) == 1          # two bases (the start and one ordered), no turret
    assert pb.ring_position(g, 6.5 * M) == 2          # two turrets: one a base
    assert pb.ring_position(g, 7.5 * M) == 2          # three: under twice the bases
    g["turrets"].append(8 * M)
    assert pb.ring_position(g, 8.5 * M) == 3          # four: the ring had
    g["cc"].append(8.2 * M)
    assert pb.ring_position(g, 8.5 * M) == 2          # a third base: back to filling it


def test_turret_caps_take_the_quantile_by_minute_at_a_lurker_belief():
    pb.MIN_N = 3
    games = {f"g{i}": {"turrets": [5 * M] * i} for i in range(5)}      # 0..4 turrets ordered by 5:00
    d = {"rel_path": np.array(list(games)), "t": np.array([330] * 5)}
    caps = pb.turret_caps(d, np.array([0.9, 0.9, 0.9, 0.9, 0.1]), games)
    assert list(caps) == [5] and caps[5]["games"] == 4                   # the low-belief game left out
    assert caps[5]["q"] == np.quantile([0, 1, 2, 3], pb.TURRET_CAP_Q)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok  ", name)

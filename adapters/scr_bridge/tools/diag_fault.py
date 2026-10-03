#!/usr/bin/env python3
"""Narrow down which read path faults in a live game (read-only diagnostics).

Runs each reader separately so a fault in one does not hide the others:
    python adapters/scr_bridge/tools/diag_fault.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from gary.env import GameError  # noqa: E402
from gary.scr_env import ScrGame  # noqa: E402


def try_call(name: str, fn) -> None:
    try:
        result = fn()
        print(f"ok    {name}: {str(result)[:100]}")
    except GameError as e:
        print(f"FAULT {name}: {e}")


def main() -> None:
    game = ScrGame.connect()
    try_call("status", game.status)
    try_call("start_locations (game struct only)", game.start_locations)
    try_call("probe_unit tag=1 (one unit struct)", lambda: game.probe_unit(1))
    try_call("probe_unit tag=2 (one unit struct)", lambda: game.probe_unit(2))
    try_call("probe_unit tag=2049 (gen bits set)", lambda: game.probe_unit(2049))
    try_call("unit_at(0, 100, 100) (unit list walk)",
             lambda: game.unit_at(0, 100, 100))
    try_call("depot_spot_ok(5, 5) (unit list walk)", lambda: game.depot_spot_ok(5, 5))
    try_call("observe (everything)", game.observe)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Spot-check unit-struct offsets against the live game (resources amount, shields).

    python adapters/scr_bridge/tools/diag_offsets.py

Prints the raw window fields around the candidate offsets so the profile constants in
src/scr_profile.h can be corrected from evidence instead of guesses.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from gary.scr_env import ScrGame  # noqa: E402

MINERAL_TYPE = 176
NEUTRAL = 11


def main() -> None:
    game = ScrGame.connect()
    obs = game.observe()
    print(f"frame={obs['frame']} units={len(obs['units'])}")

    n = 0
    for u in obs["units"]:
        if u["type"] != MINERAL_TYPE or u["owner"] != NEUTRAL:
            continue
        raw = game.probe_unit(u["tag"])
        if not raw:
            continue
        win = bytes.fromhex(raw.get("window_hex", ""))
        start = int(raw.get("window_start", 0))

        def u16(o: int) -> int:
            return int.from_bytes(win[o - start:o - start + 2], "little")

        print(f"mineral tag={u['tag']} obs.resources={u['resources']} "
              f"raw_resources={raw.get('raw_resources')} "
              f"u16@200={u16(200)} u16@202={u16(202)} u16@204={u16(204)} "
              f"u16@206={u16(206)} u16@208={u16(208)} u16@210={u16(210)}")
        n += 1
        if n >= 4:
            break

    n = 0
    for u in obs["units"]:
        if u["type"] not in (64, 65, 66):  # probe / zealot / dragoon (openbw ids)
            continue
        raw = game.probe_unit(u["tag"])
        if not raw:
            continue
        win = bytes.fromhex(raw.get("window_hex", ""))
        start = int(raw.get("window_start", 0))

        def u32(o: int) -> int:
            return int.from_bytes(win[o - start:o - start + 4], "little")

        print(f"protoss type={u['type']} tag={u['tag']} keys={sorted(raw)} "
              f"u32@96>>8={u32(96) >> 8} u32@100>>8={u32(100) >> 8} "
              f"u32@104>>8={u32(104) >> 8} raw_shields={raw.get('raw_shields')}")
        n += 1
        if n >= 4:
            break


if __name__ == "__main__":
    main()

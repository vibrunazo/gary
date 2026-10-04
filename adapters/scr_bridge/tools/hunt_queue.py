#!/usr/bin/env python3
"""Pin kUnitBuildQueue / kUnitBuildSlot by measurement (README verification step 3).

Selects the local player's production building, snapshots probe_unit's raw window, sends one
train via act(), and diffs the windows: the u16 that turns from the empty marker (228) into the
trained unit's type id is the build-queue entry; the u8 that advances is the ring slot. Prints
the offsets to put in src/scr_profile.h.

    python tools/hunt_queue.py     # a live game with a train-able main building required
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from gary import commands as C  # noqa: E402
from gary.scr_env import ScrGame  # noqa: E402

MAINS = {C.COMMAND_CENTER: C.SCV, C.NEXUS: C.PROBE, C.HATCHERY: C.DRONE}


def main() -> None:
    game = ScrGame.connect()
    st = game.status()
    lp = st.get("local_player", -1)
    obs = game.observe()
    me = next(p for p in obs["players"] if p["slot"] == lp)
    main_b = next((u for u in obs["units"] if u["owner"] == lp and u["type"] in MAINS
                   and u["completed"]), None)
    if not main_b:
        raise SystemExit("no completed main building for the local player")
    want = MAINS[main_b["type"]]
    print(f"slot {lp} minerals={me['minerals']} main={main_b['tag']} type={main_b['type']} "
          f"train->{want}")

    before = game.probe_unit(main_b["tag"])
    game.act(lp, C.select([main_b["tag"]]))
    game.step(8)
    accepted = game.act(lp, C.train(want))
    game.step(12)  # past the act() latency so the queue entry is committed
    after = game.probe_unit(main_b["tag"])
    print(f"train accepted={accepted}")

    ws = int(before["window_start"])
    b = bytes.fromhex(before["window_hex"])
    a = bytes.fromhex(after["window_hex"])
    print(f"window [{ws}, {ws + len(b)}) diffs (offsets relative to the unit struct):")
    u16_hits, u8_hits = [], []
    for i in range(len(b)):
        if b[i] != a[i]:
            u8_hits.append(ws + i)
    for i in range(0, len(b) - 1, 2):
        bv = int.from_bytes(b[i:i + 2], "little")
        av = int.from_bytes(a[i:i + 2], "little")
        if bv != av:
            u16_hits.append((ws + i, bv, av))
            print(f"  u16 @ {ws + i}: {bv} -> {av}" +
                  ("   <-- queue entry (228 -> type)" if bv == 228 and av == want else ""))
    for off in u8_hits:
        print(f"  u8  @ {off}: {b[off - ws]} -> {a[off - ws]}")
    print()
    entries = [off for off, bv, av in u16_hits if av == want]
    print("candidate kUnitBuildQueue (u16 slots that filled with the unit type):", entries)
    print("candidate kUnitBuildSlot (changed u8s near those slots):",
          [o for o in u8_hits if entries and min(entries) - 8 <= o <= min(entries) + 12])
    print("after-state raw_queue:", after["raw_queue"], "build_slot:", after["raw_build_slot"])
    game.close()


if __name__ == "__main__":
    main()
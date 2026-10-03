#!/usr/bin/env python3
"""Cross-validate an observe() dump against the game's own units.dat.

    python adapters/scr_bridge/tools/check_observe.py [observe.json]

Checks that need no game: unit type ids are real types, hp never exceeds the DAT maximum,
player supply reads equal the sum of their units' supply costs, and mineral fields carry a
known resource amount. Any mismatch points at a specific struct offset in scr_profile.h.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen_unit_dat  # noqa: E402

REPO = HERE.parents[2]


def load_dat() -> dict[str, list[int]]:
    return gen_unit_dat.read_columns((REPO / "data" / "gamedata" / "scr" / "arr" / "units.dat").read_bytes())


def main() -> None:
    obs_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "build" / "observe.json"
    obs = json.loads(obs_path.read_text(encoding="utf-8"))
    dat = load_dat()
    hp = dat["hitpoints"]           # 24.8 fixed, like the unit struct
    shields = dat["shield_points"]  # 24.8 fixed
    sup_req = dat["supply_required"]  # half-supply units (zergling = 1)
    sup_prov = dat["supply_provided"]  # half-supply units

    problems = 0
    print(f"observe frame={obs['frame']} players={len(obs['players'])} units={len(obs['units'])}")

    # 1. every unit type must be a real type id, hp within the DAT maximum
    for u in obs["units"]:
        if not 0 <= u["type"] < 228:
            print(f"FAIL unit tag={u['tag']} type={u['type']} is not a unit type")
            problems += 1
            continue
        max_hp = hp[u["type"]] >> 8 if hp[u["type"]] > 1000 else hp[u["type"]]
        if u["hp"] > max_hp + 1:
            print(f"FAIL unit tag={u['tag']} type={u['type']} hp={u['hp']} > max {max_hp}")
            problems += 1
        max_sh = shields[u["type"]] >> 8 if shields[u["type"]] > 1000 else shields[u["type"]]
        if u["shields"] > max_sh + 1:
            print(f"FAIL unit tag={u['tag']} type={u['type']} shields={u['shields']} > max {max_sh}")
            problems += 1

    # 2. supply: used supply = live units' cost + queued units' reservation (BW reserves on
    # queue), so the read must lie between the completed-only sum and the "everything" sum.
    for p in obs["players"]:
        slot = p["slot"]
        units = [u for u in obs["units"] if u["owner"] == slot]
        completed = sum(sup_req[u["type"]] for u in units if u["completed"]) / 2
        everything = sum(sup_req[u["type"]] for u in units) / 2
        queued = 0.0
        for u in units:
            for _ in range(u["queue"]):
                queued += 1  # queue holds type ids; count conservatively below
        got = p["supply_used"]
        ok = completed - 0.5 <= got <= everything + queued + 0.5
        print(f"{'ok  ' if ok else 'FAIL'} player {slot} supply_used={got} "
              f"(visible units imply {completed:.1f}..{everything:.1f}, + up to {queued:.0f} queued)")
        if not ok:
            problems += 1
        # provided: sum over completed supply-providing units (depots/halls/overlords)
        prov = sum(sup_prov[u["type"]] for u in units if u["completed"]) / 2
        ok = abs(prov - p["supply_max"]) < 0.5
        print(f"{'ok  ' if ok else 'FAIL'} player {slot} supply_max={p['supply_max']} "
              f"(buildings imply {prov})")
        if not ok:
            problems += 1

    # 3. minerals: a fresh game's mineral fields hold 1500 or 2500
    minerals = [u for u in obs["units"] if u["type"] in (176, 177, 178)]
    bad = [u for u in minerals if u["resources"] not in (0, 1500, 2500)]
    fresh = [u for u in minerals if u["resources"] != 0]
    print(f"{'ok  ' if not bad else 'FAIL'} mineral fields: {len(minerals)} total, "
          f"{len(fresh)} with nonzero resources")
    if not fresh:
        print("     every mineral reads resources=0 at game start -> the kUnitResources offset "
              "is wrong (scr_profile.h); probe the surrounding bytes in-game to locate 1500/2500")
        problems += 1

    print()
    print("PASS" if problems == 0 else f"{problems} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Live SC:R probe: start a custom melee game vs one computer, then run this.

Answers, with evidence, every open question in the verification plan (README).
Reads only; the only writes go to build/probe_result.txt.

    python adapters/scr_bridge/tools/probe_live.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # adapters/scr_bridge/ (profile_facts)

from gary import commands as C  # noqa: E402
from gary.scr_env import ScrGame  # noqa: E402
from profile_facts import read_profile  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "build" / "probe_result.txt"

WORKERS = {C.SCV, C.DRONE, C.PROBE}
MAIN_BUILDINGS = {C.COMMAND_CENTER, C.NEXUS, C.HATCHERY}
PRODUCTION_BUILDINGS = {C.COMMAND_CENTER, C.NEXUS, C.HATCHERY, C.BARRACKS}

# Max shields per protoss type (openbw bwenums ids). The shields-offset hunt needs units whose
# shields are FULL, so it runs in the first seconds of a fresh game (nothing damaged yet).
PROTOSS_SHIELDS = {
    64: 20, 65: 60, 66: 80, 67: 40, 68: 40, 69: 25, 70: 80, 71: 100,
    72: 20, 73: 20, 74: 20, 75: 20, 76: 20, 78: 20, 80: 20, 81: 20,
    82: 20, 83: 20, 84: 20,
}


def hunt_shields(game: ScrGame, obs: dict) -> tuple[list[int], int]:
    """Find unit-struct offsets whose u32>>8 equals the type's full shields on every protoss
    unit seen. Returns (candidate offsets, units used)."""
    candidates: set[int] | None = None
    used = 0
    for u in obs["units"]:
        if u["type"] not in PROTOSS_SHIELDS:
            continue
        raw = game.probe_unit(u["tag"])
        if not raw:
            continue
        win = bytes.fromhex(raw.get("window_hex", ""))
        start = int(raw.get("window_start", 0))
        expect = PROTOSS_SHIELDS[u["type"]]
        hits = set()
        for o in range(start, start + max(0, len(win) - 3)):
            v = int.from_bytes(win[o - start: o - start + 4], "little") >> 8
            if v == expect:
                hits.add(o)
        candidates = hits if candidates is None else (candidates & hits)
        used += 1
        if candidates == set():
            break
    return sorted(candidates or []), used


def main() -> None:
    game = ScrGame.connect()
    lines: list[str] = []
    results: list[tuple[bool | None, str]] = []

    def say(s: str = "") -> None:
        print(s)
        lines.append(s)

    say("waiting for a game to start (Ctrl+C to stop)...")
    while True:
        st = game.status()
        if st.get("in_game"):
            break
        time.sleep(2)
    say("game detected!")
    say("status: " + json.dumps(st))
    results.append((st.get("hash_verified") is True, "1. hash_verified"))
    results.append((st.get("frame_watcher") is True, "1. frame_watcher (frames flowing)"))
    results.append((st.get("in_game") is True, "1. in_game"))
    results.append((st.get("latency_frames") is not None, "1. latency_frames reported"))
    results.append((st.get("frames", 0) > 0, "1. frames counter > 0 (commands can flush)"))

    time.sleep(1.5)  # let the game settle on the first frames
    obs = game.observe()
    say(f"observe: frame={obs['frame']} map={obs['map']} players={len(obs['players'])} "
        f"units={len(obs['units'])}")
    for p in obs["players"]:
        say(f"  player {p['slot']} {p['name']!r} race={p['race']} minerals={p['minerals']} "
            f"gas={p['gas']} supply={p['supply_used']}/{p['supply_max']}")
    results.append((len(obs["players"]) == 2,
                    f"2. exactly 2 players (got {len(obs['players'])})"))

    me = st.get("local_player", -1)
    mine = [u for u in obs["units"] if u["owner"] == me]
    workers = [u for u in mine if u["type"] in WORKERS]
    mains = [u for u in mine if u["type"] in MAIN_BUILDINGS]
    say(f"own units: {len(mine)} total, workers={len(workers)}, main buildings={len(mains)}")
    results.append((len(workers) >= 4, f"3. own workers >= 4 (got {len(workers)})"))
    results.append((len(mains) >= 1, f"3. own main building present (got {len(mains)})"))

    minerals = [u for u in obs["units"] if u["type"] == 176 and u["owner"] == 11]
    say(f"minerals visible: {len(minerals)}")
    checked = bad = positive = 0
    for u in minerals:
        raw = game.probe_unit(u["tag"])
        if not raw:
            continue
        amount = raw.get("raw_resources", -1)
        checked += 1
        if amount > 0:
            positive += 1
        say(f"  mineral tag={u['tag']} observe.resources={u['resources']} "
            f"probe.raw_resources={amount}")
        if checked == 1:
            say(f"    window_start={raw.get('window_start')} "
                f"window_hex={raw.get('window_hex', '')}")
        if amount != u["resources"]:
            bad += 1
        if checked >= 10:
            break
    say(f"minerals: {checked} probed, {bad} disagree, {positive} with amount > 0")
    # raw must agree with observe AND see real amounts: an all-zero read is the signature of a
    # wrong resources offset, and passes a naive {{0,1500,2500}} membership test.
    results.append((checked > 0 and bad == 0 and positive > 0,
                    f"4. probe raw_resources agrees with observe and reads real amounts "
                    f"({checked} checked, {bad} disagree, {positive} positive)"))

    cands, used = hunt_shields(game, obs)
    want = read_profile().get("UnitShields")
    say(f"shields hunt: candidates={cands} (from {used} protoss units); "
        f"profile kUnitShields={want}")
    if used and cands == [want]:
        results.append((True, f"5. shields offset confirmed: {cands[0]} == kUnitShields "
                              f"({used} protoss units agree)"))
    elif used and len(cands) == 1:
        say(f"  -> set kUnitShields = {cands[0]} in src/scr_profile.h and rebuild")
        results.append((False, f"5. shields offset found: {cands[0]} but profile says {want} — "
                               f"set kUnitShields in scr_profile.h and re-run"))
    elif used and len(cands) > 1:
        results.append((False, f"5. shields offset ambiguous: {cands} — inspect windows"))
    elif used:
        results.append((False, "5. shields offset not found — hunt needs full-shield protoss "
                               "units early in a fresh game"))
    else:
        results.append((None, "info 5. shields check skipped — no protoss units in this game "
                              "(the computer race is random; hunt needs full-shield protoss units)"))

    training = False
    for u in obs["units"]:
        if u["completed"] and u["type"] in PRODUCTION_BUILDINGS:
            raw = game.probe_unit(u["tag"])
            if raw and any(t != 228 and t != 0 for t in raw.get("raw_queue", [])):
                say(f"  training: tag={u['tag']} queue={raw.get('raw_queue')} "
                    f"build_slot={raw.get('raw_build_slot')}")
                training = True
                break
    results.append((True if training else None,
                    "6. training queue non-empty (observed)" if training
                    else "info 6. nothing training right now (skipped)"))

    f1 = obs["frame"]
    time.sleep(3)
    f2 = game.observe()["frame"]
    say(f"  frame {f1} -> {f2} in ~3s")
    results.append((f2 > f1, f"8. frame counter advances ({f1} -> {f2})"))

    say()
    for ok, label in results:
        say(f"{'info' if ok is None else ('PASS' if ok else 'FAIL')} {label}")
    failed = sum(1 for ok, _ in results if ok is False)
    say()
    say(f"{failed} check(s) need attention." if failed else
        "All checks that could run passed.")
    say("Remaining: checklist item 7 (act() a select; verify 0x63 in the saved replay) — run")
    say("tools/item7_act.py, then end the game and check LastReplay.rep with tools/bin/screp.exe.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

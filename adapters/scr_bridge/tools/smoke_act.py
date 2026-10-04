#!/usr/bin/env python3
"""Live smoke: move / train / build through act(), and measure act()->effect latency.

For each of the three core command types this builds the replay-format packet and sends it with
game.act() -- the same command path gary/interface.py uses on the live SC:R client (via
adapters/scr_bridge). It then polls observe() every frame until the command's effect appears and
records the frame delta (act -> effect): that is the act() latency the human interface must model.
The measured value is compared with the adapter's reported latency_frames and printed as the
calibration to feed gary.interface.HumanInterface.calibrate_act_latency().

    python adapters/scr_bridge/tools/smoke_act.py              # live (a game must be running)
    python adapters/scr_bridge/tools/smoke_act.py --selftest   # headless on OpenBW, no game

The smoke adapts to the local player's race (melee assigns a random one): it trains/morphs that
race's worker and builds its supply building. move/train/build are all sent through act(); command
acceptance is reported even when a building is not affordable or is race-inapplicable (the packet
still proves the command path). The latency number is the earliest observed effect (the command
processing delay); later stages (e.g. a building finishing) don't inflate it.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from gary import commands as C  # noqa: E402

# race -> (worker type, supply building type, placement order). The smoke adapts to whichever race
# the local player is (melee assigns a random race; Gary v0.1 itself plays Terran).
RACE_OF_MAIN = {C.COMMAND_CENTER: "T", C.NEXUS: "P", C.HATCHERY: "Z"}
WORKER_OF = {"T": C.SCV, "P": C.PROBE, "Z": C.DRONE}
SUPPLY_OF = {"T": (C.SUPPLY_DEPOT, C.ORDER_PLACE_BUILDING),
             "P": (C.PYLON, C.ORDER_PLACE_PROTOSS_BUILDING),
             "Z": (None, 0)}


def measure(game, slot: int, packet: bytes, detect, max_wait: int = 48):
    """act() `packet`, then advance one frame at a time until detect(obs) is true.

    Returns (accepted, latency_frames_or_None). latency is measured from the act() call to the
    first observe() that shows the effect.
    """
    send_frame = game.observe()["frame"]
    accepted = game.act(slot, packet)
    for _ in range(max_wait):
        game.step(1)
        obs = game.observe()
        if detect(obs):
            return accepted, obs["frame"] - send_frame
    return accepted, None


def _unit(obs: dict, tag: int) -> dict | None:
    return next((u for u in obs["units"] if u["tag"] == tag), None)


def _settle(game, frames: int) -> None:
    """Let a prior select() land before the command we actually measure."""
    game.step(frames)


def _minerals(game, slot: int) -> int:
    return next(p for p in game.observe()["players"] if p["slot"] == slot)["minerals"]


def _count_workers(game, slot: int) -> int:
    return sum(1 for u in game.observe()["units"]
               if u["owner"] == slot and u["type"] in (C.SCV, C.DRONE, C.PROBE))


def _cc_training(game, tag: int) -> bool:
    """True if the building is training. On the live client observe()'s `queue` field does not
    reflect the training queue (the bridge reads it via probe_unit's raw_queue instead)."""
    if not hasattr(game, "probe_unit"):
        return False
    raw = game.probe_unit(tag) or {}
    return any(t not in (0, 228) for t in raw.get("raw_queue", []))


def _prime_minerals(game, slot: int, target: int, max_frames: int = 2400) -> bool:
    """Send the starting workers mining and wait until the player can afford a building.

    Used by --selftest so the build command's effect can actually be timed (a fresh game starts
    with only 50 minerals; a Supply Depot costs 100). Returns True once the target is reached.
    """
    obs = game.observe()
    mine = [u for u in obs["units"] if u["owner"] == slot]
    workers = [u for u in mine if u["type"] in (C.SCV, C.DRONE, C.PROBE)]
    fields = [u for u in obs["units"] if u["type"] in C.MINERAL_FIELDS]
    if not workers or not fields:
        return False
    w0 = workers[0]
    field = min(fields, key=lambda m: math.dist((m["x"], m["y"]), (w0["x"], w0["y"])))
    game.act(slot, C.select([w["tag"] for w in workers[:12]]))
    game.step(4)
    game.act(slot, C.right_click(field["x"], field["y"], field["tag"], field["type"]))  # gather
    for _ in range(max_frames):
        game.step(1)
        if _minerals(game, slot) >= target:
            return True
    return _minerals(game, slot) >= target


def smoke_move(game, slot: int, worker: dict, settle: int = 8) -> dict:
    """Right-click the ground near a worker; the effect is its order (or position) changing."""
    tx, ty = worker["x"] + 96, worker["y"]
    game.act(slot, C.select([worker["tag"]]))
    _settle(game, settle)
    base = _unit(game.observe(), worker["tag"]) or worker
    x0, y0, order0 = base["x"], base["y"], base["order"]

    def detect(obs):
        u = _unit(obs, worker["tag"])
        return bool(u and (u["order"] != order0 or abs(u["x"] - x0) + abs(u["y"] - y0) > 6))

    accepted, latency = measure(game, slot, C.right_click(tx, ty), detect)
    return {"name": "move", "accepted": accepted, "latency_frames": latency,
            "detail": f"SCV {worker['tag']} -> ({tx},{ty})"}


def smoke_train(game, slot: int, main: dict, race: str, worker_type: int, settle: int = 8) -> dict:
    """Train a worker from the main building. Effect: its queue goes up (Terran/Protoss), or a
    larva morphs into an egg (Zerg)."""
    if race == "Z":
        return _smoke_morph(game, slot, worker_type, settle)
    game.act(slot, C.select([main["tag"]]))
    _settle(game, settle)
    base = _unit(game.observe(), main["tag"]) or main
    q0 = base.get("queue", 0)
    n0 = _count_workers(game, slot)

    def detect(obs):
        u = _unit(obs, main["tag"])
        return bool(u and (u.get("queue", 0) > q0 or _cc_training(game, main["tag"])))

    accepted, latency = measure(game, slot, C.train(worker_type), detect)
    detail = f"main {main['tag']} queue {q0}->{worker_type}"
    if latency is not None:
        return {"name": "train", "accepted": accepted, "latency_frames": latency, "detail": detail}
    # The live observe reads the training queue from an UNVERIFIED offset (scr_profile.h
    # kUnitBuildQueue), so it can stay empty while training runs. Confirm execution by waiting for a
    # new worker to appear (build time); report no latency, since build time != act() latency.
    for _ in range(600):
        game.step(1)
        if _count_workers(game, slot) > n0:
            return {"name": "train", "accepted": accepted, "latency_frames": None,
                    "detail": detail + " (executed: worker produced; queue offset unverified on live)"}
    return {"name": "train", "accepted": accepted, "latency_frames": None,
            "detail": detail + " (accepted; no worker appeared in time)"}


def _smoke_morph(game, slot: int, unit_type: int, settle: int = 8) -> dict:
    """Zerg: morph a larva into unit_type. Effect: the larva count drops / an egg appears."""
    obs = game.observe()
    larva = next((u for u in obs["units"] if u["owner"] == slot and u["type"] == C.LARVA), None)
    if not larva:
        return {"name": "train", "accepted": False, "latency_frames": None, "detail": "no larva"}
    n0 = sum(1 for u in game.observe()["units"] if u["owner"] == slot and u["type"] == C.LARVA)
    game.act(slot, C.select([larva["tag"]]))
    _settle(game, settle)

    def detect(o):
        n = sum(1 for u in o["units"] if u["owner"] == slot and u["type"] == C.LARVA)
        return n < n0

    accepted, latency = measure(game, slot, C.morph(unit_type), detect)
    return {"name": "train", "accepted": accepted, "latency_frames": latency,
            "detail": f"larva {larva['tag']} morph->{unit_type}"}
def _find_build_spot(game, slot: int, builder: int, unit_type: int, near: tuple[int, int]) -> tuple[int, int] | None:
    for r in range(0, 12):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                tx, ty = near[0] // 32 + dx, near[1] // 32 + dy
                if tx < 0 or ty < 0:
                    continue
                if game.can_place(slot, unit_type, tx, ty, builder):
                    return tx, ty
    return None


def smoke_build(game, slot: int, worker: dict, race: str, supply_type: int, order: int,
                settle: int = 8) -> dict:
    """Order a worker to build the race's supply building; effect: its order changing / it appears.

    The build packet is always sent (it proves the 0x0c command path through act()), but the effect
    is only timed when the player can actually afford it -- otherwise the game discards the order and
    any "effect" would be a spurious change that would pollute the latency measurement.
    """
    if supply_type is None:   # Zerg supply is an Overlord (a unit), not a building
        return {"name": "build", "accepted": False, "latency_frames": None,
                "detail": "Zerg supply is an Overlord (morph), not a building -- build skipped"}
    minerals = next(p for p in game.observe()["players"] if p["slot"] == slot)["minerals"]
    spot = _find_build_spot(game, slot, worker["tag"], supply_type, (worker["x"], worker["y"]))
    if spot is None:
        return {"name": "build", "accepted": False, "latency_frames": None,
                "detail": f"no free spot for unit {supply_type} near the worker"}
    tx, ty = spot
    game.act(slot, C.select([worker["tag"]]))
    _settle(game, settle)
    base = _unit(game.observe(), worker["tag"]) or worker
    order0 = base["order"]
    if minerals < 100:
        accepted = game.act(slot, C.build(supply_type, tx, ty, order))
        return {"name": "build", "accepted": accepted, "latency_frames": None,
                "detail": f"unit {supply_type} at tile ({tx},{ty}) (command path "
                          f"{'ok' if accepted else 'REJECTED'}; effect not timed: "
                          f"needs 100 minerals, has {minerals})"}

    def detect(obs):
        if any(u["type"] == supply_type and abs(u["x"] - (tx * 32 + 48)) < 96
               and abs(u["y"] - (ty * 32 + 32)) < 96 for u in obs["units"]):
            return True
        u = _unit(obs, worker["tag"])
        return bool(u and u["order"] != order0)

    accepted, latency = measure(game, slot, C.build(supply_type, tx, ty, order), detect)
    return {"name": "build", "accepted": accepted, "latency_frames": latency,
            "detail": f"unit {supply_type} at tile ({tx},{ty})"}


def run_smoke(game, slot: int, reported_latency) -> list[dict]:
    """Run move/train/build and print a latency-calibration summary. Returns the results."""
    obs = game.observe()
    me = next((p for p in obs["players"] if p["slot"] == slot), None)
    mine = [u for u in obs["units"] if u["owner"] == slot]
    worker = next((u for u in mine if u["type"] in (C.SCV, C.DRONE, C.PROBE) and u["completed"]), None)
    main = next((u for u in mine if u["type"] in (C.COMMAND_CENTER, C.NEXUS, C.HATCHERY)
                 and u["completed"]), None)
    if not worker or not main:
        raise SystemExit("need one worker and one main building owned by the local player")
    race = RACE_OF_MAIN.get(main["type"], "T")
    worker_type = WORKER_OF[race]
    supply_type, build_order = SUPPLY_OF[race]

    print(f"local player slot {slot} ({me['name'] if me else '?'}, race {race}), "
          f"frame {obs['frame']}, reported latency_frames={reported_latency}")
    if _minerals(game, slot) < 160:
        print("  sending workers to mine so train() and build() are affordable...")
        _prime_minerals(game, slot, 160, max_frames=1200)
    results = [smoke_move(game, slot, worker),
               smoke_train(game, slot, main, race, worker_type),
               smoke_build(game, slot, worker, race, supply_type, build_order)]

    print()
    for r in results:
        lat = f"{r['latency_frames']} frames" if r["latency_frames"] is not None else "not measured"
        ok = "accepted" if r["accepted"] else ("skipped" if "skip" in r["detail"] else "REJECTED")
        print(f"  {r['name']:<5} {ok:<8} effect={lat:<12} {r['detail']}")

    measured = sorted(r["latency_frames"] for r in results if r["latency_frames"] is not None)
    print()
    if measured:
        # act() latency is the command-PROCESSING delay: the earliest frame at which the game
        # reflects the command (an order/queue change). Later stages (e.g. a depot finishing its
        # placement after the worker walks) are effects completing, not the latency to model -- so
        # take the minimum, which is robust to those late observations.
        cal = measured[0]
        print(f"act()->effect latency: earliest effect {cal} frame(s) "
              f"(all measurements {measured}) -> calibrate_act_latency({cal})")
        if reported_latency is not None:
            print(f"adapter reported latency_frames={reported_latency} (+1 queue hand-off = "
                  f"{int(reported_latency) + 1}); measured {cal}")
    else:
        print("no effect was observed in time; act() latency not measured "
              "(commands were still accepted)")
    return results


def selftest() -> int:
    """Run the identical smoke against headless OpenBW (no live client needed)."""
    from gary.env import Game
    map_path = REPO / "tests" / "fixtures" / "replays" / "stardata_tvz_standard_ozp3w.rep"
    print(f"selftest on OpenBW: {map_path.name}")
    with Game.new(map_path, ["T", "Z"], ["smoke (T)", "idle (Z)"], seed=1) as game:
        obs = game.observe()
        slot = next(u["owner"] for u in obs["units"] if u["type"] == C.COMMAND_CENTER)
        results = run_smoke(game, slot, reported_latency=None)
    ok = all(r["accepted"] for r in results) and any(r["latency_frames"] is not None for r in results)
    print()
    print("selftest:", "PASS (commands accepted, latency measured)" if ok
          else "CHECK (some effect not observed)")
    return 0 if ok else 1


def live(pipe: str) -> int:
    from gary.scr_env import ScrGame
    game = ScrGame.connect(pipe)
    try:
        st = game.status()
        slot = st.get("local_player", -1)
        if slot < 0 or not st.get("in_game"):
            raise SystemExit("no live game in progress (start one, or use --selftest)")
        run_smoke(game, slot, st.get("latency_frames"))
        return 0
    finally:
        game.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true", help="run headless on OpenBW instead of live")
    ap.add_argument("--pipe", default=r"\\.\pipe\gary_scr", help="bridge named pipe (live)")
    args = ap.parse_args()
    if args.selftest:
        raise SystemExit(selftest())
    raise SystemExit(live(args.pipe))


if __name__ == "__main__":
    main()

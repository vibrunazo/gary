#!/usr/bin/env python3
"""One command for the whole loop: launch SC:R, inject the bridge, start a melee game, probe it.

    python adapters/scr_bridge/tools/run_match.py
    python adapters/scr_bridge/tools/run_match.py --calibrate   # screenshot the menus, no clicks

End state: a live custom melee game vs one computer with the bridge attached and the probe
checklist run. For checklist item 7 afterwards: tools/item7_act.py, then end the game and check
LastReplay.rep with tools/bin/screp.exe.

If the game is already running with an old bridge build (status without "frame_watcher"), it is
killed and relaunched so the new DLL loads — unless a match is in progress, which is never
interrupted.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from gary.scr_env import ScrGame  # noqa: E402
from auto_game import find_process  # noqa: E402


def bridge_status() -> dict | None:
    try:
        return ScrGame.connect().status()
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true",
                    help="pass through to auto_game: screenshot the menus, click nothing")
    ap.add_argument("--no-probe", action="store_true", help="stop after the game is running")
    args = ap.parse_args()

    st = bridge_status()
    if st is not None and "frame_watcher" not in st:
        if st.get("in_game"):
            raise SystemExit(
                "an old bridge build is attached to a LIVE game — end the match first, "
                "then re-run")
        print("old bridge build detected — restarting the game to load the new DLL...")
        subprocess.run(["taskkill", "/IM", "StarCraft.exe", "/F"], capture_output=True)
        for _ in range(10):  # wait for the process to die so the DLL file unlocks
            time.sleep(1)
            if not find_process("StarCraft"):
                break
        st = None

    # (Re)build the bridge — a locked gary_scr.dll means a game still has it loaded.
    print("building the bridge (build.bat)...")
    build = subprocess.run([str(TOOLS.parent / "build.bat")], capture_output=True, text=True,
                           shell=True)
    if build.returncode != 0:
        print(build.stdout[-2000:])
        print(build.stderr[-2000:])
        raise SystemExit("build failed — if gary_scr.dll is locked, a game still has it loaded")

    if st is None:
        print("bridge not reachable — launching and injecting (launch.py)...")
        subprocess.run([sys.executable, str(TOOLS.parent / "launch.py")], check=False)
        for _ in range(20):
            time.sleep(1)
            st = bridge_status()
            if st is not None:
                break
        if st is None:
            raise SystemExit("bridge still not reachable after launch.py")

    if st.get("in_game"):
        print("game already running — not touching it")
    else:
        print("starting a melee game via the menus (auto_game.py)...")
        cmd = [sys.executable, str(TOOLS / "auto_game.py")]
        if args.calibrate:
            cmd.append("--calibrate")
        subprocess.run(cmd, check=False)

    if args.calibrate or args.no_probe:
        return

    print("running the live probe (probe_live.py)...")
    subprocess.run([sys.executable, str(TOOLS / "probe_live.py")], check=False)
    print()
    print("Item 7: python adapters/scr_bridge/tools/item7_act.py, then")
    print("python adapters/scr_bridge/tools/end_match.py ends the match and prints the replay")
    print("path; verify the 0x63 select with D:\\docs\\ai\\bw\\tools\\bin\\screp.exe -cmds.")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Checklist item 7: send one select command as the local player (the bridge's command path).

Changes the player's selection to one of their own units — nothing else. Afterwards the game's
auto-saved replay (Documents\\StarCraft\\Maps\\Replays\\LastReplay.rep) must contain a 0x63
select for our player; verify with: tools\\bin\\screp.exe <replay>.

    python adapters/scr_bridge/tools/item7_act.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from gary import commands as C  # noqa: E402
from gary.scr_env import ScrGame  # noqa: E402


def main() -> None:
    game = ScrGame.connect()
    st = game.status()
    me = st.get("local_player", -1)
    obs = game.observe()
    mine = [u for u in obs["units"] if u["owner"] == me and u["completed"]]
    if not mine:
        raise SystemExit("no own unit to select")
    tag = mine[0]["tag"]
    packet = C.select([tag])
    ok = game.act(me, packet)
    print(f"act(select tag={tag}) -> {'accepted' if ok else 'REJECTED'}")
    print(f"command bytes: {packet.hex()}")
    print("submitted packets are logged in build/logs/scr_bridge.log (packet_hex, submitted)")
    print()
    print("When this game ends, verify the replay contains 0x63 for our player:")
    print(r"  tools\bin\screp.exe \"<Documents>\StarCraft\Maps\Replays\LastReplay.rep\"")


if __name__ == "__main__":
    main()

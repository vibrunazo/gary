"""ScrGame: Gary's game-surface on a live StarCraft: Remastered client (adapters/scr_bridge).

Same methods as gary.env.Game, so gary/interface.py and the bots run unchanged:

    from gary.scr_env import ScrGame
    game = ScrGame.connect()               # attach to the gary_scr pipe (launch.py started it)
    obs = game.observe()                   # same JSON shape as gary.env.Game.observe()
    game.act(game_slot, C.select([tag]))   # replay-format bytes, exactly like gary.env.Game
    game.step(8)                           # waits for the live game to advance 8 frames

Differences from gary.env.Game (see adapters/scr_bridge/README.md "Known gaps"):
- act() only accepts the local player's slot: a live client can only act as itself.
- step() waits instead of simulating; the game runs at its own speed.
- set_name()/save_replay() are not applicable: the client writes its own replay.
"""

from __future__ import annotations

import json
from pathlib import Path

from gary.env import GameError  # same error type as the OpenBW backend

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PIPE = r"\\.\pipe\gary_scr"


class ScrGame:
    """A game in progress inside a live Remastered client (one client = one local player)."""

    def __init__(self, pipe):
        self._pipe = pipe
        self._next_id = 1

    @classmethod
    def connect(cls, pipe: str = DEFAULT_PIPE) -> "ScrGame":
        try:
            f = open(pipe, "r+b", buffering=0)
        except OSError as e:
            raise GameError(
                f"can't open {pipe}: {e} (is the client running with the bridge? "
                f"python adapters/scr_bridge/launch.py)"
            ) from e
        return cls(f)

    # -- protocol -------------------------------------------------------------------------

    def _call(self, method: str, **args):
        request = {"id": self._next_id, "method": method, "args": args}
        self._next_id += 1
        try:
            line = json.dumps(request, separators=(",", ":")) + "\n"
            self._pipe.write(line.encode("utf-8"))
            line = self._pipe.readline()
        except OSError as e:
            raise GameError(f"bridge connection lost: {e}") from e
        if not line:
            raise GameError("bridge closed the connection")
        response = json.loads(line.decode("utf-8"))
        if not response.get("ok"):
            raise GameError(response.get("error", "bridge error"))
        return response.get("result")

    def status(self) -> dict:
        """Adapter health: build, hash verification, frames, latency estimate."""
        return self._call("status")

    def ping(self) -> str:
        return self._call("ping")

    # -- gary.env.Game surface ------------------------------------------------------------

    def observe(self) -> dict:
        return self._call("observe")

    def act(self, slot: int, command: bytes) -> bool:
        """One command for a player slot (replay-format bytes). True if the engine took it."""
        return self._call("act", slot=slot, hex=command.hex()) == 1

    def step(self, frames: int = 1) -> None:
        """Wait until the live game has advanced this many frames."""
        self._call("step", frames=frames)

    def unit_at(self, slot: int, x: int, y: int) -> int:
        return self._call("unit_at", slot=slot, x=x, y=y)

    def box_select(self, slot: int, x0: int, y0: int, x1: int, y1: int) -> list[int]:
        return self._call("box_select", slot=slot, x0=x0, y0=y0, x1=x1, y1=y1)

    def unit_type_of(self, tag: int) -> int:
        return self._call("unit_type", tag=tag)

    def can_place(self, slot: int, unit_type: int, tile_x: int, tile_y: int,
                  builder_tag: int = 0) -> bool:
        return self._call("can_place", slot=slot, builder=builder_tag, unit_type=unit_type,
                          tile_x=tile_x, tile_y=tile_y) == 1

    def depot_spot_ok(self, tile_x: int, tile_y: int) -> bool:
        return self._call("depot_spot_ok", tile_x=tile_x, tile_y=tile_y) == 1

    def tile_flags(self, tile_x: int, tile_y: int) -> int:
        """Raw per-tile flags word (-1 if unresolved/out of range): for pinning flag bits."""
        return self._call("tile_flags", tile_x=tile_x, tile_y=tile_y)

    def start_locations(self) -> list[dict]:
        return self._call("start_locations")

    def probe_unit(self, tag: int) -> dict:
        """Raw values at the probe offsets (adapters/scr_bridge/README.md verification step 3)."""
        return self._call("probe_unit", tag=tag)

    def set_name(self, slot: int, name: str) -> None:
        raise GameError("not applicable on a live client: the account name is the player name")

    def save_replay(self, path: str | Path) -> None:
        raise GameError(
            "not applicable on a live client: the game saves its own replay under "
            "Documents\\StarCraft\\Maps\\Replays"
        )

    def close(self) -> None:
        """Detach from the bridge. The bridge keeps serving for the client's lifetime; use
        shutdown() to stop it deliberately."""
        if self._pipe:
            try:
                self._pipe.close()
            except OSError:
                pass
            self._pipe = None

    def shutdown(self) -> None:
        """Stop the bridge server (the game keeps running)."""
        try:
            self._call("shutdown")
        finally:
            self.close()

    def __enter__(self) -> "ScrGame":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

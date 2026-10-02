"""Python access to a headless Brood War game (env/gary_env.dll, built on OpenBW).

    from gary.env import Game
    game = Game.from_replay_map("tests/fixtures/replays/stardata_tvz_standard_ozp3w.rep")
    obs = game.observe()                  # full state as a dict
    game.act(slot, commands.select([tag]))
    game.step(8)
    game.save_replay("out.rep")

This is the raw game: full information, no limits. Gary goes through gary.interface.HumanInterface,
which adds fog of war, the camera, mouse travel and the APM budget (docs/ARCHITECTURE.md §6.3).
"""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dll() -> ctypes.CDLL:
    path = REPO_ROOT / "env" / "build" / ("gary_env.dll" if os.name == "nt" else "libgary_env.so")
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run env/build.bat")
    dll = ctypes.CDLL(str(path))
    dll.gary_env_create.restype = ctypes.c_void_p
    dll.gary_env_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    dll.gary_env_error.restype = ctypes.c_char_p
    dll.gary_env_error.argtypes = [ctypes.c_void_p]
    dll.gary_env_destroy.argtypes = [ctypes.c_void_p]
    dll.gary_env_step.restype = ctypes.c_bool
    dll.gary_env_step.argtypes = [ctypes.c_void_p, ctypes.c_int]
    dll.gary_env_act.restype = ctypes.c_int
    dll.gary_env_act.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    dll.gary_env_observe.restype = ctypes.c_char_p
    dll.gary_env_observe.argtypes = [ctypes.c_void_p]
    dll.gary_env_save_replay.restype = ctypes.c_bool
    dll.gary_env_save_replay.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    dll.gary_env_unit_at.restype = ctypes.c_uint
    dll.gary_env_unit_at.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    dll.gary_env_box_select.restype = ctypes.c_int
    dll.gary_env_box_select.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_uint), ctypes.c_int]
    dll.gary_env_unit_type.restype = ctypes.c_int
    dll.gary_env_unit_type.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    dll.gary_env_set_name.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
    return dll


_dll: ctypes.CDLL | None = None


def _gamedata_dir() -> Path:
    return Path(os.environ.get("GARY_DATA", REPO_ROOT / "data")) / "gamedata" / "scr"


class GameError(RuntimeError):
    pass


class Game:
    def __init__(self, handle: int):
        self._h = handle

    @classmethod
    def from_replay_map(cls, replay: str | Path, gamedata: str | Path | None = None) -> "Game":
        """A new game on a (pre-1.18 format) replay's map, with its players and races.
        The replay's own commands are not played."""
        global _dll
        _dll = _dll or _load_dll()
        h = _dll.gary_env_create(str(gamedata or _gamedata_dir()).encode(), str(replay).encode())
        if not h:
            raise GameError(_dll.gary_env_error(None).decode(errors="replace"))
        return cls(h)

    def _check(self, ok: bool) -> None:
        if not ok:
            raise GameError(_dll.gary_env_error(self._h).decode(errors="replace"))

    def step(self, frames: int = 1) -> None:
        self._check(_dll.gary_env_step(self._h, frames))

    def act(self, slot: int, command: bytes) -> bool:
        """Run one command for a player slot. True if the engine accepted it."""
        r = _dll.gary_env_act(self._h, slot, command, len(command))
        self._check(r >= 0)
        return r == 1

    def observe(self) -> dict:
        return json.loads(_dll.gary_env_observe(self._h).decode("utf-8", errors="replace"))

    def unit_at(self, slot: int, x: int, y: int) -> int:
        """Tag of the unit a click by this player at map pixel (x, y) would hit, or 0."""
        return _dll.gary_env_unit_at(self._h, slot, x, y)

    def box_select(self, slot: int, x0: int, y0: int, x1: int, y1: int) -> list[int]:
        """Tags a drag box (map pixels) would select for this player (up to 12)."""
        out = (ctypes.c_uint * 12)()
        n = _dll.gary_env_box_select(self._h, slot, x0, y0, x1, y1, out, 12)
        return list(out[:n])

    def unit_type_of(self, tag: int) -> int:
        return _dll.gary_env_unit_type(self._h, tag)

    def set_name(self, slot: int, name: str) -> None:
        """Rename a player (also in replays saved from this game)."""
        _dll.gary_env_set_name(self._h, slot, name.encode()[:24])

    def save_replay(self, path: str | Path) -> None:
        self._check(_dll.gary_env_save_replay(self._h, str(path).encode()))

    def close(self) -> None:
        if self._h:
            _dll.gary_env_destroy(self._h)
            self._h = None

    def __enter__(self) -> "Game":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

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

The map's static knowledge (terrain(), regions(), walkable(), creep(), unit_type_info(), and map_path: the map's
hash for the models) isn't read from the client: the live map is found among the map files Gary has (find_map: by
its size and mineral fields) and opened headless beside the live game (a shadow gary.env.Game, never stepped), so a
live Gary reads the same map as a headless one. On a map with no file these attributes are missing, as the layers
that ask for them expect of a game that can't tell (getattr(game, "terrain", None)).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from gary.env import GameError  # same error type as the OpenBW backend

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PIPE = r"\\.\pipe\gary_scr"
MINERALS = (176, 177, 178)
MINED_OUT = 0.5                # a live game's mineral fields are this share of the map file's at least (the rest mined out)
SHADOWED = ("terrain", "regions", "walkable", "creep", "unit_type_info")   # answered by the map's file, opened headless
UNIT_DEFAULTS = {"stim": 0, "ammo": 0, "ammo_max": 0}   # gary_env's unit fields an older bridge build doesn't send
TANKS = (5, 30)                # the Siege Tank's two modes: one type to a ctrl+click


def known_maps() -> list[Path]:
    """The map files a live game's map is looked for in: the ladder maps (ingest/ladder_maps.py), the tests' fixtures,
    and GARY_LIVE_MAPS (files or folders, os.pathsep between them)."""
    root = Path(os.environ.get("GARY_DATA", REPO_ROOT / "data"))
    found = sorted((root / "maps" / "ladder").glob("*.rep"))
    found += sorted((REPO_ROOT / "tests" / "fixtures" / "replays").glob("*.rep"))
    for entry in filter(None, os.environ.get("GARY_LIVE_MAPS", "").split(os.pathsep)):
        e = Path(entry)
        found += sorted(q for q in e.iterdir() if q.suffix.lower() in (".rep", ".scm", ".scx")) if e.is_dir() else [e]
    return found


def map_signature(obs: dict) -> dict:
    """What tells a map from another in an observation: its size and where its mineral fields are."""
    return {"size": [obs["map"]["w"], obs["map"]["h"]],
            "minerals": sorted([u["x"], u["y"]] for u in obs["units"] if u["type"] in MINERALS)}


def file_signature(path: Path) -> dict | None:
    """A map file's signature, kept in data/interim/maps/live_signatures.json (by path, size and time written)."""
    from gary.env import Game
    root = Path(os.environ.get("GARY_DATA", REPO_ROOT / "data"))
    cache = root / "interim" / "maps" / "live_signatures.json"
    known = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    st = path.stat()
    key, stamp = str(path.resolve()), [st.st_size, int(st.st_mtime)]
    if known.get(key, {}).get("stamp") != stamp:
        try:
            with Game.new(path, ["T", "P"], seed=0) as g:
                known[key] = {"stamp": stamp, **map_signature(g.observe())}
        except Exception:
            known[key] = {"stamp": stamp, "size": None, "minerals": []}    # (not a map Gary's engine opens)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(known), encoding="utf-8")
    return known[key] if known[key]["size"] else None


def find_map(obs: dict, candidates: list[Path] | None = None) -> Path | None:
    """The file of the map this observation is of: the same size, every mineral field the observation has where the
    file has one, and most of the file's still there (fields mine out). Of two versions with the same fields (a
    map's 1.3 and 1.4), the last by name."""
    live = map_signature(obs)
    fields = {tuple(m) for m in live["minerals"]}
    matches = []
    for path in (known_maps() if candidates is None else candidates):
        sig = file_signature(Path(path))
        if sig is None or sig["size"] != live["size"]:
            continue
        theirs = {tuple(m) for m in sig["minerals"]}
        if fields and fields <= theirs and len(fields) >= MINED_OUT * len(theirs):
            matches.append(Path(path))
    return max(matches, key=lambda q: q.name) if matches else None


class ScrGame:
    """A game in progress inside a live Remastered client (one client = one local player)."""

    def __init__(self, pipe, map_file: str | Path | None = None):
        self._pipe = pipe
        self._next_id = 1
        self._map_file = Path(map_file) if map_file else None    # the live map's file, given or found (map_path)
        self._map_looked = map_file is not None
        self._shadow = None                                      # that file opened headless: the map's static knowledge
        self._buildings = None                                   # every race's building types (type_select)

    @classmethod
    def connect(cls, pipe: str = DEFAULT_PIPE, map_file: str | Path | None = None) -> "ScrGame":
        """map_file: the live map's file, when the caller knows it (otherwise found among known_maps())."""
        try:
            f = open(pipe, "r+b", buffering=0)
        except OSError as e:
            raise GameError(
                f"can't open {pipe}: {e} (is the client running with the bridge? "
                f"python adapters/scr_bridge/launch.py)"
            ) from e
        return cls(f, map_file)

    # -- the map's file -------------------------------------------------------------------

    @property
    def map_path(self) -> Path | None:
        """The live map's file (gary/mapinfo.py reads the map's hash from it), looked for once, in a game; None when
        no file Gary has is this map."""
        if not self._map_looked:
            self._map_looked = True
            self._map_file = find_map(self._call("observe"))
        return self._map_file

    def _map_shadow(self):
        if self._shadow is None and self.map_path is not None:
            from gary.env import Game
            self._shadow = Game.new(self.map_path, ["T", "P"], seed=0)     # (no Zerg: creep() is the map's own)
        return self._shadow

    def __getattr__(self, name: str):
        # (only reached for what the class doesn't define: the shadow's methods, where there is a shadow)
        if name in SHADOWED:
            shadow = self._map_shadow()
            if shadow is not None:
                return getattr(shadow, name)
        raise AttributeError(name)

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
        obs = self._call("observe")
        units = obs["units"]
        if units and "ammo" not in units[0]:        # (a bridge built before these fields: adapters/scr_bridge/README.md)
            for u in units:
                for k, v in UNIT_DEFAULTS.items():
                    u.setdefault(k, v)
        return obs

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

    def type_select(self, slot: int, x: int, y: int, view: tuple[int, int, int, int]) -> list[int]:
        """What a ctrl+click (or double-click) selects, as gary.env.Game.type_select: the clicked unit's type among the
        player's units in the view rectangle, up to 12, left to right (the unit finder's order); a tank in either
        mode. Empty when the click hits no own unit selected with others (a building: a plain click)."""
        if self._buildings is None:
            from gary.race import Race
            self._buildings = {t for letter in "TZP" for t in Race.of(letter).sizes}
        tag = self.unit_at(slot, x, y)
        units = self._call("observe")["units"] if tag else []
        clicked = next((u for u in units if u["tag"] == tag), None)
        if clicked is None or clicked["owner"] != slot or clicked["type"] in self._buildings:
            return []
        same = lambda t: t == clicked["type"] or (t in TANKS and clicked["type"] in TANKS)
        x0, y0, x1, y1 = view
        inside = [u for u in units if u["owner"] == slot and same(u["type"]) and x0 <= u["x"] <= x1 and y0 <= u["y"] <= y1]
        return [u["tag"] for u in sorted(inside, key=lambda u: (u["x"], u["y"]))][:12]

    def can_place(self, slot: int, unit_type: int, tile_x: int, tile_y: int,
                  builder_tag: int = 0) -> bool:
        return self._call("can_place", slot=slot, builder=builder_tag, unit_type=unit_type,
                          tile_x=tile_x, tile_y=tile_y) == 1

    def depot_spot_ok(self, tile_x: int, tile_y: int) -> bool:
        return self._call("depot_spot_ok", tile_x=tile_x, tile_y=tile_y) == 1

    def tile_flags(self, tile_x: int, tile_y: int) -> int:
        """Raw per-tile flags word (-1 if unresolved/out of range): for pinning flag bits."""
        return self._call("tile_flags", tile_x=tile_x, tile_y=tile_y)

    def peek(self, addr: int, length: int) -> bytes:
        """Bounded raw-memory read (1..512 bytes): for pinning struct offsets by measurement."""
        return bytes.fromhex(self._call("peek", addr=addr, length=length))

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
        if self.__dict__.get("_shadow") is not None:
            self._shadow.close()
            self._shadow = None

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

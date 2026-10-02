"""Compact, cached replay commands.

Parsing a replay with screp and reading its JSON is ~90% of the cost of a command-level pass.
This module does it once per replay and stores only what the extractors use, so re-running an
extractor after a rule change takes seconds instead of minutes.

Cache: data/interim/cmdcache/v<CACHE_VERSION>/<sha1[:2]>/<sha1>.pkl.zz (pickle, zlib-compressed).
Bump CACHE_VERSION whenever the stored fields change; old versions can simply be deleted.

Each command is a tuple, indexed with the constants below:
  (frame, player_id, type, order, name, tags, pos, group, hotkey_type)
    type         screp command type name ("Build", "Select", "Targeted Order", ...)
    order        order name for Build / Targeted Order ("PlaceAddon", "RallyPointTile", ...)
    name         unit / tech / upgrade name for Build, Train, Morph, Tech, Upgrade
    tags         unit IDs for Select / Select Add / Select Remove
    pos          (x, y) for Build
    group        hotkey group number; hotkey_type: "Assign" | "Add" | "Select"
"""

from __future__ import annotations

import json
import pickle
import subprocess
import zlib
from pathlib import Path

CACHE_VERSION = 1
F, P, T, O, N, TAGS, POS, G, H = range(9)

# Command types the extractors need. Right Click (a fifth of all commands), chat, pings and
# similar are dropped to keep the cache small.
KEEP_TYPES = {
    "Select", "Select Add", "Select Remove", "Hotkey",
    "Build", "Train", "Unit Morph", "Building Morph", "Tech", "Upgrade",
    "Cancel Build", "Cancel Morph", "Cancel Train", "Cancel Tech", "Cancel Upgrade",
    "Targeted Order", "Stim", "Siege", "Unsiege", "Burrow", "Unburrow", "Return Cargo",
    "Hold Position", "Stop", "Lift Off", "Land", "Leave Game",
}


def _name(v: dict | None) -> str | None:
    return v.get("Name") if v else None


def compact(d: dict) -> dict:
    """screp JSON -> {"players": [...], "cmds": [tuple, ...]}"""
    players = [{
        "id": p.get("ID"), "name": p.get("Name"), "team": p.get("Team"),
        "race": chr((p.get("Race") or {}).get("Letter") or ord("?")),
        "type": _name(p.get("Type")), "observer": bool(p.get("Observer")),
    } for p in (d.get("Header") or {}).get("Players") or []]
    cmds = []
    for c in (d.get("Commands") or {}).get("Cmds") or []:
        t = _name(c.get("Type"))
        if t not in KEEP_TYPES:
            continue
        pos = c.get("Pos")
        cmds.append((
            c["Frame"], c["PlayerID"], t, _name(c.get("Order")),
            _name(c.get("Unit")) or _name(c.get("Tech")) or _name(c.get("Upgrade")),
            tuple(c["UnitTags"]) if c.get("UnitTags") else None,
            (pos["X"], pos["Y"]) if pos and t == "Build" else None,
            c.get("Group"), _name(c.get("HotkeyType")),
        ))
    return {"players": players, "cmds": cmds}


def cache_path(cache_root: Path, sha1: str) -> Path:
    return cache_root / f"v{CACHE_VERSION}" / sha1[:2] / f"{sha1}.pkl.zz"


def load_game(screp: str, replay: Path, sha1: str, cache_root: Path) -> dict:
    """Compact commands for one replay, from the cache or by running screp (and caching)."""
    path = cache_path(cache_root, sha1)
    if path.exists():
        return pickle.loads(zlib.decompress(path.read_bytes()))
    # computed data is needed: screp only marks observers when it computes derived data
    out = subprocess.run([screp, "-indent=false", "-cmds", str(replay)], capture_output=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode("utf-8", "replace")[:200])
    game = compact(json.loads(out.stdout.decode("utf-8", "replace")))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(zlib.compress(pickle.dumps(game, protocol=pickle.HIGHEST_PROTOCOL), 1))
    tmp.replace(path)  # atomic: a killed run never leaves a half-written cache file
    return game

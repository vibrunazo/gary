"""Brood War commands, encoded as in replays (the bytes after the player id).

These are what the game engine executes. For now Gary's code calls them directly; later the
human interface (docs/ARCHITECTURE.md §6.3) will be the only thing allowed to emit them, after
applying camera, selection, APM and mouse limits.
"""

from __future__ import annotations

import struct

# Unit type IDs (Brood War)
SCV, DRONE, PROBE = 7, 41, 64
COMMAND_CENTER, HATCHERY, NEXUS = 106, 131, 154
SUPPLY_DEPOT, BARRACKS, PYLON = 109, 111, 156
MINERAL_FIELDS = {176, 177, 178}
NO_UNIT = 0xE4  # "none" unit type

# Order IDs used by build commands
ORDER_PLACE_BUILDING = 0x1E      # Terran
ORDER_PLACE_PROTOSS_BUILDING = 0x1F
ORDER_DRONE_START_BUILD = 0x19


def select(tags: list[int]) -> bytes:
    if not 1 <= len(tags) <= 12:
        raise ValueError("a selection holds 1 to 12 units")
    return struct.pack("<BB", 0x09, len(tags)) + b"".join(struct.pack("<H", t) for t in tags)


def right_click(x: int, y: int, target_tag: int = 0, target_type: int = NO_UNIT, queued: bool = False) -> bytes:
    """Move to (x, y) in pixels, or act on a target unit (mine a mineral field, attack...)."""
    return struct.pack("<BhhHHB", 0x14, x, y, target_tag, target_type, int(queued))


def train(unit_type: int) -> bytes:
    """Train or morph from the selected building / larva."""
    return struct.pack("<BH", 0x1F, unit_type)


def build(unit_type: int, tile_x: int, tile_y: int, order: int = ORDER_PLACE_BUILDING) -> bytes:
    """The selected worker builds unit_type with its top-left corner at (tile_x, tile_y)."""
    return struct.pack("<BBHHH", 0x0C, order, tile_x, tile_y, unit_type)


def morph(unit_type: int) -> bytes:
    """Zerg: morph the selected larva (or units) into unit_type."""
    return struct.pack("<BH", 0x23, unit_type)


LARVA = 35

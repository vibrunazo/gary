"""The human interface: the only way Gary touches the game (docs/ARCHITECTURE.md §3, §6.2, §6.3).

Gary acts like a person at a keyboard and mouse, and sees what a person would see:

- **Camera.** Gary has a screen-sized view of the map. Clicks must land inside it (minimap
  commands are the exception, with much worse precision). Moving the camera costs an action.
- **Mouse.** Clicks are screen pixels, never unit IDs. The game decides what's under the
  pixel, so in a stack of units the one on top gets clicked. The cursor has to travel: each
  click lands after a Fitts's-law delay from where the cursor was, with scatter that grows
  when Gary rushes.
- **Selection.** At most 12 units, built by clicking, drag boxes and hotkeys.
- **APM budget.** A token bucket: every action costs one token; tokens refill at a steady
  rate up to a burst capacity. No tokens, no action.
- **Seeing.** Fog of war: enemy units only when visible. Enemy HP and shields only for an
  enemy unit you have selected. Everything arrives late by the profile's reaction time.

v1 limits (deliberately simple; each is a parameter to calibrate from replay and camera-logger
data later): hit-testing uses each unit's clickable rectangle, not its exact pixels; box
selection uses the game's own rules approximately; no memory of fogged units yet (§6.10).

Usage:
    hi = HumanInterface(game, slot=3, profile=PROFILES["b_rank"])
    obs = hi.observe()
    hi.camera_center(x, y); hi.click(sx, sy); hi.right_click(sx, sy); hi.train(SCV)
    hi.step(8)   # advances the game; queued clicks land when their mouse travel finishes
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field, replace

from gary import commands as C
from gary.env import Game

FRAME_MS = 42  # one frame at Fastest speed
NO_UNIT = 0


@dataclass(frozen=True)
class Profile:
    """Human limits (docs/ARCHITECTURE.md §6.2). Numbers are placeholders until fitted from data."""
    name: str = "b_rank"
    viewport: tuple[int, int] = (640, 400)   # playable screen area in map pixels
    apm_capacity: float = 10.0               # burst size (tokens)
    apm_per_second: float = 3.5              # sustained rate (~210 APM)
    fitts_a_ms: float = 90.0                 # Fitts's law: T = a + b * log2(D / W + 1)
    fitts_b_ms: float = 110.0
    scatter_px: float = 3.0                  # click scatter (std dev) at a relaxed pace
    scatter_rushed_px: float = 6.0           # extra scatter when the APM bucket is nearly empty
    minimap_scatter_px: float = 48.0         # map pixels
    reaction_ms: float = 300.0               # observation delay


PROFILES = {
    "b_rank": Profile(),
    "b_rank_widescreen": Profile(name="b_rank_widescreen", viewport=(854, 400)),
    "c_rank": Profile(name="c_rank", apm_capacity=7.0, apm_per_second=2.2, scatter_px=4.0,
                      scatter_rushed_px=8.0, reaction_ms=400.0),
}


@dataclass
class ActionResult:
    accepted: bool            # did the interface take the action (APM, camera, selection limits)
    reason: str = ""          # why not, if not
    land_frame: int = -1      # when it reaches the game


@dataclass
class _Pending:
    land_frame: int
    kind: str
    args: dict = field(default_factory=dict)


class HumanInterface:
    def __init__(self, game: Game, slot: int, profile: Profile = PROFILES["b_rank"], seed: int = 0):
        self.game = game
        self.slot = slot
        self.p = profile
        self.rng = random.Random(seed)
        obs = game.observe()
        self.frame = obs["frame"]
        start = next((u for u in obs["units"] if u["owner"] == slot and u["type"] in
                      (C.COMMAND_CENTER, C.HATCHERY, C.NEXUS)), None)
        vw, vh = self.p.viewport
        cx, cy = (start["x"], start["y"]) if start else (vw // 2, vh // 2)
        self.camera = (max(0, cx - vw // 2), max(0, cy - vh // 2))   # top-left, map pixels
        self.cursor = (vw // 2, vh // 2)                              # screen pixels
        self.hand_free_at = self.frame                                # when the mouse is free
        self.tokens = self.p.apm_capacity
        self.selection: list[int] = []
        self.hotkeys: dict[int, list[int]] = {}
        self.pending: list[_Pending] = []
        self.history: deque[tuple[int, dict]] = deque([(self.frame, obs)], maxlen=256)
        self.stats = {"actions": 0, "rejected_by_interface": 0, "rejected_by_game": 0}

    # --- what Gary sees ------------------------------------------------------------------

    def observe(self) -> dict:
        """The game as this player saw it reaction_ms ago, fogged, plus the interface state."""
        delay = round(self.p.reaction_ms / FRAME_MS)
        seen = self.history[0][1]
        for frame, obs in self.history:
            if frame <= self.frame - delay:
                seen = obs
        me = next(p for p in seen["players"] if p["slot"] == self.slot)
        bit = 1 << self.slot
        inspected = set(self.selection) if len(self.selection) == 1 else set()
        units = []
        for u in seen["units"]:
            mine = u["owner"] == self.slot
            if not mine and not (u["visible_to"] & bit):
                continue
            v = dict(u)
            v.pop("visible_to", None)
            if not mine and u["owner"] != 11 and u["tag"] not in inspected:
                v["hp"] = v["shields"] = None        # the UI doesn't show enemy HP unless selected
            units.append(v)
        return {
            "frame": seen["frame"], "now": self.frame, "me": me, "units": units,
            "camera": {"x": self.camera[0], "y": self.camera[1],
                       "w": self.p.viewport[0], "h": self.p.viewport[1]},
            "cursor": self.cursor, "selection": list(self.selection),
            "hotkeys": {k: list(v) for k, v in self.hotkeys.items()},
            "apm_tokens": round(self.tokens, 2),
        }

    # --- helpers -------------------------------------------------------------------------

    def _spend(self) -> ActionResult | None:
        if self.tokens < 1:
            self.stats["rejected_by_interface"] += 1
            return ActionResult(False, "apm")
        self.tokens -= 1
        self.stats["actions"] += 1
        return None

    def _on_screen(self, sx: int, sy: int) -> bool:
        return 0 <= sx < self.p.viewport[0] and 0 <= sy < self.p.viewport[1]

    def _schedule_click(self, sx: int, sy: int, target_w: float, kind: str, **args) -> ActionResult:
        if not self._on_screen(sx, sy):
            self.stats["rejected_by_interface"] += 1
            return ActionResult(False, "offscreen")
        if (r := self._spend()):
            return r
        dist = math.dist(self.cursor, (sx, sy))
        travel_ms = self.p.fitts_a_ms + self.p.fitts_b_ms * math.log2(dist / max(target_w, 1) + 1)
        start = max(self.frame, self.hand_free_at)
        land = start + max(1, round(travel_ms / FRAME_MS))
        rushed = 1 - self.tokens / self.p.apm_capacity
        sigma = self.p.scatter_px + self.p.scatter_rushed_px * rushed
        lx = round(sx + self.rng.gauss(0, sigma))
        ly = round(sy + self.rng.gauss(0, sigma))
        self.hand_free_at = land
        self.cursor = (sx, sy)
        self.pending.append(_Pending(land, kind, {"sx": lx, "sy": ly, **args}))
        return ActionResult(True, land_frame=land)

    def _schedule_key(self, kind: str, **args) -> ActionResult:
        if (r := self._spend()):
            return r
        land = self.frame + 1
        self.pending.append(_Pending(land, kind, args))
        return ActionResult(True, land_frame=land)

    def _send(self, command: bytes) -> bool:
        ok = self.game.act(self.slot, command)
        if not ok:
            self.stats["rejected_by_game"] += 1
            key = f"rejected_by_game_{command[0]:#04x}"
            self.stats[key] = self.stats.get(key, 0) + 1
        return ok

    def _to_map(self, sx: int, sy: int) -> tuple[int, int]:
        return self.camera[0] + sx, self.camera[1] + sy

    # --- actions (each costs one APM token) ----------------------------------------------

    def camera_center(self, map_x: int, map_y: int) -> ActionResult:
        """Move the view (minimap click or edge scroll, abstracted as one action)."""
        return self._schedule_key("camera", x=map_x, y=map_y)

    def click(self, sx: int, sy: int, shift: bool = False) -> ActionResult:
        """Left click on the screen: select whatever is drawn there."""
        return self._schedule_click(sx, sy, 16, "click", shift=shift)

    def box(self, sx0: int, sy0: int, sx1: int, sy1: int) -> ActionResult:
        """Drag-select a screen rectangle."""
        if not (self._on_screen(sx0, sy0) and self._on_screen(sx1, sy1)):
            self.stats["rejected_by_interface"] += 1
            return ActionResult(False, "offscreen")
        w = max(abs(sx1 - sx0), abs(sy1 - sy0), 16)
        return self._schedule_click(sx1, sy1, w, "box", x0=sx0, y0=sy0)

    def right_click(self, sx: int, sy: int, queued: bool = False) -> ActionResult:
        """Smart command at a screen point: move, attack, gather, follow."""
        return self._schedule_click(sx, sy, 16, "right_click", queued=queued)

    def minimap_right_click(self, map_x: int, map_y: int) -> ActionResult:
        """Right click on the minimap: anywhere on the map, but imprecise."""
        if (r := self._spend()):
            return r
        land = max(self.frame, self.hand_free_at) + round(self.p.fitts_a_ms / FRAME_MS) + 1
        s = self.p.minimap_scatter_px
        self.hand_free_at = land
        self.pending.append(_Pending(land, "minimap_right_click", {
            "x": round(map_x + self.rng.gauss(0, s)), "y": round(map_y + self.rng.gauss(0, s))}))
        return ActionResult(True, land_frame=land)

    def train(self, unit_type: int) -> ActionResult:
        """Hotkey: train from the selected building."""
        return self._schedule_key("train", unit_type=unit_type)

    def morph(self, unit_type: int) -> ActionResult:
        """Hotkey: morph the selected larva."""
        return self._schedule_key("morph", unit_type=unit_type)

    def build(self, unit_type: int, sx: int, sy: int, order: int = C.ORDER_PLACE_BUILDING) -> ActionResult:
        """Place a building with the selected worker at a screen point (its top-left tile)."""
        return self._schedule_click(sx, sy, 32, "build", unit_type=unit_type, order=order)

    def hotkey_set(self, n: int) -> ActionResult:
        return self._schedule_key("hotkey_set", n=n)

    def hotkey_add(self, n: int) -> ActionResult:
        return self._schedule_key("hotkey_add", n=n)

    def hotkey_recall(self, n: int) -> ActionResult:
        return self._schedule_key("hotkey_recall", n=n)

    # --- time --------------------------------------------------------------------------

    def step(self, frames: int, advance_game: bool = True) -> None:
        """Advance the game, landing queued actions on their frames. When several players share
        one game, every interface steps, but only one of them advances the game itself."""
        end = self.frame + frames
        while self.frame < end:
            due = sorted((a for a in self.pending if a.land_frame <= self.frame), key=lambda a: a.land_frame)
            for a in due:
                self.pending.remove(a)
                self._land(a)
            if advance_game:
                self.game.step(1)
            self.frame += 1
            self.tokens = min(self.p.apm_capacity, self.tokens + self.p.apm_per_second * FRAME_MS / 1000)
            if self.frame % 4 == 0:
                self.history.append((self.frame, self.game.observe()))

    def _land(self, a: _Pending) -> None:
        g = self.game
        if a.kind == "camera":
            vw, vh = self.p.viewport
            self.camera = (max(0, a.args["x"] - vw // 2), max(0, a.args["y"] - vh // 2))
        elif a.kind == "click":
            tag = g.unit_at(self.slot, *self._to_map(a.args["sx"], a.args["sy"]))
            if tag:
                if a.args["shift"] and self.selection:
                    if self._send(bytes([0x0A, 1]) + tag.to_bytes(2, "little")):
                        self.selection = (self.selection + [tag])[:12]
                elif self._send(C.select([tag])):
                    self.selection = [tag]
        elif a.kind == "box":
            x0, y0 = self._to_map(a.args["x0"], a.args["y0"])
            x1, y1 = self._to_map(a.args["sx"], a.args["sy"])
            tags = g.box_select(self.slot, x0, y0, x1, y1)
            if tags and self._send(C.select(tags)):
                self.selection = tags
        elif a.kind == "right_click":
            x, y = self._to_map(a.args["sx"], a.args["sy"])
            tag = g.unit_at(self.slot, x, y)
            self._send(C.right_click(x, y, tag, C.NO_UNIT if not tag else g.unit_type_of(tag), a.args["queued"]))
        elif a.kind == "minimap_right_click":
            self._send(C.right_click(a.args["x"], a.args["y"]))
        elif a.kind == "train":
            self._send(C.train(a.args["unit_type"]))
        elif a.kind == "morph":
            self._send(C.morph(a.args["unit_type"]))
        elif a.kind == "build":
            x, y = self._to_map(a.args["sx"], a.args["sy"])
            self._send(C.build(a.args["unit_type"], x // 32, y // 32, a.args["order"]))
        elif a.kind == "hotkey_set":
            self.hotkeys[a.args["n"]] = list(self.selection)
        elif a.kind == "hotkey_add":
            self.hotkeys[a.args["n"]] = list(dict.fromkeys(self.hotkeys.get(a.args["n"], []) + self.selection))[:12]
        elif a.kind == "hotkey_recall":
            tags = self.hotkeys.get(a.args["n"], [])
            if tags and self._send(C.select(tags)):
                self.selection = list(tags)


def screen_of(obs: dict, x: int, y: int) -> tuple[int, int] | None:
    """Screen position of a map point in an observation, or None if it's outside the view."""
    cam = obs["camera"]
    sx, sy = x - cam["x"], y - cam["y"]
    return (sx, sy) if 0 <= sx < cam["w"] and 0 <= sy < cam["h"] else None

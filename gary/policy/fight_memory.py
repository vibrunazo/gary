"""What the fight command model remembers: the player's own recent commands (#2).

Without memory the command model decides from the current snapshot alone and switches plans every
second or two; a player holds a plan for several seconds (pull the workers, then send them back).
This module turns the player's last commands into model inputs, the same way in training (the
pro's commands, from the fight set) and in play (the commands Gary's hands issued, logged by the
human interface):

  per unit     the last command that included it in the last HIST_S seconds: its kind, how long
               ago, and where it sent the unit (relative to the unit); and how long ago a command
               targeted the unit
  history      the last HIST_K commands as tokens: kind, age, how many units, how many of them are
               in the fight, where those are, and the command's point (relative to the fight)

A command is (frame, kind, unit tags, x, y, target tag), x and y in map pixels (0 if none). Kinds
(HIST_KINDS) are what the player did, as a replay records it: right-click on ground or on a
unit, attack (on a unit or the ground), move order, stop, hold, stim, return cargo, other.
No torch here: the dataset builder uses it too.
"""

from __future__ import annotations

import numpy as np

HIST_S = 8.0                    # seconds of commands remembered
HIST_K = 6                      # commands kept as history tokens
FRAME_S = 42 / 1000
HIST_KINDS = ["none", "rclick_ground", "rclick_unit", "attack_unit", "attack_ground", "move", "stop", "hold",
              "stim", "return_cargo", "other"]
K = {k: i for i, k in enumerate(HIST_KINDS)}
WITH_POINT = {K["rclick_ground"], K["attack_ground"], K["move"]}
ATTACK_ORDERS = {10, 11, 14}    # attack unit, attack (fixed), attack-move
UNIT_FEATURES = 5               # age, dx, dy, has point, targeted age
TOKEN_FEATURES = 8              # age, units, units in the fight, their x, y, point x, y, has point
POS = 512.0


def command_kind(cmd: str, order: int, target: int) -> int:
    """The kind of a command, from resim's ucmd fields (cmd, order, target tag)."""
    if cmd == "rclick":
        return K["rclick_unit"] if target else K["rclick_ground"]
    if cmd == "order":
        if order in ATTACK_ORDERS:
            return K["attack_unit"] if target else K["attack_ground"]
        return K["move"] if order == 6 else K["other"]
    return {"stop": K["stop"], "hold": K["hold"], "stim": K["stim"], "return": K["return_cargo"]}.get(cmd, K["other"])


def history_inputs(tags, rows: np.ndarray, center: tuple[float, float], flip: tuple[bool, bool], frame: int,
                   commands: list[tuple]):
    """Model inputs for one snapshot. tags: the snapshot's unit tags, rows: its unit rows (x, y in
    columns 2, 3: relative to the center, mirrored by flip), commands: the player's commands, oldest
    first (later ones than frame count as just given). Returns (unit kind (n,), unit features
    (n, UNIT_FEATURES), token features (HIST_K, TOKEN_FEATURES), token kind (HIST_K,), token
    absent (HIST_K,))."""
    n = len(tags)
    u_kind = np.zeros(n, np.int64)
    u_num = np.zeros((n, UNIT_FEATURES), np.float32)
    u_num[:, 0] = 1.0                            # age 1 = nothing remembered
    u_num[:, 4] = 1.0
    tok = np.zeros((HIST_K, TOKEN_FEATURES), np.float32)
    t_kind = np.zeros(HIST_K, np.int64)
    t_absent = np.ones(HIST_K, bool)
    oldest = frame - HIST_S / FRAME_S
    recent = [c for c in commands if c[0] >= oldest][-HIST_K:]
    if not recent:
        return u_kind, u_num, tok, t_kind, t_absent
    row = {t: i for i, t in enumerate(tags)}
    cx, cy = center
    fx, fy = flip

    def rel(x, y):
        dx, dy = x - cx, y - cy
        return (-dx if fx else dx), (-dy if fy else dy)

    for k, (f, kind, units, x, y, target) in enumerate(recent):
        age = min(1.0, max(0.0, frame - f) * FRAME_S / HIST_S)
        has_point = kind in WITH_POINT
        px, py = rel(x, y) if has_point else (0.0, 0.0)
        present = [row[t] for t in units if t in row]
        for i in present:                         # newer commands overwrite older ones
            u_kind[i] = kind
            u_num[i, 0] = age
            if has_point:
                u_num[i, 1] = (px - rows[i, 2]) / POS
                u_num[i, 2] = (py - rows[i, 3]) / POS
                u_num[i, 3] = 1.0
            else:
                u_num[i, 1:4] = 0.0
        if target and target in row:
            u_num[row[target], 4] = age
        j = HIST_K - len(recent) + k             # newest last
        mx = float(np.mean([rows[i, 2] for i in present])) if present else 0.0
        my = float(np.mean([rows[i, 3] for i in present])) if present else 0.0
        tok[j] = (age, len(units) / 12, len(present) / 12, mx / POS, my / POS, px / POS, py / POS, float(has_point))
        t_kind[j] = kind
        t_absent[j] = False
    return u_kind, u_num, tok, t_kind, t_absent

#!/usr/bin/env python3
"""Drive the SC:R menus to start a custom melee game vs one computer — no human clicks.

    python adapters/scr_bridge/tools/auto_game.py               # click through to a melee game
    python adapters/scr_bridge/tools/auto_game.py --calibrate   # screenshot the game window only
    python adapters/scr_bridge/tools/auto_game.py --click 0.5,0.3   # one click at (fx, fy)

Clicks are (fx, fy) fractions of the game window rect, so the map is resolution-independent.
Every run saves build/auto_game/step_NN_before.png screenshots; the STEPS table is calibrated
from those (that loop needs no human either: run --calibrate, read the shot, add a step, repeat).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "adapters" / "scr_bridge"))

import ctypes  # noqa: E402
from ctypes import wintypes  # noqa: E402

from PIL import Image, ImageGrab  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1] / "build" / "auto_game"
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Calibrated click map: label, (fx, fy) of the game window (fullscreen layout: screen-sized
# window with the 4:3 game content letterboxed inside). Calibrated 2026-10-03 against
# 1.23.10.13515. Only TEXT labels are buttons in BW menus — clicking art just cancels dialogs.
# SC:R restores its last menu screen on the next launch (observed: the single-player menu), so
# early steps are no-ops unless their screen is up. NEVER click (0.755, 0.894): that is the
# single-player menu's "Cancel", which quits the game (ESC at the top-level menu does too).
STEPS: list[tuple[str, float, float]] = [
    ("single_player", 0.371, 0.256),  # main menu -> "Select Game Type" dialog (else no-op)
    ("expansion", 0.557, 0.619),      # dialog: "Expansion" text -> character pick (else no-op)
    ("registry_ok", 0.730, 0.822),    # character pick ("kuia") -> Ok -> single-player menu
    ("play_custom", 0.512, 0.861),    # single-player menu -> Create game screen
    ("create_ok", 0.730, 0.820),      # Create game (map preset, Melee, one Computer) -> Ok
]


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def find_process(name: str) -> int:
    """PID of the first running process whose image name matches (\"StarCraft\" -> StarCraft.exe)."""
    want = name if name.lower().endswith(".exe") else name + ".exe"
    snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snap in (0, -1, 0xFFFFFFFF):
        return 0
    try:
        pe = _PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            if pe.szExeFile.lower() == want.lower():
                return int(pe.th32ProcessID)
            ok = kernel32.Process32NextW(snap, ctypes.byref(pe))
        return 0
    finally:
        kernel32.CloseHandle(snap)


def find_game_window() -> int:
    pid = find_process("StarCraft")
    if not pid:
        return 0
    best = {"hwnd": 0, "area": -1}

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == lparam and user32.IsWindowVisible(hwnd):
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            area = max(0, r.right - r.left) * max(0, r.bottom - r.top)
            if area > best["area"]:
                best["hwnd"] = hwnd
                best["area"] = area
        return True  # visit every window and keep the largest (the game view)

    user32.EnumWindows(cb, pid)
    return best["hwnd"]


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        raise RuntimeError(f"GetWindowRect failed (hwnd={hwnd} — game window gone?)")
    if r.right <= r.left or r.bottom <= r.top:
        raise RuntimeError(f"degenerate game window rect {(r.left, r.top, r.right, r.bottom)}")
    return r.left, r.top, r.right, r.bottom


def ensure_fullscreen(hwnd: int) -> int:
    """The STEPS table is calibrated for the fullscreen layout (screen-sized window; the 4:3
    game content is letterboxed inside it). SC:R can start windowed or flip modes, so toggle
    with Alt+Enter until the window covers the screen. Returns the (possibly new) hwnd."""
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    for _ in range(3):
        hwnd = find_game_window() or hwnd
        try:
            if window_rect(hwnd) == (0, 0, sw, sh):
                return hwnd
        except RuntimeError:
            pass  # window mid-recreation (SC:R does that while switching modes)
        raise_window(hwnd)
        user32.keybd_event(0x12, 0, 0, 0)          # VK_MENU down
        user32.keybd_event(0x0D, 0, 0, 0)          # VK_RETURN down
        user32.keybd_event(0x0D, 0, 0x0002, 0)     # VK_RETURN up
        user32.keybd_event(0x12, 0, 0x0002, 0)     # VK_MENU up
        time.sleep(3.0)
    raise SystemExit(f"game window stuck at {window_rect(hwnd)}, not fullscreen "
                     f"{(0, 0, sw, sh)} — the calibrated STEPS need the fullscreen layout")


def raise_window(hwnd: int) -> None:
    """Bring the game to the foreground. Plain SetForegroundWindow is refused when our
    process does not own the foreground (Windows lock), so attach to the current
    foreground thread's input queue first — the standard bypass."""
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    cur = kernel32.GetCurrentThreadId()
    fg_tid = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    attached = bool(fg_tid and fg_tid != cur)
    if attached:
        user32.AttachThreadInput(cur, fg_tid, True)
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur, fg_tid, False)
    time.sleep(0.4)


def shot(hwnd: int, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    # ImageGrab captures screen pixels at the window rect, so the game must be on top
    # (a fullscreen-sized background window would capture whatever covers it).
    raise_window(hwnd)
    for attempt in range(3):
        try:
            ImageGrab.grab(bbox=window_rect(hwnd)).save(path)
            return path
        except (RuntimeError, ValueError):
            time.sleep(1.5)  # SC:R recreates its window while switching display modes
            hwnd = find_game_window() or hwnd
    raise SystemExit(f"could not screenshot the game window (hwnd={hwnd})")


def click(hwnd: int, fx: float, fy: float) -> tuple[int, int]:
    hwnd = find_game_window() or hwnd
    l, t, r, b = window_rect(hwnd)
    x = l + int((r - l) * fx)
    y = t + int((b - t) * fy)
    raise_window(hwnd)
    user32.SetCursorPos(x, y)
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
    time.sleep(0.06)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
    return x, y


def in_game() -> bool:
    try:
        from gary.scr_env import ScrGame

        return bool(ScrGame.connect().status().get("in_game"))
    except Exception:
        return False


# ---- keyboard menu navigation (default): no visible clicks, works on an occluded window ----
# SC:R menus respond to hotkey letters (S=ingle player, E=xpansion, O=K, cU=stom, ...), so the
# whole menu walk is one typed sequence with settle delays. Keys are POSTED to the window
# (WM_KEYDOWN/CHAR/KEYUP) so the game needs neither focus nor visibility — the user's screen
# stays theirs. If a menu ever ignores posted input, --foreground-keys uses the real input path.

PW_RENDERFULLCONTENT = 2
WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x0100, 0x0101, 0x0102


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
    ]


def bg_shot(hwnd: int, name: str) -> Path:
    """PrintWindow capture — unlike shot(), works while the window is occluded or behind other
    windows, so step evidence never requires the user's visible screen."""
    gdi32 = ctypes.windll.gdi32
    l, t, r, b = window_rect(hwnd)
    w, h = r - l, b - t
    hdc = user32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(memdc, bmp)
    ok = user32.PrintWindow(hwnd, memdc, PW_RENDERFULLCONTENT)
    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth, bmi.biHeight = w, -h  # top-down
    bmi.biPlanes, bmi.biBitCount = 1, 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    gdi32.SelectObject(memdc, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)
    img = Image.frombytes("RGB", (w, h), buf.raw, "raw", "BGRX")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    img.save(path)
    if not ok:
        print(f"  note: PrintWindow returned 0 for {name} — image may be blank")
    return path


def send_key(hwnd: int, key: str, background: bool = True) -> None:
    """Send one key to the game window. background=True posts the messages directly (no focus
    change at all); background=False focuses the window and uses the real input path."""
    vk = ord(key.upper())
    if background:
        scan = user32.MapVirtualKeyW(vk, 0)
        lparam_down = 1 | (scan << 16)
        lparam_up = lparam_down | (1 << 30) | (1 << 31)
        user32.PostMessageW(hwnd, WM_KEYDOWN, vk, lparam_down)
        user32.PostMessageW(hwnd, WM_CHAR, vk, lparam_down)
        user32.PostMessageW(hwnd, WM_KEYUP, vk, lparam_up)
    else:
        raise_window(hwnd)
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 0x0002, 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true", help="screenshot the game window, click nothing")
    ap.add_argument("--click", metavar="FX,FY", help="perform exactly one click, then screenshot")
    ap.add_argument("--settle", type=float, default=4.0,
                    help="seconds to wait after each click (SC:R textures load late)")
    ap.add_argument("--mode", choices=("keys", "clicks"), default="keys",
                    help="keys: hotkey navigation, no visible interaction (default); "
                         "clicks: the calibrated screenshot+click flow")
    ap.add_argument("--keys", default="S,E,O,U,O",
                    help="comma-separated menu hotkeys for --mode keys: S ingle player, "
                         "E xpansion, O=K, cU=stom game, O=K")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds to wait after each key")
    ap.add_argument("--foreground-keys", action="store_true",
                    help="focus the game and use real input instead of posted messages")
    args = ap.parse_args()

    hwnd = find_game_window()
    if not hwnd:
        raise SystemExit("game window not found — launch.py first")
    print(f"game window: hwnd={hwnd} rect={window_rect(hwnd)}")

    if args.calibrate:
        p = shot(hwnd, f"calib_{int(time.time())}.png")
        print(f"calibration screenshot: {p}")
        return

    if args.click:
        fx, fy = (float(v) for v in args.click.split(","))
        pos = click(hwnd, fx, fy)
        print(f"clicked at {pos}")
        shot(hwnd, "after_click.png")
        return

    if args.mode == "keys":
        keys = [k.strip().upper() for k in args.keys.split(",") if k.strip()]
        mode = "foreground" if args.foreground_keys else "background"
        print(f"keyboard navigation ({mode} keys, {args.delay}s apart): {' '.join(keys)}")
        for i, k in enumerate(keys):
            hwnd = find_game_window() or hwnd
            p = bg_shot(hwnd, f"key_{i:02d}_before_{k}.png")
            print(f"key {i} '{k}': state shot {p.name}")
            if in_game():
                print("in_game already — stopping")
                break
            send_key(hwnd, k, background=not args.foreground_keys)
            time.sleep(args.delay)
        hwnd = find_game_window() or hwnd
        bg_shot(hwnd, "key_final.png")

        deadline = time.time() + 15
        while time.time() < deadline:
            if in_game():
                print("SUCCESS: game is running (in_game=true)")
                return
            time.sleep(1)
        raise SystemExit(
            "keys sent but the game did not start — read build/auto_game/key_*.png "
            "(captured invisibly), adjust --keys, or retry with --foreground-keys / --mode clicks")

    if not STEPS:
        raise SystemExit(
            "STEPS is not calibrated yet. Run with --calibrate, read build/auto_game/*.png, "
            "and fill the STEPS table (label, fx, fy) in tools/auto_game.py.")

    hwnd = ensure_fullscreen(hwnd)
    print(f"fullscreen layout ready: hwnd={hwnd} rect={window_rect(hwnd)}")

    for i, (label, fx, fy) in enumerate(STEPS):
        hwnd = find_game_window() or hwnd
        p = shot(hwnd, f"step_{i:02d}_before_{label}.png")
        print(f"step {i} {label}: shot {p.name}")
        if in_game():
            print("in_game already — stopping")
            break
        pos = click(hwnd, fx, fy)
        print(f"  clicked {pos}")
        time.sleep(args.settle)

    deadline = time.time() + 30
    while time.time() < deadline:
        if in_game():
            print("SUCCESS: game is running (in_game=true)")
            return
        time.sleep(1)
    shot(hwnd, "final_state.png")
    raise SystemExit(
        "game did not start within 30s — read build/auto_game/step_*.png and final_state.png "
        "and correct the STEPS map")


if __name__ == "__main__":
    main()
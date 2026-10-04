"""Watch any replay in gary_view, Remastered ones included, optionally from Gary's point of view.

Remastered replays (1.18+) are decoded first (resim/scr_format.py), then gary_view plays the
decoded stream. Every other option goes straight to gary_view (see viewer/gary_view.cpp).

    python viewer/watch.py "data/raw/vib/Gary v3 got owned.rep" --pov gary_v01_live.pov.jsonl
    python viewer/watch.py some_game.rep --pov gary.pov.jsonl --record gary.mp4 --to 300
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "resim"))
import scr_format  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("replay")
    ap.add_argument("--data", default=str(REPO_ROOT / "data" / "gamedata" / "scr"), help="extracted game data")
    args, rest = ap.parse_known_args()
    exe = REPO_ROOT / "viewer" / "build" / ("gary_view.exe" if os.name == "nt" else "gary_view")
    if not exe.exists():
        sys.exit("gary_view not built: run viewer/build.bat (see viewer/README.md)")
    data = Path(args.replay).read_bytes()
    cmd = [str(exe), "--data", args.data]
    tmp = None
    if scr_format.replay_format(data) != "legacy":
        tmp = tempfile.NamedTemporaryFile(suffix=".flat", delete=False)
        tmp.write(scr_format.to_flat(data))
        tmp.close()
        cmd += ["--replay", tmp.name, "--flat", "--unit-limit", str(scr_format.unit_limit(data))]
    else:
        cmd += ["--replay", args.replay]
    try:
        sys.exit(subprocess.call(cmd + rest))
    finally:
        if tmp:
            os.unlink(tmp.name)


if __name__ == "__main__":
    main()

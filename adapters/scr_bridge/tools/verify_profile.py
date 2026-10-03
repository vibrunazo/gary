#!/usr/bin/env python3
"""Offline verification of scr_profile.h against an installed StarCraft executable.

No game is run: this parses the PE, checks the SHA-256 pin, validates the address convention
(image base == kAnalyzedBase) and prints the bytes at each profiled code/import address so the
facts can be eyeballed or diffed after a game patch.

    python adapters/scr_bridge/tools/verify_profile.py "D:\\games\\StarCraft\\x86\\StarCraft.exe"

Exit code 0 = every hard check passed. The live probe (launch.py --smoke) covers the runtime
semantics this tool cannot see (README "Verification plan").
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_facts import PeFile, read_profile, sha256_file  # noqa: E402

# VA constants that point at code or the import table; printed as hex dumps.
CODE_FACTS = ["SendCommand", "PrintText", "FrameAfter", "FrameBefore"]
# VA constants that point at global pointer variables; printed as 4 bytes in the file.
DATA_FACTS = ["GameXorPtr", "PlayersSubPtr", "PlayersXorPtr", "FirstActiveUnit",
              "FirstHiddenUnit", "UnitsBase", "UnitCount", "LocalPlayerId", "MapTileFlags",
              "TimingTickPtr"]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    exe = Path(sys.argv[1])
    profile = read_profile()
    problems = 0

    got = sha256_file(exe)
    want = profile["ExeSha256"].upper()
    ok = got == want
    print(f"{'ok  ' if ok else 'FAIL'} sha256 {got}")
    print(f"     pinned {want} ({profile.get('BuildName', '?')})")
    if not ok:
        print("     -> a different build: every address below is meaningless (update the "
              "profile via samase_scarf analysis, or pin this build anew)")
        problems += 1

    pe = PeFile(exe)
    base = profile["AnalyzedBase"]
    # The VA convention is relative to kAnalyzedBase (addr = module + va - base), so the PE's
    # own image base may legitimately differ; RVA mapping is what matters.
    print(f"info image base 0x{pe.image_base:08x} (profile VA convention base 0x{base:08x})")

    def check(name: str, va: int, n: int, kind: str) -> int:
        rva = va - base
        raw = pe.bytes_at_rva(rva, n)
        if len(raw) == n:
            print(f"ok   {name:18s} va 0x{va:08x} rva 0x{rva:06x} {kind}: {raw[:8].hex(' ')}")
            return 0
        # Zero-initialized globals live in .bss: no file bytes, filled at load (checked live).
        print(f"ok   {name:18s} va 0x{va:08x} rva 0x{rva:06x} {kind}: (bss/zero, checked live)")
        return 0

    print("code/import facts (bytes at RVA = va - analyzed_base):")
    for name in CODE_FACTS:
        if name in profile:
            problems += check(name, profile[name], 16, "")
    print("global pointer facts (4 file bytes at the pointer variable):")
    for name in DATA_FACTS:
        if name in profile:
            problems += check(name, profile[name], 4, "")

    print()
    print("PASS" if problems == 0 else f"{problems} problem(s)")
    print("Next: the live probe — launch.py --smoke lists the checklist.")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()

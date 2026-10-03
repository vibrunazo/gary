"""Shared reader for adapters/scr_bridge/src/scr_profile.h (the single source of truth).

The C++ header keeps every constant on one `constexpr uint32_t kName = 0x...;` line so these
tools can verify the same facts the DLL will act on — no duplicated tables.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILE_H = HERE / "src" / "scr_profile.h"

_UINT_RE = re.compile(r"constexpr\s+uint32_t\s+k(\w+)\s*=\s*0x([0-9a-fA-F]+)\s*;")
_STR_RE = re.compile(r'constexpr\s+char\s+k(\w+)\s*\[\]\s*=\s*"([^"]*)"\s*;')


def read_profile(path: Path = PROFILE_H) -> dict:
    text = path.read_text(encoding="utf-8")
    out: dict = {}
    for name, value in _UINT_RE.findall(text):
        out[name] = int(value, 16)
    for name, value in _STR_RE.findall(text):
        out[name] = value
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


class PeFile:
    """Enough PE parsing to map RVAs to file offsets (for offline profile checks)."""

    def __init__(self, path: Path):
        self.data = path.read_bytes()
        if self.data[:2] != b"MZ":
            raise ValueError("not a PE file (no MZ)")
        e_lfanew = int.from_bytes(self.data[0x3C:0x40], "little")
        if self.data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            raise ValueError("not a PE file (no PE header)")
        coff = e_lfanew + 4
        n_sections = int.from_bytes(self.data[coff + 2:coff + 4], "little")
        opt_size = int.from_bytes(self.data[coff + 16:coff + 18], "little")
        opt = coff + 20
        magic = int.from_bytes(self.data[opt:opt + 2], "little")
        if magic != 0x10b:
            raise ValueError(f"not a PE32 (32-bit) image (magic 0x{magic:x})")
        self.image_base = int.from_bytes(self.data[opt + 28:opt + 32], "little")
        self.sections = []
        at = opt + opt_size
        for i in range(n_sections):
            entry = self.data[at + i * 40:at + (i + 1) * 40]
            virtual_size = int.from_bytes(entry[8:12], "little")
            virtual_addr = int.from_bytes(entry[12:16], "little")
            raw_size = int.from_bytes(entry[16:20], "little")
            raw_ptr = int.from_bytes(entry[20:24], "little")
            self.sections.append((virtual_addr, virtual_size, raw_ptr, raw_size))

    def rva_to_offset(self, rva: int) -> int | None:
        for va, vsize, raw, rawsize in self.sections:
            if va <= rva < va + max(vsize, rawsize):
                return raw + (rva - va)
        return None

    def bytes_at_rva(self, rva: int, n: int) -> bytes:
        off = self.rva_to_offset(rva)
        if off is None:
            return b""
        return self.data[off:off + n]

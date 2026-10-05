"""Which Gary is playing, exactly: announced in the game chat at the start of every game, so a
replay alone says which version, code revision and models played it."""

from __future__ import annotations

import functools
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@functools.lru_cache(maxsize=1)
def git_revision() -> str:
    """Short commit hash, with '+' if tracked files have uncommitted changes; 'unknown' outside git.
    Asked once per process (each ask runs git twice)."""
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                             text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=REPO_ROOT, timeout=10).returncode != 0
        return (rev + ("+" if dirty else "")) or "unknown"
    except Exception:  # noqa: BLE001 - no git, not a checkout: still play
        return "unknown"


def announcement(version: str, style: int | None = None, models: dict[str, str] | None = None) -> list[str]:
    """Chat lines (each under the game's 80 characters) saying which Gary this is."""
    lines = [f"Gary {version} is on (git {git_revision()}" + (f", style {style})" if style is not None else ")")]
    for name, path in (models or {}).items():
        lines.append(f"{name} model: {Path(path).parent.name}"[:79])
    return lines

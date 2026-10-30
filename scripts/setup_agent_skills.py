"""Expose .agent/skills to Claude Code through the .claude/skills link.

Claude Code only discovers project skills under .claude/skills. We keep the
canonical files in .agent/skills and create a directory link at .claude/skills
so both layouts stay in sync. Safe to run repeatedly.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".agent" / "skills"
LINK = ROOT / ".claude" / "skills"


def is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(os.path, "isjunction", None)
    return bool(is_junction and is_junction(path))


def resolve(path: Path) -> Path:
    try:
        return Path(os.path.realpath(path))
    except OSError:
        return path


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    LINK.parent.mkdir(parents=True, exist_ok=True)

    if is_link(LINK):
        current = resolve(LINK)
        if current == resolve(TARGET):
            print(f"already linked: {LINK} -> {TARGET}")
            return 0
        print(
            f"{LINK} is a link to {current}, expected {TARGET}.\n"
            f"Remove it and run this script again.",
            file=sys.stderr,
        )
        return 1

    if LINK.exists():
        print(
            f"{LINK} exists and is not a link; refusing to overwrite.\n"
            f"Move its contents into {TARGET} first.",
            file=sys.stderr,
        )
        return 1

    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(LINK), str(TARGET)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout, result.stderr, file=sys.stderr)
            return result.returncode
    else:
        LINK.symlink_to(TARGET, target_is_directory=True)

    print(f"linked: {LINK} -> {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

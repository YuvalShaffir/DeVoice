"""Fail if a tracked folder lacks AGENTS.md or the root lacks ARCHITECTURE.md/CONTEXT.md.

Warn (no failure) when files passed on argv changed without their folder's AGENTS.md.
"""

import subprocess
import sys
from pathlib import PurePosixPath

ROOT_DOCS = ["AGENTS.md", "ARCHITECTURE.md", "CONTEXT.md"]
AGENTS = "AGENTS.md"


def tracked_files() -> list[PurePosixPath]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [PurePosixPath(line) for line in out.splitlines() if line]


def main(changed: list[str]) -> int:
    files = tracked_files()
    present = {str(f) for f in files}
    dirs = {str(f.parent) for f in files if f.parent != PurePosixPath(".")}

    missing = [d + "/" + AGENTS for d in sorted(dirs) if f"{d}/{AGENTS}" not in present]
    missing += [d for d in ROOT_DOCS if d not in present]
    for path in missing:
        print(f"missing: {path}")

    touched = {
        str(PurePosixPath(c).parent) for c in changed if PurePosixPath(c).name != AGENTS
    }
    updated = {
        str(PurePosixPath(c).parent) for c in changed if PurePosixPath(c).name == AGENTS
    }
    for d in sorted(touched - updated - {"."}):
        print(f"warning: {d}/ changed but {d}/{AGENTS} did not")

    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

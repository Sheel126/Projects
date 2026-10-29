"""The lockbox is opened once, and only after the rules are on record (lesson 04 §5).

Two guards, both checked before any lockbox bar is read:

1. The pre-registration file is tracked by git and has no uncommitted changes, so the criteria
   provably predate the result.
2. No `lockbox_opened.json` exists yet. The run writes it first, before computing anything, so a
   crash halfway still counts as an opening.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


class LockboxRefused(RuntimeError):
    pass


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def check_preregistration(path: Path) -> str:
    """Return the commit that last touched the pre-registration; refuse if it is not committed."""
    cwd = path.parent
    if _git(["ls-files", "--error-unmatch", path.name], cwd).returncode != 0:
        raise LockboxRefused(f"{path} is not committed: the rules must be on record first")
    if _git(["diff", "--quiet", "HEAD", "--", path.name], cwd).returncode != 0:
        raise LockboxRefused(f"{path} has uncommitted changes: commit them, or revert them")
    return _git(["log", "-1", "--format=%H", "--", path.name], cwd).stdout.strip()


def open_once(marker: Path, preregistration: Path, details: dict) -> dict:
    commit = check_preregistration(preregistration)
    if marker.exists():
        raise LockboxRefused(f"the lockbox was already opened ({marker}); it is not unseen data "
                             "any more and cannot be re-run")
    record = {"opened_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "preregistration_commit": commit, **details}
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(record, indent=1, default=str))
    return record

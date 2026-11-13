# offtarget · offtarget/stamp.py
# v0.1 · 13NOV2026
#
# Practical: run_stamp() returns what a raw run file should say about its own birth:
# the time the run started (UTC), a hash of the registration it ran under, and the
# commit of the code that ran it. The three registered runners put it in their output.
#
# Philosophical: the registered runs already in results/ carry none of this. Their
# order (freeze first, run second) is asserted by a commit history, and a cold reader
# pointed out two things about that. The history is ours, so the times are ours. And
# the freeze of registration 003 shares a second with another commit, which looks odd
# even though it is only two commits made by one command. A raw file that carried its
# own start time and the hash of its rules would have answered both on sight.
#
# This does not make the order provable. The clock is still this machine's and the
# file is still written by the party being checked. It makes the claim specific: this
# run says it started at this time, under a registration with this hash, on this
# commit. A specific claim can be checked against a registration published before the
# run. A vague one cannot be checked against anything.
from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
from pathlib import Path


def sha256_text(path: Path) -> str:
    """Hash of a text file with its line endings normalised, the same way the freeze log is made."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _git(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def run_stamp(root: Path, prereg: str) -> dict:
    """Start time, registration hash and code commit for a run that is about to begin."""
    reg = root / prereg
    if not reg.is_file():
        raise RuntimeError(f"WIRING FAILURE: no registration at {reg}. A registered run cannot start without one.")
    dirty = _git(root, "status", "--porcelain")
    return {
        "started_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "registration": prereg,
        "registration_sha256": sha256_text(reg),
        "commit": _git(root, "rev-parse", "HEAD"),                 # None when this is not a git checkout
        "uncommitted_changes": None if dirty is None else bool(dirty),
    }

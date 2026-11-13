# offtarget · tests/test_stamp_and_gate.py
# v0.1 · 13NOV2026
#
# Practical: two small guards added after a cold read. The stamp a run writes about its
# own birth, and the gate that stops a tool reading outside files unless Python is in
# isolated mode.
# Philosophical: both exist because a sentence in the documentation was true only by
# habit. "Every tool runs under -I" and "each run was frozen first" were things the
# author did, and nothing in the code would have noticed if the next worker did not.
# These tests are the noticing.
import subprocess
import sys
from pathlib import Path

import pytest

from offtarget import isolation, stamp

ROOT = Path(__file__).resolve().parents[1]


def test_the_stamp_names_the_registration_by_hash(tmp_path):
    (tmp_path / "prereg").mkdir()
    reg = tmp_path / "prereg" / "009-test.md"
    reg.write_bytes(b"**Status: FROZEN**\nthreshold = 5\n")
    s = stamp.run_stamp(tmp_path, "prereg/009-test.md")
    assert s["registration"] == "prereg/009-test.md"
    assert s["registration_sha256"] == stamp.sha256_text(reg)
    assert s["started_utc"].endswith("+00:00")
    assert s["commit"] is None and s["uncommitted_changes"] is None      # a bare folder is not a git checkout, and the stamp says so


def test_the_stamp_changes_when_the_registration_changes(tmp_path):
    (tmp_path / "prereg").mkdir()
    reg = tmp_path / "prereg" / "009-test.md"
    reg.write_bytes(b"threshold = 5\n")
    before = stamp.run_stamp(tmp_path, "prereg/009-test.md")["registration_sha256"]
    reg.write_bytes(b"threshold = 10\n")
    assert stamp.run_stamp(tmp_path, "prereg/009-test.md")["registration_sha256"] != before


def test_the_stamp_hash_ignores_line_endings_like_the_freeze_log(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_bytes(b"one\ntwo\n")
    b.write_bytes(b"one\r\ntwo\r\n")
    assert stamp.sha256_text(a) == stamp.sha256_text(b)


def test_a_run_cannot_be_stamped_without_its_registration(tmp_path):
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        stamp.run_stamp(tmp_path, "prereg/missing.md")


def test_the_gate_refuses_when_python_is_not_isolated():
    """pytest itself is not started with -I, so the gate must refuse here."""
    assert not sys.flags.isolated
    with pytest.raises(SystemExit, match="WIRING FAILURE"):
        isolation.require_isolated("offtarget.diff")


def test_a_tool_that_reads_outside_files_stops_without_dash_I_and_starts_with_it():
    """The real thing, in a subprocess: the same command with and without -I."""
    without = subprocess.run([sys.executable, "-m", "offtarget.sidecar", "--base", "x", "--edited", "y", "--out", "z"],
                             capture_output=True, text=True, cwd=ROOT)
    assert without.returncode != 0 and "isolated mode" in without.stderr
    with_i = subprocess.run([sys.executable, "-I", "-m", "offtarget.sidecar", "--base", "x", "--edited", "y", "--out", "z"],
                            capture_output=True, text=True, cwd=ROOT)
    # It gets past the gate and fails on the folder that does not exist, which is the next honest failure.
    assert "isolated mode" not in with_i.stderr and "no snapshot folder" in with_i.stderr


def test_every_entry_point_that_takes_an_outside_path_has_the_gate():
    """A new tool that reads a download and forgets the gate should fail this, not ship."""
    reads_outside = ("--base", "--edited", "--eval", "--edit-dir", "--logs", "--tokenizer")
    missing = []
    for path in sorted((ROOT / "offtarget").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if any(f'"{flag}"' in text for flag in reads_outside) and "require_isolated" not in text:
            missing.append(path.name)
    assert not missing, f"these tools take a path to outside files and never call the gate: {missing}"

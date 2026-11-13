# offtarget · tests/test_ghostbeat_registered.py
# v0.1 · 11NOV2026
#
# Practical: the parts of the registered runner that need no model. The seal on the
# held-out labels, the sizes promised in the registration, and that the runner and
# the verdict agree on what the arms are called.
# Philosophical: the seal is the one piece of this project that protects me from
# myself, so it gets the test I would give a lock: try the door before trusting it.
from pathlib import Path

from offtarget import ghostbeat as gb
from offtarget import ghostbeat_registered as reg
from offtarget import ghostbeat_verdict as gv


def _root(tmp_path: Path, status: str) -> Path:
    (tmp_path / "prereg").mkdir(parents=True)
    (tmp_path / reg.PREREG).write_text(f"# Pre-registration 002\n\n*Flame*\n\n**Status: {status}**\n\nbody\n", encoding="utf-8")
    return tmp_path


def test_the_seal_opens_only_on_the_word_frozen(tmp_path):
    assert not reg.frozen(_root(tmp_path / "a", "DRAFT for review. Not binding yet."))
    assert reg.frozen(_root(tmp_path / "b", "FROZEN at this commit, 12 NOV 2026."))
    # the word appearing somewhere else in the file does not count
    root = _root(tmp_path / "c", "DRAFT. It becomes binding when this line says FROZEN.")
    assert not reg.frozen(root)


def test_held_out_labels_were_never_used_before():
    seen = {gb.LABEL, "PAC, isolated", "pause, 2.4 s"}          # the first look and the competence check
    assert len(set(reg.HELD_OUT)) == 5 and not set(reg.HELD_OUT) & seen


def test_the_run_is_the_size_the_registration_promises():
    lists = [gb.make_case(n, "list", "bare", s, lab) for lab in reg.HELD_OUT for n in reg.LIST_SIZES for s in range(reg.LIST_SEEDS)]
    twins = [gb.make_case(n, v, "id", s, lab) for lab in reg.HELD_OUT for n in reg.TWIN_SIZES for s in range(reg.TWIN_SEEDS) for v in gb.VARIANTS]
    assert (len(lists), len(twins)) == (280, 160)
    assert len({c.case_id for c in lists + twins}) == 440                      # no two logs share a name
    assert len({c.prompt for c in lists}) == 280                               # and no two lists are the same log
    assert all(len(c.rows) == len(c.truth) for c in lists)                     # a plain list has no resent packet
    assert reg.LIST_SIZES[0] <= gv.S_MIN_EVENTS and reg.LIST_SIZES[-1] == gv.S_MAX_EVENTS


def test_runner_and_verdict_use_the_same_arm_names():
    needed = set(gv.DOSES) | set(gv.RANDOM) | set(gv.MATCHED) | {"dose:-2", gv.PUSH_IN, "only:15", "only:19"}
    assert needed == set(reg.ARMS) and len(reg.ARMS) == 20
    assert set(reg.TWIN_ARMS) == {"dose:0", "dose:6"}

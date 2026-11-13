# offtarget · tests/test_default_verdict.py
# v0.1 · 11NOV2026
#
# Practical: the rules of prereg/003 on planted worlds. One where the default
# setting matches the edit, one where the edit is well ahead, one in between, one
# too small to read, and the same for the edit's effect with thinking off.
# Philosophical: the sentence under test is the one I would most like to be true,
# which is the best reason to build the worlds where it is false first.
import pytest

from offtarget import default_verdict as dv


def _run(unedited: list[int], edited: list[int], kinds=("finished", "finished"), block: int = 100) -> dict:
    """A run whose two arms got these problems right (1) or wrong (0), in blocks."""
    ids = [f"p{i}" for i in range(max(len(unedited), len(edited)))]
    blocks = {}
    for arm, marks, kind in (("0.0", unedited, kinds[0]), ("6.0", edited, kinds[1])):
        for b in range(0, len(marks), block):
            blocks[f"{arm}/block{b // block}"] = {"rows": [{"id": ids[i], "correct": bool(marks[i]), "kind": kind, "tokens": 700}
                                                           for i in range(b, min(b + block, len(marks)))]}
    return {"prereg": "prereg/003", "problem_ids": ids, "blocks": blocks}


def _theirs(n: int, right_of_four: int) -> dict[str, list[int]]:
    return {f"p{i}": [1] * right_of_four + [0] * (4 - right_of_four) for i in range(n)}


def _marks(n: int, share: float) -> list[int]:
    """Evenly spread 1s so that the share right is exact and independent of the block."""
    out, acc = [], 0.0
    for _ in range(n):
        acc += share
        out.append(1 if acc >= 1 else 0)
        acc -= out[-1]
    return out


def test_paired_interval_is_centred_and_refuses_a_single_pair():
    p = dv.paired([1, 0, 1, 0])
    assert p["difference"] == 0.5 and p["interval"][0] < 0.5 < p["interval"][1]
    with pytest.raises(ValueError, match="WIRING FAILURE"):
        dv.paired([1])


def test_only_problems_answered_under_both_arms_are_read():
    run = _run(_marks(500, 0.5), _marks(300, 0.5))            # the edited arm stopped after three blocks
    assert len(dv.complete(run)) == 300
    v = dv.judge(run, _theirs(500, 2), _theirs(500, 0))
    assert v["problems_complete"] == 300 and v["Q1"]["n"] == 300 and v["published_unedited_thinking_accuracy"] == 0.0


def test_q1_as_good_when_the_default_setting_matches_the_edit():
    run = _run(_marks(500, 0.5), _marks(500, 0.5))
    v = dv.q1(dv.per_problem(run)["0.0"], _theirs(500, 2), dv.complete(run))          # theirs: 50% on every problem
    assert v["verdict"] == "AS GOOD OR BETTER" and v["difference"] == pytest.approx(0.0)
    assert v["default_mode_accuracy"] == 0.5 and v["published_edited_thinking_accuracy"] == 0.5


def test_q1_says_so_when_the_edit_is_ahead_and_when_it_cannot_tell():
    behind = _run(_marks(500, 0.3), _marks(500, 0.3))                                   # 20 points behind
    assert dv.q1(dv.per_problem(behind)["0.0"], _theirs(500, 2), dv.complete(behind))["verdict"] == "THE EDIT IS AHEAD"
    middling = _run(_marks(500, 0.43), _marks(500, 0.43))                               # 7 points behind: neither side of the line
    v = dv.q1(dv.per_problem(middling)["0.0"], _theirs(500, 2), dv.complete(middling))
    assert v["verdict"] == "INCONCLUSIVE" and v["interval"][0] < dv.Q1_LOWER < dv.Q1_POINT < v["interval"][1]


def test_q1_and_q2_refuse_a_run_that_is_too_small():
    small = _run(_marks(200, 0.5), _marks(200, 0.5))
    assert dv.q1(dv.per_problem(small)["0.0"], _theirs(200, 2), dv.complete(small))["verdict"] == "NOT TESTABLE"
    assert dv.q2(dv.per_problem(small)["0.0"], dv.per_problem(small)["6.0"], dv.complete(small))["verdict"] == "NOT TESTABLE"


def test_q1_fails_loudly_when_a_problem_is_missing_from_the_published_scores():
    run = _run(_marks(400, 0.5), _marks(400, 0.5))
    with pytest.raises(KeyError, match="WIRING FAILURE"):
        dv.q1(dv.per_problem(run)["0.0"], _theirs(399, 2), dv.complete(run))


def test_q2_reads_help_harm_and_no_difference():
    base = _marks(500, 0.4)
    better = [1 if (m or i % 5 == 0) else 0 for i, m in enumerate(base)]                # the edit rescues some and loses none
    v = dv.q2(dv.per_problem(_run(base, better))["0.0"], dv.per_problem(_run(base, better))["6.0"], [f"p{i}" for i in range(500)])
    assert v["verdict"] == "THE EDIT HELPS IN THE DEFAULT MODE" and v["only_unedited_right"] == 0 and v["only_edited_right"] > 0
    worse = [0 if i % 4 == 0 else m for i, m in enumerate(base)]
    run = _run(base, worse)
    assert dv.q2(dv.per_problem(run)["0.0"], dv.per_problem(run)["6.0"], dv.complete(run))["verdict"] == "THE EDIT HURTS IN THE DEFAULT MODE"
    swapped = [base[(i + 1) % 500] for i in range(500)]                                 # same score, different problems
    run = _run(base, swapped)
    v = dv.q2(dv.per_problem(run)["0.0"], dv.per_problem(run)["6.0"], dv.complete(run))
    assert v["verdict"] == "NO DIFFERENCE DETECTED" and v["only_unedited_right"] == v["only_edited_right"] > 0


def test_endings_count_each_arm_and_how_each_problem_moved():
    run = _run(_marks(300, 0.5), _marks(300, 0.5), kinds=("loop", "whitespace"))
    e = dv.endings(dv.per_problem(run), dv.complete(run))
    assert e["0.0"]["loop"] == 300 and e["6.0"]["whitespace"] == 300 and e["unedited_to_edited"] == {"loop -> whitespace": 300}


def test_a_stray_arm_or_a_repeated_problem_is_a_wiring_failure():
    run = _run(_marks(100, 0.5), _marks(100, 0.5))
    run["blocks"]["1.0/block0"] = {"rows": []}
    with pytest.raises(KeyError, match="WIRING FAILURE"):
        dv.per_problem(run)
    twice = _run(_marks(100, 0.5), _marks(100, 0.5))
    twice["blocks"]["0.0/block9"] = twice["blocks"]["0.0/block0"]
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        dv.per_problem(twice)

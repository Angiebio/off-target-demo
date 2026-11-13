# offtarget · tests/test_default_report.py
# v0.1 · 12NOV2026
#
# Practical: the descriptive tables of prereg/003 on a small planted run where
# every count can be checked by hand: two blocks of four problems, known endings,
# known marks, and a pilot that got a different pair of problems right.
# Philosophical: a table nobody checked is a rumour with borders. These counts are
# small enough to do on fingers, which is the point.
import pytest

from offtarget import default_report as dr


def _row(i, kind, correct):
    return {"id": i, "kind": kind, "correct": correct, "tokens": 8192 if kind in ("loop", "long") else 1000, "boxed": correct, "onset": None}


IDS = [f"test/algebra/{i}.json" for i in range(4)] + [f"test/geometry/{i}.json" for i in range(4)]
#                    unedited                edited
PLAN = [
    (("finished", True), ("finished", True)),
    (("finished", True), ("long", False)),        # the edit lost this one
    (("loop", False), ("finished", True)),        # and gained this one
    (("loop", False), ("long", False)),
    (("long", False), ("long", False)),
    (("finished", False), ("finished", False)),
    (("loop", False), ("loop", False)),
    (("finished", True), ("finished", True)),
]


def _run(n_edited: int = 8) -> dict:
    blocks = {}
    for b in range(2):
        blocks[f"0.0/block{b}"] = {"rows": [_row(IDS[i], *PLAN[i][0]) for i in range(4 * b, 4 * b + 4)]}
        if 4 * b + 4 <= n_edited:
            blocks[f"6.0/block{b}"] = {"rows": [_row(IDS[i], *PLAN[i][1]) for i in range(4 * b, 4 * b + 4)]}
    return {"prereg": "prereg/003", "block": 4, "problem_ids": IDS, "blocks": blocks}


EDITED_PUB = {i: [1, 1, 0, 0] for i in IDS}                       # 50% on every problem
UNEDITED_PUB = {i: [1, 0, 0, 0] if i.startswith("test/algebra") else [0, 0, 0, 0] for i in IDS}


def test_the_four_accuracies_and_the_blocks():
    rep = dr.report(_run(), EDITED_PUB, UNEDITED_PUB)
    f = rep["four_accuracies"]
    assert f["n"] == 8 and f["unedited"]["thinking_off_ours"] == 3 / 8 and f["edited"]["thinking_off_ours"] == 3 / 8
    assert f["edited"]["thinking_on_published"] == 0.5 and f["unedited"]["thinking_on_published"] == 0.125
    assert rep["by_block"]["block0"] == {"n": 4, "unedited_right": 2, "edited_right": 2,
                                         "published_edited_thinking": 0.5, "published_unedited_thinking": 0.25}
    assert rep["by_block"]["block1"]["unedited_right"] == 1 and rep["by_block"]["block1"]["published_unedited_thinking"] == 0.0


def test_endings_and_how_they_moved():
    rep = dr.report(_run(), EDITED_PUB, UNEDITED_PUB)
    e = rep["by_ending"]
    assert e["0.0"]["finished"] == {"n": 4, "right": 3} and e["0.0"]["loop"] == {"n": 3, "right": 0} and e["0.0"]["long"] == {"n": 1, "right": 0}
    assert e["6.0"]["finished"] == {"n": 4, "right": 3} and e["6.0"]["loop"] == {"n": 1, "right": 0} and e["6.0"]["long"] == {"n": 3, "right": 0}
    m = rep["moves"]
    assert m["loop -> finished"] == {"n": 1, "right_unedited": 0, "right_edited": 1, "gained": 1, "lost": 0}
    assert m["finished -> long"] == {"n": 1, "right_unedited": 1, "right_edited": 0, "gained": 0, "lost": 1}
    assert m["finished -> finished"]["n"] == 3 and m["finished -> finished"]["right_edited"] == 2
    assert sum(c["n"] for c in m.values()) == 8 and sum(c["gained"] for c in m.values()) == sum(c["lost"] for c in m.values()) == 1


def test_subjects_come_from_the_problem_id():
    rep = dr.report(_run(), EDITED_PUB, UNEDITED_PUB)
    assert set(rep["by_subject"]) == {"algebra", "geometry"}
    assert rep["by_subject"]["algebra"]["unedited_right"] == 2 and rep["by_subject"]["geometry"]["edited_right"] == 1
    with pytest.raises(ValueError, match="WIRING FAILURE"):
        dr.subject("p7")


def test_the_pilot_is_set_beside_its_fresh_draw():
    run = _run()
    run["problem_ids"] = IDS                                          # all eight are "the first hundred" here
    was = [True, False, True, False, False, False, False, False]       # the pilot got problems 0 and 2
    pilot = {"problem_ids": IDS, "doses": {"0.0": {"per_problem": [{"id": i, "correct": c} for i, c in zip(IDS, was)]}}}
    p = dr.report(run, EDITED_PUB, UNEDITED_PUB, pilot)["pilots_hundred"]
    assert p["pilot_unedited_right"] == 2 and p["unedited_right"] == 3
    assert (p["right_both_times"], p["right_in_the_pilot_only"], p["right_this_time_only"]) == (1, 1, 2)
    pilot["problem_ids"] = IDS[::-1]
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        dr.report(run, EDITED_PUB, UNEDITED_PUB, pilot)


def test_only_problems_answered_under_both_arms_are_tabulated():
    rep = dr.report(_run(n_edited=4), EDITED_PUB, UNEDITED_PUB)        # the edited arm stopped after one block
    assert rep["problems_complete"] == 4 and list(rep["by_block"]) == ["block0"]
    assert sum(c["n"] for c in rep["moves"].values()) == 4
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        dr.report(_run(n_edited=0), EDITED_PUB, UNEDITED_PUB)

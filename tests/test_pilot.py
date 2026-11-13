# offtarget · tests/test_pilot.py
# v0.1 · 11NOV2026
#
# Practical: the pre-registered decision rules on made-up run results, on both
# sides of each threshold.
# Philosophical: a rule fixed in advance is only worth something if the code that
# applies it cannot be argued with afterwards. These tests are the argument, had
# early, while nobody yet cares which way the real numbers fall.
import json

import pytest

from offtarget.pilot import subset_accuracy, verdict_a, verdict_b, wilson


def _dose(l0, l1, l6, n=32):
    return {"doses": {a: {"n": n, "loop_share": share} for a, share in (("0.0", l0), ("1.0", l1), ("6.0", l6))}}


def test_wilson_is_sane_at_the_edges():
    lo, hi = wilson(0, 32)
    assert lo == 0.0 and 0.05 < hi < 0.15
    lo, hi = wilson(32, 32)
    assert hi == 1.0 and 0.85 < lo < 0.95
    lo, hi = wilson(50, 100)
    assert lo == pytest.approx(0.404, abs=0.005) and hi == pytest.approx(0.596, abs=0.005)
    with pytest.raises(ValueError):
        wilson(0, 0)


def test_run_a_passes_on_a_big_drop_and_fails_on_a_small_one():
    good = verdict_a(_dose(0.90, 0.60, 0.10))
    assert good["pass"] is True
    assert good["predictions"] == {"alpha0_at_least_70pct": True, "alpha6_at_most_30pct": True,
                                   "alpha1_strictly_between": True}
    bad = verdict_a(_dose(0.50, 0.40, 0.25))
    assert bad["pass"] is False
    assert bad["predictions"]["alpha0_at_least_70pct"] is False


def test_run_a_notices_when_alpha_one_is_not_between():
    v = verdict_a(_dose(0.90, 0.95, 0.10))
    assert v["pass"] is True and v["predictions"]["alpha1_strictly_between"] is False


def test_run_a_without_the_anchor_doses_is_loud():
    with pytest.raises(KeyError, match="WIRING FAILURE"):
        verdict_a({"doses": {"1.0": {"n": 4, "loop_share": 0.5}}})


def _logs(root, edited_correct, base_correct):
    for model, rows in (("p50c", edited_correct), ("unedited", base_correct)):
        part = root / model / "parts" / "math500_s0of1"
        part.mkdir(parents=True)
        (part / "math500_per_problem.json").write_text(
            json.dumps([{"id": f"p{i}", "correct": c} for i, c in enumerate(rows)]), encoding="utf-8")


def _default(acc, n=4):
    return {"problem_ids": [f"p{i}" for i in range(n)],
            "doses": {"0.0": {"n": n, "accuracy": acc, "finished": n, "loop": 0, "whitespace": 0, "long": 0,
                              "mean_tokens": 300.0}}}


def test_run_b_reports_parity_inside_the_margin(tmp_path):
    _logs(tmp_path, [[1, 1], [1, 0], [0, 0], [0, 0]], [[0, 0]] * 4)      # edited 37.5%
    v = verdict_b(_default(0.50), tmp_path)
    assert v["published_edited_thinking_same_problems"]["accuracy"] == 0.375
    assert v["report"].startswith("the documented default setting does about as well")


def test_run_b_reports_the_gap_outside_the_margin(tmp_path):
    _logs(tmp_path, [[1, 1], [1, 1], [1, 0], [0, 0]], [[0, 0]] * 4)      # edited 62.5%
    v = verdict_b(_default(0.25), tmp_path)
    assert v["edited_minus_default"] == pytest.approx(0.375)
    assert v["report"] == "the edit has an advantage over the default setting"


def test_subset_with_unknown_problem_is_loud():
    with pytest.raises(KeyError, match="WIRING FAILURE"):
        subset_accuracy({"a": [1]}, ["a", "b"])

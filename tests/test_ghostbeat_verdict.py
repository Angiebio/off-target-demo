# offtarget · tests/test_ghostbeat_verdict.py
# v0.1 · 11NOV2026
#
# Practical: every rule in prereg/002, fed outcomes planted on each side of its
# line. A world where the edit drops events, a world where it does nothing, a world
# where a random shove does just as much, and a world too small to say anything.
# Philosophical: a decision rule that cannot say "no" is a decoration. Each test
# here builds the result I would least like to see and checks the clerk reads it
# out anyway.
import pytest

from offtarget import ghostbeat_verdict as gv

ARMS = list(gv.DOSES) + ["dose:-2", "dose:-6", "only:15", "only:19"] + list(gv.RANDOM) + list(gv.MATCHED)
PUSH = {"dose:6": {"L15": 2.0, "L19": 3.0}, **{a: {"L15": 0.4, "L19": 0.6} for a in gv.RANDOM},
        **{a: {"L15": 1.9, "L19": 2.9} for a in gv.MATCHED}}


def _list(n, base_exact=True, short_at=(), long_at=(), stop=None):
    """One list record. short_at / long_at name the arms that drop or add a line."""
    stop = stop or {}
    arms = {}
    for a in ARMS:
        entries = n - 2 if a in short_at else n + 3 if a in long_at else n
        if a == "dose:0" and not base_exact:
            entries = n - 1
        arms[a] = {"entries": entries, "outcome": "exact" if entries == n else "dropped" if entries < n else "ghost",
                   "p_stop": [stop.get(a, 0.05)] * n}
    return {"case": f"x{n}", "label": "x", "n": n, "arms": arms}


def _world(n_logs=60, **kw):
    return [_list(4 + i % 5, **kw) for i in range(n_logs)]


RISING = {"dose:0": 0.05, "dose:1": 0.08, "dose:2": 0.15, "dose:4": 0.3, "dose:6": 0.5, "dose:-2": 0.03, "dose:-6": 0.01}


def _run(lists, twins=None, delivered=PUSH):
    return {"prereg": "prereg/002", "lists": lists, "twins": twins or [], "delivered": delivered}


def test_the_analysis_set_is_chosen_by_the_unedited_model_alone():
    lists = [_list(3), _list(4), _list(8), _list(9), _list(5, base_exact=False), _list(6, short_at=("dose:6",))]
    assert [r["n"] for r in gv.analysis_set(lists)] == [4, 8, 6]


def test_q1_supported_when_the_edit_drops_events_often():
    lists = _world(60, short_at=("dose:6",))[:30] + _world(60)[:30]            # half the set comes up short
    v = gv.q1(gv.analysis_set(lists))
    assert v["verdict"] == "SUPPORTED" and v["k"] == 30 and v["n"] == 60


def test_q1_not_supported_when_nothing_happens_and_inconclusive_in_between():
    assert gv.q1(gv.analysis_set(_world(60)))["verdict"] == "NOT SUPPORTED"
    some = _world(60, short_at=("dose:6",))[:9] + _world(60)[:51]                # 15%: above nothing, below the bar
    assert gv.q1(gv.analysis_set(some))["verdict"] == "INCONCLUSIVE"


def test_q1_refuses_a_set_that_is_too_small():
    assert gv.q1(gv.analysis_set(_world(20, short_at=("dose:6",))))["verdict"] == "NOT TESTABLE"


def test_q2_needs_a_rise_in_behaviour_and_in_the_stop_probability():
    lists = _world(60, short_at=("dose:4", "dose:6"), stop=RISING)
    assert gv.q2(gv.analysis_set(lists), lists)["verdict"] == "SUPPORTED"
    flat = _world(60, short_at=("dose:1", "dose:2", "dose:4", "dose:6"), stop=RISING)      # as bad at dose 1 as at 6
    assert gv.q2(gv.analysis_set(flat), flat)["verdict"] == "NOT SUPPORTED"
    dip = dict(RISING, **{"dose:2": 0.07})                                                   # p(stop) falls at one step
    wobble = _world(60, short_at=("dose:4", "dose:6"), stop=dip)
    assert gv.q2(gv.analysis_set(wobble), wobble)["verdict"] == "NOT SUPPORTED"


def test_q3_tells_a_special_direction_from_damage_in_the_right_place():
    special = _world(60, short_at=("dose:6",))
    assert gv.q3(gv.analysis_set(special), PUSH, "SUPPORTED")["verdict"] == "THE DIRECTION MATTERS"
    one = _world(60, short_at=("dose:6", "matched:3"))                                       # one direction in eight is allowed
    assert gv.q3(gv.analysis_set(one), PUSH, "SUPPORTED")["verdict"] == "THE DIRECTION MATTERS"
    damage = _world(60, short_at=("dose:6",) + gv.MATCHED[:4])                               # half of them do as much
    v = gv.q3(gv.analysis_set(damage), PUSH, "SUPPORTED")
    assert v["verdict"] == "DAMAGE IN THE RIGHT PLACE" and v["matched_directions_doing_at_least_half_as_much"] == 4
    mixed = _world(60, short_at=("dose:6", "matched:0", "matched:1"))                        # two of eight
    assert gv.q3(gv.analysis_set(mixed), PUSH, "SUPPORTED")["verdict"] == "INCONCLUSIVE"
    # the verdict rests on the push-matched arms. The weaker, usual control is reported and does not decide.
    usual_only = _world(60, short_at=("dose:6",) + gv.RANDOM)
    v = gv.q3(gv.analysis_set(usual_only), PUSH, "SUPPORTED")
    assert v["verdict"] == "THE DIRECTION MATTERS" and v["as_usually_specified"]["mean"] == 1.0 and v["of"] == 8
    assert v["as_usually_specified"]["push_relative_to_edit"]["L15"] == pytest.approx(0.2)
    assert gv.q3(gv.analysis_set(special), PUSH, "INCONCLUSIVE")["verdict"] == "NOT READ"


def test_q3_says_when_the_control_pushes_too_softly_to_count():
    weak = dict(PUSH, **{a: {"L15": 0.4, "L19": 2.9} for a in gv.MATCHED})
    v = gv.q3(gv.analysis_set(_world(60, short_at=("dose:6",))), weak, "SUPPORTED")
    assert v["control_is_weak"] and v["matched"]["push_relative_to_edit"]["L15"] == pytest.approx(0.2)
    # a soft control would otherwise read as "the direction matters", the answer I would most like to hear
    assert v["verdict"] == "CONTROL FAILED"
    fair = gv.q3(gv.analysis_set(_world(60, short_at=("dose:6",))), PUSH, "SUPPORTED")
    assert not fair["control_is_weak"] and fair["verdict"] == "THE DIRECTION MATTERS"


def test_q4_wants_the_stop_probability_to_fall_and_the_unedited_drops_to_heal():
    # 20 lists where the unedited model drops a line, and pushing the direction in brings the line back
    healed = _world(40, stop=RISING) + [_list(5, base_exact=False, stop=RISING) for _ in range(20)]
    v = gv.q4(gv.analysis_set(healed), healed)
    assert v["verdict"] == "SUPPORTED" and v["unedited_short"] == 20 and v["no_longer_short"]["share"] == 1.0
    # the same lists, but the push-in leaves them short
    stuck = _world(40, stop=RISING) + [_list(5, base_exact=False, short_at=("dose:-6",), stop=RISING) for _ in range(20)]
    assert gv.q4(gv.analysis_set(stuck), stuck)["verdict"] == "NOT SUPPORTED"
    # too few unedited drops to say anything about behaviour: the mechanism half is read alone, and says so
    few = _world(40, stop=RISING) + [_list(5, base_exact=False, stop=RISING) for _ in range(3)]
    assert gv.q4(gv.analysis_set(few), few)["verdict"] == "MECHANISM ONLY, SUPPORTED"
    flat = dict(RISING, **{"dose:-6": 0.2})                                                   # p(stop) goes up instead of down
    wrong = _world(40, stop=flat)
    assert gv.q4(gv.analysis_set(wrong), wrong)["verdict"] == "NOT SUPPORTED"


def _twin(base, edited):
    return {"case": "t", "label": "x", "n": 4, "variant": "second", "arms": {"dose:0": {"entries": 5, "outcome": base}, "dose:6": {"entries": 5, "outcome": edited}}}


def test_q5_reads_harm_no_harm_and_too_small():
    clean = [_twin("exact", "exact")] * 78 + [_twin("exact", "dropped")] * 2 + [_twin("ghost", "exact")] * 5
    v = gv.q5(clean)
    assert v["verdict"] == "NO HARM AT THIS SIZE" and v["n"] == 80 and v["fixed_by_the_edit"] == 5
    assert gv.q5([_twin("exact", "exact")] * 50 + [_twin("exact", "dropped")] * 30)["verdict"] == "HARM"
    assert gv.q5([_twin("exact", "exact")] * 34 + [_twin("exact", "dropped")] * 6)["verdict"] == "INCONCLUSIVE"
    assert gv.q5([_twin("exact", "exact")] * 12)["verdict"] == "NOT TESTABLE"


def test_judge_puts_it_together_and_wilson_refuses_nothing():
    lists = _world(60, short_at=("dose:4", "dose:6"), long_at=("dose:-6",), stop=RISING)
    v = gv.judge(_run(lists, [_twin("exact", "exact")] * 40))
    assert (v["Q1"]["verdict"], v["Q2"]["verdict"], v["Q3"]["verdict"], v["Q4"]["verdict"], v["Q5"]["verdict"]) == (
        "SUPPORTED", "SUPPORTED", "THE DIRECTION MATTERS", "MECHANISM ONLY, SUPPORTED", "NO HARM AT THIS SIZE")
    assert v["analysis_set"] == 60 and set(v["Q6"]) == {"only:15", "only:19", "dose:6"}
    with pytest.raises(ValueError, match="WIRING FAILURE"):
        gv.wilson(0, 0)

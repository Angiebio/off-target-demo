# offtarget · tests/test_ghostbeat_report.py
# v0.1 · 11NOV2026
#
# Practical: the descriptive tables of prereg/002, fed a small world where every
# count is known by construction.
# Philosophical: a table nobody checked is a rumour with borders. These are the
# numbers a reader will quote, so each one is planted and then asked for by name.
from offtarget import ghostbeat_report as gr

ARMS = ["dose:0", "dose:6", "matched:0"]


def _list(label, n, entries, stop=0.1):
    """entries: lines written under each arm, in the order of ARMS."""
    arms = {a: {"entries": e, "outcome": "exact" if e == n else "dropped" if e < n else "ghost", "p_stop": [stop] * n}
            for a, e in zip(ARMS, entries)}
    arms["dose:6"]["p_stop"] = [0.4] * n
    return {"case": f"{label}-{n}", "label": label, "n": n, "arms": arms}


def _twin(variant, base, edited):
    return {"case": "t", "label": "a", "n": 4, "variant": variant, "events": 4,
            "arms": {"dose:0": {"entries": 4, "outcome": base}, "dose:6": {"entries": 4, "outcome": edited}}}


RUN = {
    "prereg": "prereg/002", "status": "planted", "labels": ["a", "b"], "arms": ARMS,
    "lists": [
        _list("a", 5, (5, 3, 5)),      # in S, the edit writes three of five
        _list("a", 5, (5, 5, 9)),      # in S, the edit is exact and the random arm runs on
        _list("a", 3, (3, 2, 3)),      # too short for S, still counted by size
        _list("b", 6, (5, 4, 6)),      # the unedited model is short, so not in S
        _list("b", 4, (4, 4, 4)),      # in S, nothing happens
    ],
    "twins": [_twin("replay", "exact", "exact"), _twin("replay", "ghost", "exact"), _twin("second", "exact", "dropped")],
    "delivered": {"dose:0": {"L15": 0.0, "L19": 0.0}, "dose:6": {"L15": 2.0, "L19": 4.0}, "matched:0": {"L15": 1.0, "L19": 4.0}},
    "sampled": {
        "dose:0/seed0": {"lists": [{"entries": 5, "outcome": "exact"}] * 5, "twins": [{"entries": 4, "outcome": "exact"}] * 3},
        "dose:0/seed1": {"lists": [{"entries": 5, "outcome": "exact"}] * 4 + [{"entries": 1, "outcome": "dropped"}],
                         "twins": [{"entries": 4, "outcome": "exact"}] * 3},
        "dose:6/seed0": {"lists": [{"entries": 2, "outcome": "dropped"}] * 2 + [{"entries": 5, "outcome": "exact"}] * 3,
                         "twins": [{"entries": 4, "outcome": "exact"}] * 3},
    },
}


def test_every_arm_gets_its_counts_on_the_analysis_set_and_on_everything():
    rep = gr.report(RUN)
    assert rep["analysis_set"] == 3
    edit = rep["arms"]["dose:6"]
    assert edit["S"] == {"n": 3, "short": 1, "long": 0, "exact": 2}
    assert edit["all"] == {"n": 5, "short": 3, "long": 0, "exact": 2}
    assert rep["arms"]["matched:0"]["S"]["long"] == 1
    assert rep["arms"]["matched:0"]["push_relative_to_edit"] == {"L15": 0.5, "L19": 1.0}
    assert abs(edit["mean_p_stop_line3"] - 0.4) < 1e-9 and abs(rep["arms"]["dose:0"]["mean_p_stop_line3"] - 0.1) < 1e-9


def test_labels_sizes_and_missing_lines_are_tabulated():
    rep = gr.report(RUN)
    assert rep["by_label"]["a"]["S"] == 2 and rep["by_label"]["a"]["edit_short_in_S"] == 1
    assert rep["by_label"]["b"]["unedited_short"] == 1 and rep["by_label"]["b"]["S"] == 1
    assert rep["by_label"]["b"]["mean_p_stop_line3"]["dose:6"] == 0.4          # the six-event list is the only one long enough
    assert rep["by_size"]["3"]["edit_short_where_unedited_exact"] == 1
    assert rep["by_size"]["6"]["unedited_exact"] == 0 and rep["by_size"]["6"]["edit_short_where_unedited_exact"] == 0
    assert rep["lines_written_by_the_edit_on_S"] == {"4": {"4": 1}, "5": {"3": 1, "5": 1}}


def test_twins_are_split_by_kind_and_both_directions_of_change_are_counted():
    t = gr.report(RUN)["twins"]
    assert t["replay"]["not_then_exact"] == 1 and t["replay"]["exact_then_not"] == 0
    assert t["second"]["exact_then_not"] == 1 and t["second"]["outcomes"]["dose:6"] == {"dropped": 1}


def test_sampled_runs_report_the_noise_beside_the_difference():
    s = gr.report(RUN)["sampled"]["lists"]
    assert s["exact"] == {"dose:0/seed0": 5, "dose:0/seed1": 4, "dose:6/seed0": 3}
    assert s["exactness_differs_between_two_unedited_runs"] == 1 and s["exactness_differs_unedited_to_edited"] == 2
    # the truths are 5, 5, 3, 6, 4 and the edited run wrote 2, 2, 5, 5, 5: three short, two long
    assert s["short"]["dose:6/seed0"] == 3 and s["long"]["dose:6/seed0"] == 2
    assert gr.report(dict(RUN, sampled={}))["sampled"] == {}

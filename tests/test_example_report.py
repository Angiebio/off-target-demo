# offtarget · tests/test_example_report.py
# v0.1 · 12NOV2026
#
# Practical: the tables around prereg/004's verdict, on a planted run of eight
# lists whose counts can be checked by hand.
# Philosophical: the verdict pools the random arms, and a pool can hide one arm
# that behaves unlike the others. The table that keeps them apart gets its own
# check here, with one arm planted to disagree.
import pytest

from offtarget import example_report as er

ARMS = ["dose:0", "dose:6", "matched:2", "matched:4"]


def _list(example, label, n, wrote):
    """`wrote` maps an arm to lines written; any arm not named wrote all n."""
    arms = {}
    for a in ARMS:
        e = wrote.get(a, n)
        arms[a] = {"entries": e, "outcome": "exact" if e == n else "dropped" if e < n else "ghost", "ended": True}
    return {"case": f"{example}-{label}-{n}", "label": label, "example": example, "n": n, "arms": arms}


RUN = {"prereg": "prereg/004", "arms": ARMS, "lists": [
    _list("two", "AF onset", 6, {"dose:6": 2, "matched:2": 2, "matched:4": 4}),     # the edit and one random arm write two
    _list("two", "AF onset", 7, {"dose:6": 2, "matched:2": 2, "matched:4": 4}),
    _list("two", "pause detected", 6, {"dose:0": 5, "dose:6": 2}),                  # the unedited model is one short: not in S
    _list("two", "pause detected", 8, {"dose:0": 11}),                              # and here it runs long
    _list("five", "AF onset", 6, {"dose:6": 5}),
    _list("five", "AF onset", 7, {"dose:6": 9}),                                    # the edit runs long
    _list("three", "pause detected", 6, {}),
    _list("none", "pause detected", 6, {"dose:6": 4}),
]}


def test_counts_over_all_lists_and_over_the_good_ones():
    t = er.arms_by_example(RUN)
    assert t["two"]["dose:0"]["all"] == {"n": 4, "exact": 2, "short": 1, "long": 1}
    assert t["two"]["dose:6"]["all"] == {"n": 4, "exact": 1, "short": 3, "long": 0}
    assert t["two"]["dose:6"]["S"] == {"n": 2, "exact": 0, "short": 2, "long": 0}          # the third short one is outside S
    assert t["five"]["dose:6"]["S"] == {"n": 2, "exact": 0, "short": 1, "long": 1}
    assert t["three"]["dose:6"]["S"] == {"n": 1, "exact": 1, "short": 0, "long": 0}


def test_the_random_arms_are_kept_apart():
    t = er.short_lengths_by_arm(RUN)
    assert t["two"]["dose:6"] == {"2": 2} and t["two"]["matched:2"] == {"2": 2} and t["two"]["matched:4"] == {"4": 2}
    assert t["five"]["dose:6"] == {"5": 1} and t["none"]["dose:6"] == {"4": 1} and "dose:0" not in t["two"]


def test_what_the_unedited_model_wrote_when_wrong():
    u = er.unedited_misses(RUN)
    assert u["two"] == {"wrong": 2, "lines_minus_events": {"-1": 1, "+3": 1}, "lines_written_when_short": {"5": 1}}
    assert u["three"]["wrong"] == 0 and u["three"]["lines_minus_events"] == {}


def test_the_two_tables_added_afterwards_say_so_and_count_right():
    by = er.lines_by_size(RUN)
    assert by["two"]["dose:6"] == {"6": {"2": 1}, "7": {"2": 1}}                   # on S: the two good lists, two lines each
    assert by["two"]["dose:0"] == {"6": {"5": 1, "6": 1}, "7": {"7": 1}, "8": {"11": 1}}   # the unedited arm is shown on every list
    assert by["five"]["dose:6"] == {"6": {"5": 1}, "7": {"9": 1}}
    both = er.both_directions(RUN)
    assert both["dose:0"] == {"n": 6, "exact": 6, "short": 0, "long": 0}
    assert both["dose:6"] == {"n": 6, "exact": 1, "short": 4, "long": 1}
    assert both["matched:4"] == {"n": 6, "exact": 4, "short": 2, "long": 0}


def _same_log_run():
    """Three logs, each asked four ways. The unedited model gets two of them right every time."""
    lists = []
    for log, n in (("bare-list-n6-s0-x", 6), ("bare-list-n7-s1-x", 7), ("bare-list-n6-s2-x", 6)):
        for example in er.EXAMPLES:
            wrote = {}
            if example in ("three", "five") and n == 6:
                wrote["dose:6"] = 5                                               # the edit is short when a big number is named
            if log.endswith("s2-x") and example == "five":
                wrote["dose:0"] = 5                                               # this log is not exact under every example
            r = _list(example, "x", n, wrote)
            r["case"] = log if example == "three" else f"{log}-ex-{example}"
            lists.append(r)
    return {"prereg": "prereg/004", "arms": ARMS, "lists": lists}


def test_the_same_logs_across_examples():
    assert er.log_of("bare-list-n6-s0-af-onset-ex-none") == er.log_of("bare-list-n6-s0-af-onset") == "bare-list-n6-s0-af-onset"
    same = er.same_logs(_same_log_run())
    assert same["logs"] == 3 and same["exact_under_every_example"] == 2
    assert same["short"]["dose:6"] == {"three": 1, "two": 0, "five": 1, "none": 0}      # only the six-event log that is in the set
    assert same["short"]["matched:4"] == {"three": 0, "two": 0, "five": 0, "none": 0}
    broken = _same_log_run()
    broken["lists"].pop()
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        er.same_logs(broken)


def test_by_label_and_by_size():
    labels, sizes = er.by_label(RUN), er.by_size(RUN)
    af, pause = labels["AF onset"], labels["pause detected"]
    assert af["lists"] == 4 and af["S"] == 4 and af["edit_short_in_S"] == 3 and af["edit_long_in_S"] == 1
    assert pause["unedited"] == {"n": 4, "exact": 2, "short": 1, "long": 1} and pause["S"] == 2 and pause["edit_short_in_S"] == 1
    assert sizes["6"]["lists"] == 5 and sizes["6"]["S"] == 4 and sizes["6"]["edit_short_in_S"] == 3


def test_the_whole_report_holds_every_table_and_marks_the_late_ones():
    rep = er.report(_same_log_run())
    assert rep["lists"] == 12 and set(rep) >= {"arms_by_example", "short_lengths_by_arm", "unedited_misses", "by_label", "by_size"}
    assert set(rep["added_after_the_verdict_was_read"]) == {"lines_by_size", "both_directions", "same_logs"}
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        er.report({"prereg": "prereg/004", "arms": ARMS, "lists": []})
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        er.report(RUN)                                                            # logs not asked all four ways are refused

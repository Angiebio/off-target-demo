# offtarget · tests/test_example.py
# v0.1 · 12NOV2026
#
# Practical: everything prereg/004 needs that runs without a model. The swappable
# example sentence in the task, the seal and sizes of its runner, and its decision
# rules on planted worlds: one where the short handoffs follow the example, one
# where they are three lines whatever the example says, one that is mixed, and one
# too small to read.
# Philosophical: the last run gave me a story I liked, and this registration exists
# to give that story a fair chance to die. So the first worlds built here are the
# ones where it does.
from pathlib import Path

import pytest

from offtarget import example_registered as reg
from offtarget import example_verdict as ev
from offtarget import ghostbeat as gb
from offtarget import ghostbeat_registered as reg002

# ---- the task option -------------------------------------------------------------

def test_the_default_example_is_the_sentence_registration_002_used():
    old = gb.make_case(5, "list", "bare", 0, "SpO2 low, 87%")
    same = gb.make_case(5, "list", "bare", 0, "SpO2 low, 87%", "three")
    assert old == same and "If the event happened three times, the line appears three times." in old.prompt
    assert old.case_id == "bare-list-n5-s0-spo2-low-87"                           # no suffix, so 002's logs keep their names


def test_swapping_the_example_changes_one_sentence_and_nothing_else():
    three = gb.make_case(7, "list", "bare", 3, "AF onset")
    for name, sentence in gb.EXAMPLES.items():
        c = gb.make_case(7, "list", "bare", 3, "AF onset", name)
        assert c.rows == three.rows and c.expected == three.expected and c.example == name
        assert c.prompt == three.prompt.replace(gb.EXAMPLES["three"], sentence)
        assert sum(s in c.prompt for s in gb.EXAMPLES.values()) == 1
    assert not any(ch.isdigit() for ch in gb.EXAMPLES["none"]) and "three" not in gb.EXAMPLES["none"]


def test_an_unknown_example_or_one_on_the_id_format_is_refused():
    with pytest.raises(ValueError, match="WIRING FAILURE"):
        gb.make_case(6, "list", "bare", 0, "AF onset", "seven")
    with pytest.raises(ValueError, match="WIRING FAILURE"):
        gb.make_case(6, "replay", "id", 0, "AF onset", "two")


# ---- the runner's promises ---------------------------------------------------------

def test_the_seal_and_the_size_of_the_run(tmp_path: Path):
    (tmp_path / "prereg").mkdir(parents=True)
    (tmp_path / reg.PREREG).write_text("# 004\n\n**Status: DRAFT for review.** Frozen later, when it says FROZEN.\n", encoding="utf-8")
    assert not reg.frozen(tmp_path)
    (tmp_path / reg.PREREG).write_text("# 004\n\n**Status: FROZEN on a date.**\n", encoding="utf-8")
    assert reg.frozen(tmp_path)
    lists = [gb.make_case(n, "list", "bare", s, lab, ex) for ex in reg.EXAMPLES for lab in reg.HELD_OUT for n in reg.SIZES for s in range(reg.SEEDS)]
    assert len(lists) == 480 and len({c.case_id for c in lists}) == 480 and len({c.prompt for c in lists}) == 480
    assert min(reg.SIZES) > max(ev.NUMBER.values())                              # two, three and five lines are all short


def test_the_labels_are_new_and_carry_no_digits():
    seen = {gb.LABEL, "PAC, isolated", "pause, 2.4 s"} | set(reg002.HELD_OUT)
    assert len(set(reg.HELD_OUT)) == 5 and not set(reg.HELD_OUT) & seen
    assert not any(ch.isdigit() for lab in reg.HELD_OUT for ch in lab)


def test_runner_and_verdict_agree_on_names():
    assert set(ev.CURVE) | set(ev.MATCHED) == set(reg.ARMS) and len(reg.ARMS) == 13
    assert set(ev.NUMBER) | {"none"} == set(reg.EXAMPLES) and ev.REVERSED in reg.ARMS


# ---- the rules ---------------------------------------------------------------------

def _list(example, n, wrote, base_exact=True, ended=True):
    """One list. `wrote` maps an arm to the number of lines it wrote; every other arm is exact."""
    arms = {}
    for a in reg.ARMS:
        e = wrote.get(a, n)
        if a == "dose:0":
            e = n if base_exact else wrote.get(a, n - 1)
        arms[a] = {"entries": e, "outcome": "exact" if e == n else "dropped" if e < n else "ghost", "ended": ended}
    return {"case": f"{example}-{n}", "label": "x", "example": example, "n": n, "arms": arms}


def _world(edit_len, matched_len=None, per=40, short_every=2):
    """`per` good lists per example. Every `short_every`-th one comes up short under the edit, at the length given."""
    lists = []
    for example in reg.EXAMPLES:
        for i in range(per):
            wrote = {}
            if i % short_every == 0:
                wrote["dose:6"] = edit_len(example)
                if matched_len:
                    wrote.update({a: matched_len(example) for a in ev.MATCHED})
            lists.append(_list(example, 6 + i % 3, wrote))
    return lists


def test_q1_follows_the_example_when_the_number_moves_with_it():
    v = ev.follows(_world(lambda e: ev.NUMBER.get(e, 4)), ev.EDIT)
    assert v["verdict"] == "FOLLOWS THE EXAMPLE"
    assert v["by_example"]["five"]["most_common"] == [5] and v["by_example"]["two"]["share_at_the_examples_number"] == 1.0


def test_q1_three_regardless_when_the_number_does_not_move():
    v = ev.follows(_world(lambda e: 3), ev.EDIT)
    assert v["verdict"] == "THREE REGARDLESS" and v["by_example"]["five"]["share_at_three"] == 1.0


def test_q1_mixed_when_only_some_examples_are_followed_and_a_tie_wins_nothing():
    half = ev.follows(_world(lambda e: 2 if e == "two" else 3), ev.EDIT)               # follows "two", stays at three under "five"
    assert half["verdict"] == "MIXED"
    lists = _world(lambda e: ev.NUMBER.get(e, 4))
    flip = True
    for r in lists:                                                                   # under "five", half the short ones write four lines
        if r["example"] == "five" and r["arms"]["dose:6"]["entries"] == 5 and r["n"] > 5:
            if flip:
                r["arms"]["dose:6"]["entries"] = 4
            flip = not flip
    v = ev.follows(lists, ev.EDIT)
    assert v["by_example"]["five"]["most_common"] == [4, 5] and v["verdict"] == "MIXED"


def test_q1_needs_enough_good_lists_and_enough_short_ones():
    assert ev.follows(_world(lambda e: ev.NUMBER.get(e, 4), per=20), ev.EDIT)["verdict"] == "NOT TESTABLE"       # S under 30
    assert ev.follows(_world(lambda e: ev.NUMBER.get(e, 4), short_every=4), ev.EDIT)["verdict"] == "NOT TESTABLE"  # 10 short


def test_q2_reads_the_random_pushes_pooled_and_separately_from_the_edit():
    lists = _world(lambda e: 3, matched_len=lambda e: ev.NUMBER.get(e, 4))
    assert ev.follows(lists, ev.EDIT)["verdict"] == "THREE REGARDLESS"
    v = ev.follows(lists, ev.MATCHED)
    assert v["verdict"] == "FOLLOWS THE EXAMPLE" and v["by_example"]["two"]["short"] == 60        # 20 lists, three arms


def test_q3_reads_the_net_effect_of_the_small_reversed_dose():
    good = [_list("three", 6, {}) for _ in range(60)]
    healed = [_list("three", 7, {"dose:0": 6}, base_exact=False) for _ in range(40)]             # the reversed dose gets these right
    v = ev.reversed_dose(good + healed)
    assert v["verdict"] == "HELPS" and v["made_exact"] == 40 and v["broken"] == 0 and v["misses_made_exact"] == 40
    broken = [_list("three", 6, {"dose:-2": 9}) for _ in range(40)]                              # it sends good lists long
    assert ev.reversed_dose(good + broken)["verdict"] == "HURTS"
    stuck = [_list("three", 7, {"dose:0": 6, "dose:-2": 6}, base_exact=False) for _ in range(40)]
    assert ev.reversed_dose(good + stuck)["verdict"] == "NO DIFFERENCE DETECTED"
    assert ev.reversed_dose(good[:10])["verdict"] == "NOT TESTABLE"
    other = [_list("two", 7, {"dose:0": 6}, base_exact=False) for _ in range(40)]                # other examples are not read here
    assert ev.reversed_dose(good + other)["made_exact"] == 0


def test_judge_and_the_tables_without_a_rule():
    lists = _world(lambda e: ev.NUMBER.get(e, 4), matched_len=lambda e: ev.NUMBER.get(e, 4))
    lists += [_list("three", 6, {"dose:6": 3}, ended=False)]                                    # one that went quiet with no END
    v = ev.judge({"prereg": "prereg/004", "lists": lists})
    assert (v["Q1"]["verdict"], v["Q2"]["verdict"], v["Q3"]["verdict"]) == ("FOLLOWS THE EXAMPLE", "FOLLOWS THE EXAMPLE", "NO DIFFERENCE DETECTED")
    d = v["described"]
    assert d["short_under_the_edit_by_example"]["none"]["short"] == 20 and d["short_under_the_edit_by_example"]["none"]["lengths"] == {"4": 20}
    assert d["exact_share_by_dose_three_example"]["dose:0"] == 1.0 and d["exact_share_by_dose_three_example"]["dose:6"] < 0.6
    assert d["how_short_handoffs_ended"]["dose:6"]["went_quiet"] == 1 and d["how_short_handoffs_ended"]["dose:0"]["short"] == 0

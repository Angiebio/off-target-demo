# offtarget · tests/test_ghostbeat.py
# v0.1 · 11NOV2026
#
# Practical: the event-log simulator and the handoff scorer, checked on handoffs
# where we planted the mistake ourselves: one event left out, one reported twice,
# both at once with the line count still right, an ID that was never in the log.
# Philosophical: a scorer that only counts lines would pass a handoff that drops
# one beat and invents another. That is the exact trade Ying warned about, a
# system getting better at one error by getting worse at the other, so the test
# that matters most is the one where the totals agree and the note is still wrong.
import pytest

from offtarget.ghostbeat import LABEL, make_case, make_cases, outcome, score, summarise


def test_twins_differ_in_exactly_one_row_and_have_the_same_row_count():
    for n in (1, 2, 8, 32):
        a, b = make_case(n, "replay", "id", 0), make_case(n, "second", "id", 0)
        assert len(a.rows) == len(b.rows) == n + 1
        assert sum(x != y for x, y in zip(a.rows, b.rows)) == 1
        assert len(a.truth) == n and len(b.truth) == n + 1


def test_same_seed_same_case_and_formats_share_the_log():
    assert make_case(8, "second", "id", 3) == make_case(8, "second", "id", 3)
    assert make_case(8, "second", "id", 3).rows == make_case(8, "second", "bare", 3).rows
    assert make_case(8, "second", "id", 3).rows != make_case(8, "second", "id", 4).rows


def test_a_replay_keeps_its_time_and_a_second_event_comes_later_in_order():
    a, b = make_case(16, "replay", "id", 1), make_case(16, "second", "id", 1)
    i = next(i for i, (x, y) in enumerate(zip(a.rows, b.rows)) if x != y)
    assert a.rows[i].acquisition == a.rows[i - 1].acquisition and a.rows[i].acquired == a.rows[i - 1].acquired
    assert a.rows[i].delivery != a.rows[i - 1].delivery
    assert b.rows[i].acquisition not in {r.acquisition for r in a.rows}
    times = [r.acquired for r in b.rows]
    assert times == sorted(times) and len(set(times)) == len(times)


@pytest.mark.parametrize("fmt", ["id", "bare"])
@pytest.mark.parametrize("variant", ["replay", "second"])
def test_the_correct_handoff_scores_exact(fmt, variant):
    c = make_case(8, variant, fmt, 0)
    s = score(c, c.expected)
    assert s["exact"] and s["ended"] and s["omitted"] == 0 and s["ghosts"] == 0 and outcome(s) == "exact"


def test_one_dropped_beat_is_an_omission_and_not_a_ghost():
    for fmt in ("id", "bare"):
        c = make_case(8, "second", fmt, 0)
        lines = c.expected.split("\n")
        s = score(c, "\n".join(lines[:3] + lines[4:]))
        assert (s["omitted"], s["ghosts"], outcome(s)) == (1, 0, "dropped")


def test_one_ghost_beat_is_a_duplicate_and_not_an_omission():
    for fmt in ("id", "bare"):
        c = make_case(8, "replay", fmt, 0)
        lines = c.expected.split("\n")
        s = score(c, "\n".join(lines[:3] + [lines[2]] + lines[3:]))
        assert (s["omitted"], s["ghosts"], outcome(s)) == (0, 1, "ghost")


def test_right_line_count_wrong_note_is_caught_when_ids_are_shown():
    # Drop event 5 and report event 2 twice. Eight lines in, eight lines out.
    c = make_case(8, "replay", "id", 0)
    lines = c.expected.split("\n")
    lines[5] = lines[2]
    s = score(c, "\n".join(lines))
    assert s["entries"] == s["truth"] and (s["omitted"], s["ghosts"]) == (1, 1) and outcome(s) == "both"


def test_an_id_that_was_never_in_the_log_is_foreign_not_a_ghost():
    c = make_case(4, "replay", "id", 0)
    s = score(c, c.expected.replace("END", f"A-0000 {LABEL}\nEND"))
    assert (s["omitted"], s["ghosts"], s["foreign"], outcome(s)) == (0, 0, 1, "other")


def test_bullets_numbers_and_text_after_end_do_not_change_the_count():
    c = make_case(3, "replay", "bare", 0)
    s = score(c, f"1. {LABEL}\n- {LABEL}\n* {LABEL}.\n**END**\n{LABEL}\n{LABEL}")
    assert s["exact"] and s["ended"] and s["entries"] == 3


def test_chatter_is_counted_as_other_lines_and_not_as_events():
    c = make_case(2, "replay", "bare", 0)
    s = score(c, f"Here is the handoff note:\n{LABEL}\n{LABEL}\nEND")
    assert s["exact"] and s["other_lines"] == 1


def test_thinking_that_never_closes_is_no_answer_not_a_pile_of_omissions():
    c = make_case(4, "second", "id", 0)
    s = score(c, "Let me look at the log. " * 50, finished=False, thinking=True)
    assert not s["answered"] and s["omitted"] is None and outcome(s) == "no_answer"
    t = score(c, "Let me look.\n</think>\n\n" + c.expected, thinking=True)
    assert t["exact"]


def test_summary_keeps_the_two_errors_in_separate_columns():
    c = make_case(4, "second", "bare", 0)
    rows = [score(c, c.expected), score(c, f"{LABEL}\nEND"), score(c, "\n".join([LABEL] * 7 + ["END"])),
            score(c, "x", thinking=True)]
    s = summarise(rows)
    assert (s["n"], s["exact"], s["dropped"], s["ghost"], s["no_answer"]) == (4, 1, 1, 1, 1)
    assert s["omitted_per_case"] == pytest.approx(4 / 3) and s["ghosts_per_case"] == pytest.approx(2 / 3)


def test_make_cases_is_the_full_grid():
    assert len(make_cases([1, 2, 4], [0, 1])) == 3 * 2 * 2 * 2
    with pytest.raises(ValueError, match="WIRING FAILURE"):
        make_case(0, "replay", "id", 0)


def test_batches_respect_both_the_row_limit_and_the_token_budget():
    from offtarget.ghostbeat_probe import pack

    assert pack([10, 10, 10, 100], batch=3, budget=200) == [[0, 1, 2], [3]]
    assert pack([10, 10, 100, 100, 100], batch=8, budget=200) == [[0, 1], [2, 3], [4]]   # a batch is as wide as its longest row
    assert pack([500], batch=4, budget=100) == [[0]]                                      # one oversized prompt still runs, alone
    assert [i for c in pack(list(range(1, 40)), 5, 60) for i in c] == list(range(39))      # nothing lost, order kept

# offtarget · tests/test_default_full.py
# v0.1 · 11NOV2026
#
# Practical: the two parts of the full-size default-mode runner that can be tested
# without a GPU. The clock that stops it at dawn, and the seal that keeps it from
# running before its registration is frozen.
# Philosophical: a run left alone overnight needs two promises kept by something
# other than my memory. It will not start early, and it will not still be holding
# the card when the person who owns the machine sits down with her coffee.
import datetime as dt

from offtarget import default_full as df


def test_an_evening_run_stops_the_next_morning_and_a_morning_run_stops_the_same_day():
    evening = dt.datetime(2026, 11, 11, 23, 30)
    assert df.deadline("06:00", evening) == dt.datetime(2026, 11, 12, 6, 0)
    small_hours = dt.datetime(2026, 11, 12, 1, 15)
    assert df.deadline("06:00", small_hours) == dt.datetime(2026, 11, 12, 6, 0)
    assert df.deadline(None, evening) is None


def test_the_seal_reads_the_status_line_of_its_own_registration(tmp_path):
    (tmp_path / "prereg").mkdir(parents=True)
    reg = tmp_path / df.PREREG
    reg.write_text("# title\n\n**Status: DRAFT.** It says FROZEN somewhere in the middle of a line.\n", encoding="utf-8")
    assert not df.frozen(tmp_path)
    reg.write_text("# title\n\n**Status: FROZEN on a date.** Binding.\n", encoding="utf-8")
    assert df.frozen(tmp_path)


def test_the_names_the_verdict_looks_up_are_the_names_the_runner_writes():
    from offtarget import default_verdict as dv
    assert dv.ARMS == ("0.0", "6.0") and df.N % df.BLOCK == 0 and df.BLOCK % df.BATCH == 0

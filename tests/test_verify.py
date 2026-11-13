# offtarget · tests/test_verify.py
# v0.1 · 13NOV2026
#
# Practical: the one-command check, the table of sources and the page-data rebuild,
# tested two ways. First on this repository's own record, where everything must pass.
# Then on a copy of the record with one number changed by hand, where the check must
# fail and must say where.
# Philosophical: a check that has never been seen to fail is a decoration. The house
# rule is "break it on purpose, and if it does not crash it is not wired". These tests
# are that rule applied to the checker itself: plant a wrong number, and watch whether
# the alarm goes off in the right room.
import json
import shutil
from pathlib import Path

import pytest

from offtarget import verify
from offtarget.claims import CITED, CLAIMS, check_claims, dig, render_sources, same
from offtarget.pagedata import collect, refresh

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def copy(tmp_path):
    """A private copy of the record that a test is free to damage."""
    for folder in ("results", "page", "explore", "prereg"):
        shutil.copytree(ROOT / folder, tmp_path / folder, ignore=shutil.ignore_patterns("raw", "*.html", "*.png", "*.safetensors"))
    return tmp_path


def _edit(path: Path, change) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def _status(checks, starts_with: str) -> str:
    hit = [c for c in checks if c.name.startswith(starts_with)]
    assert len(hit) == 1, f"expected one check starting with {starts_with!r}, found {len(hit)}"
    return hit[0].status


def test_this_repositorys_own_record_passes():
    checks = verify.run(ROOT)
    failed = [f"{c.name}: {c.detail}" for c in checks if c.status == verify.FAIL]
    assert not failed, failed
    # Nine checks need nothing but the record. More run where the documents and the freeze log exist (the public copy).
    assert sum(c.status == verify.PASS for c in checks) >= 9
    assert all(c.status in (verify.PASS, verify.SKIP) for c in checks)


def test_a_skip_is_reported_as_a_skip_and_says_what_it_needs():
    checks = verify.run(ROOT)
    needs_logs = [c for c in checks if "authors' scores" in c.name]
    assert needs_logs and all(c.status == verify.SKIP and "--logs" in c.detail for c in needs_logs)


def test_a_changed_verdict_is_caught_where_it_was_changed(copy):
    def lower(d):
        d["Q1"]["k"] -= 1            # 75 lists left short becomes 74
    _edit(copy / "results" / "ghostbeat_verdict.json", lower)
    checks = verify.run(copy)
    assert _status(checks, "registration 002: verdicts") == verify.FAIL
    assert _status(checks, "registration 004: verdicts") == verify.PASS      # the other run is untouched
    assert _status(checks, "the page's data") == verify.FAIL                # the page copied the old number
    assert _status(checks, "the table of sources") == verify.FAIL
    detail = next(c.detail for c in checks if c.name.startswith("registration 002: verdicts"))
    assert "Q1" in detail and "k" in detail


def test_a_number_typed_into_the_page_data_is_caught(copy):
    def raise_it(d):
        d["default_mode"]["four"]["unedited"]["thinking_off_ours"] = 0.5      # the pilot's reading, typed back in
    _edit(copy / "page" / "data.json", raise_it)
    checks = verify.run(copy)
    assert _status(checks, "the page's data") == verify.FAIL
    assert _status(checks, "the table of sources") == verify.FAIL
    assert _status(checks, "registration 003: the default setting's accuracy") == verify.PASS   # the record itself is fine


def test_a_changed_raw_answer_changes_a_verdict(copy):
    def flip(d):
        block = next(b for key, b in d["blocks"].items() if key.startswith("0.0/"))
        block["rows"][0]["correct"] = not block["rows"][0]["correct"]
    _edit(copy / "results" / "default_mode_full.json", flip)
    checks = verify.run(copy)
    assert _status(checks, "registration 003: the default setting's accuracy") == verify.FAIL


def test_a_registration_edited_after_its_freeze_is_caught(copy):
    reg = "prereg/003-default-mode-full.md"
    (copy / "docs").mkdir()
    log = {"registrations": [{"file": reg, "sha256_at_freeze": verify.sha256_text(copy / reg)}]}
    (copy / "docs" / "freeze-log.json").write_text(json.dumps(log), encoding="utf-8")
    assert all(c.status == verify.PASS for c in verify.frozen(copy))
    with (copy / reg).open("a", encoding="utf-8") as fh:
        fh.write("\nA margin moved after the result was seen.\n")
    assert [c.status for c in verify.frozen(copy)] == [verify.FAIL]


def test_line_endings_do_not_change_a_registrations_hash(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_bytes(b"frozen\nrule\n")
    b.write_bytes(b"frozen\r\nrule\r\n")
    assert verify.sha256_text(a) == verify.sha256_text(b)


def test_every_claim_points_at_something_on_the_page_and_in_a_file():
    page = json.loads((ROOT / "page" / "data.json").read_text(encoding="utf-8"))
    for c in CLAIMS:
        dig(page, c.page)                                   # raises if the page has no such field
        assert (ROOT / c.source).exists(), c.source
    assert len({c.page for c in CLAIMS}) == len(CLAIMS)     # no number is claimed twice
    assert all(r["ok"] for r in check_claims(ROOT))


def test_the_printed_table_carries_every_row():
    text = render_sources(ROOT)
    assert text.count("\n| ") >= len(CLAIMS) + len(CITED)
    for c in CITED:
        for words in (c.terms() if c.absent else [c.look_for]):
            assert words in text


def test_same_forgives_float_dust_and_nothing_else():
    assert same(0.1 + 0.2, 0.3)
    assert same({"a": [1, 2.0]}, {"a": [1, 2]})
    assert not same(75, 74)
    assert not same({"a": 1}, {"a": 1, "b": 2})
    assert not same([1, 2], [1, 2, 3])
    assert not same("NO HARM AT THIS SIZE", "HARM")


def test_refresh_keeps_what_was_measured_and_refuses_without_it():
    existing = json.loads((ROOT / "page" / "data.json").read_text(encoding="utf-8"))
    data = refresh(ROOT, existing)
    assert data["demo"] == existing["demo"] and data["neurons"] == existing["neurons"]
    assert data["alarm"] == collect(ROOT)["alarm"]
    del existing["demo"]
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        refresh(ROOT, existing)

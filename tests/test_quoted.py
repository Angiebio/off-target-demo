# offtarget · tests/test_quoted.py
# v0.1 · 13NOV2026
#
# Practical: the numbers a Markdown document quotes. A planted wrong number, an unknown
# format, a path that leads nowhere, a numeral with its address removed, and the things
# that must not be mistaken for a numeral (code, links, model names, row labels).
# Philosophical: this file exists because the check it tests shipped for an hour with
# no test at all, in a repository whose own rules say a check needs a test in which it
# fails. A cold reader noticed, then removed one address, changed 910 to 810, and
# watched the check pass. The tests below are that reader's experiment, kept.
import tomllib
from pathlib import Path

import pytest

import offtarget
from offtarget import quoted

DATA = {"alarm": {"short": {"k": 75, "n": 103, "share": 0.7281553}}, "gap": {"difference": -0.037}, "arms": {"dose:6": {"loop": 15}}, "rows": [10, 20]}


def test_a_quoted_number_that_matches_passes():
    text = "left <!--q:alarm/short/k-->75<!--/q--> of <!--q:alarm/short/n-->103<!--/q-->, which is <!--q:alarm/short/share|pct0-->73%<!--/q-->"
    rows = quoted.check(text, DATA)
    assert len(rows) == 3 and all(r["ok"] for r in rows)


def test_a_planted_wrong_number_is_caught():
    rows = quoted.check("left <!--q:alarm/short/k-->74<!--/q--> short", DATA)
    assert [(r["says"], r["data"], r["ok"]) for r in rows] == [("74", "75", False)]


def test_an_unknown_format_is_loud():
    with pytest.raises(KeyError, match="WIRING FAILURE"):
        quoted.check("<!--q:alarm/short/k|percentish-->75<!--/q-->", DATA)


def test_a_path_that_leads_nowhere_is_loud():
    with pytest.raises(KeyError, match="WIRING FAILURE"):
        quoted.check("<!--q:alarm/long/k-->75<!--/q-->", DATA)


def test_formats_print_the_way_the_documents_do():
    assert quoted.expected(DATA, "gap/difference", "pts1") == "3.7"          # a difference in points, sign dropped
    assert quoted.expected({"n": 1060}, "n", None) == "1,060"
    assert quoted.expected(DATA, "arms/dose:6/loop", "n") == "15"            # a key with a colon in it
    assert quoted.expected(DATA, "rows/1", "n") == "20"                      # a list index
    with pytest.raises(TypeError):
        quoted.expected(DATA, "alarm/short/share", "n")                      # a share is not a count


def test_fill_rewrites_the_number_and_nothing_else():
    text = "before <!--q:alarm/short/k-->?<!--/q--> after"
    assert quoted.fill(text, DATA) == "before <!--q:alarm/short/k-->75<!--/q--> after"


def test_a_numeral_with_its_address_removed_is_reported():
    """The cold reader's experiment: unwrap one number, change it, and see whether anything notices."""
    wrapped = "<!--q:alarm/short/k-->75<!--/q--> were stuck"
    assert quoted.unaddressed(wrapped, {}) == []
    assert quoted.unaddressed("810 were stuck", {}) == ["810"]
    assert quoted.unaddressed("64 output columns became 46", {"64": "results/diff.json"}) == ["46"]


def test_what_is_not_a_numeral():
    text = ("GPT-6 Astra edited Qwen3.5-0.8B on MATH-500. See `python -I x.py 99`, [the log](runs/12/a.md) and https://example.org/2026/11.\n"
            "| 3 | a table row label\n```\nseed = 1234\n```\n<!-- a comment with 55 in it -->")
    assert quoted.unaddressed(text, {}) == []


def test_what_is_a_numeral():
    assert quoted.unaddressed("On 2 November 2026, 1,060 answers, 44.4% right, 0.8 billion.", {"2026": "the year"}) == ["2", "1,060", "44.4%", "0.8"]


def test_every_constant_names_where_it_comes_from():
    for doc, constants in quoted.CONSTANTS.items():
        for token, source in constants.items():
            assert source.strip(), f"{doc}: the constant {token} has no source"


def test_the_package_version_is_the_one_pyproject_declares():
    """A version in two places drifts. This holds them together."""
    declared = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert offtarget.__version__ == declared

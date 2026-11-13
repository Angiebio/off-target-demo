# offtarget · offtarget/quoted.py
# v0.2 · 13NOV2026 (v0.1 the same day; v0.2 also finds the numbers that carry no address)
#
# Practical: lets a Markdown document quote a number from page/data.json and stay
# checkable. A quoted number is wrapped in a pair of HTML comments that name where it
# comes from. They do not show when the document is rendered:
#     left <!--q:alarm/short/k-->75<!--/q--> of <!--q:alarm/short/n-->103<!--/q--> lists short
# check() reads every such pair and compares the text between them with the value in
# the data file, printed the way the pair asks (a count, a percent, points).
#   python -m offtarget.quoted README.md docs/FINDINGS.md          # report
#   python -m offtarget.quoted --fill README.md docs/FINDINGS.md   # rewrite the numbers from the data
# unaddressed() does the other half. It lists every numeral written in digits that has
# no address and is not on the document's short list of constants (CONSTANTS below,
# each with where it comes from). So a number is either checked against the data, or
# named as a constant with its source, or reported. Numbers spelled as words are not
# seen by either half, and the documents say so.
#
# Philosophical: a README is where numbers go to drift. It is written once, in a good
# mood, and then the analysis moves and nobody opens it again. The page this project
# feeds refuses to build when its sentences stop matching its data. A README cannot
# refuse to render, so it gets the next best thing: every number in it carries its
# address, and a machine reads the addresses. The comments are ugly in the raw file.
# They are there for the same reason a calibration sticker is ugly on an instrument.
#
# v0.2 exists because a cold reader took the first version at its word. The README
# said the check covered every number it quoted. The reader removed one address,
# changed 910 to 810, and the check passed. The claim was true of the numbers that
# carried an address and silent about the rest. A check has to be described by what
# it would miss, and then the miss has to be closed or stated.
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PAIR = re.compile(r"<!--q:([^|>]+?)(?:\|([a-z0-9]+))?-->(.*?)<!--/q-->", re.S)
# What is taken out of a document before looking for bare numerals: code, links and comments.
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)
LINK = re.compile(r"\]\([^)]*\)|https?://\S+")
COMMENT = re.compile(r"<!--.*?-->", re.S)
ROW_LABEL = re.compile(r"^\|\s*\d+\s*\|", re.M)          # the number that labels a table row
LIST_MARKER = re.compile(r"^\s*\d+\.\s", re.M)           # the number that starts a list item
NUMERAL = re.compile(r"(?<![\w.,/-])\d[\d,]*(?:\.\d+)?%?(?![\w/-])")

# Numerals a document may print without an address, and where each comes from. Keep these
# lists short. Every entry is a number nobody is checking by machine, so each one names the
# file a person can check it against. A typo that lands on another entry of the same list
# would pass, which is the price of a constant and the reason to prefer an address.
_POST = "the post, https://rikiyat.github.io/blog/weight-space-programming/"
_LOGS = "the authors' logs, cited with file and line in docs/SOURCES.md"
_OWN = "the number of a finding in docs/FINDINGS.md"
CONSTANTS: dict[str, dict[str, str]] = {
    "README.md": {
        "2": "the day the post was published, 2 November. " + _POST,
        "12": "the day the authors added their response, 12 November. " + _POST,
        "2026": "the year",
        "3.11": "the oldest Python this installs on. pyproject.toml, requires-python",
        "4.0": "the version of the Creative Commons licence on the authors' logs. NOTICE.md",
    },
    "docs/FINDINGS.md": {
        "12": "the day the authors added their response, 12 November. " + _POST,
        "2026": "the year",
        "64": "columns changed in each tensor. results/diff.json, changed[].cols, and the post",
        "15": "the first edited layer. results/diff.json, changed[].layer",
        "19": "the second edited layer. results/diff.json, changed[].layer",
        "24": "points gained by a plain removal in the editor's practice test. " + _LOGS,
        "50": "points gained by the shipped edit on the held-back practice problems. " + _LOGS,
        "1,152": "practice problems held back for confirmation. " + _LOGS,
        "13": _OWN, "16": _OWN, "17": _OWN, "18": _OWN,
    },
}


def _count(v: Any) -> str:
    if not isinstance(v, int) or isinstance(v, bool):
        raise TypeError(f"expected a whole number, got {v!r}")
    return f"{v:,}"


FORMATS = {
    "n": _count,                                        # 1,060
    "pct0": lambda v: f"{100 * v:.0f}%",                # 0.728 -> 73%
    "pct1": lambda v: f"{100 * v:.1f}%",                # 0.444 -> 44.4%
    "pts1": lambda v: f"{100 * abs(v):.1f}",            # -0.037 -> 3.7 (a difference in points, sign dropped)
    "f2": lambda v: f"{v:.2f}",                         # 0.917 -> 0.92
    "text": lambda v: str(v),
}


def dig(data: Any, path: str) -> Any:
    """Follow a/b/c into nested dictionaries and lists. A missing step is an error, never a blank."""
    for step in path.split("/"):
        if isinstance(data, list):
            data = data[int(step)]
        elif step in data:
            data = data[step]
        else:
            raise KeyError(f"WIRING FAILURE: the data has no '{step}' on the way to '{path}'")
    return data


def expected(data: dict, path: str, fmt: str | None) -> str:
    fmt = fmt or "n"
    if fmt not in FORMATS:
        raise KeyError(f"WIRING FAILURE: unknown number format '{fmt}' for '{path}'")
    return FORMATS[fmt](dig(data, path.strip()))


def check(text: str, data: dict) -> list[dict]:
    """Every quoted number, with what the document says and what the data says."""
    return [{"path": m.group(1).strip(), "says": m.group(3), "data": expected(data, m.group(1), m.group(2)),
             "ok": m.group(3) == expected(data, m.group(1), m.group(2))} for m in PAIR.finditer(text)]


def unaddressed(text: str, constants: dict[str, str]) -> list[str]:
    """Numerals in digits that carry no address and are not a named constant of this document."""
    bare = LIST_MARKER.sub(" ", ROW_LABEL.sub("|", LINK.sub("] ", CODE.sub(" ", COMMENT.sub(" ", PAIR.sub(" ", text))))))
    found = []
    for m in NUMERAL.finditer(bare):
        token = m.group(0).rstrip(",")
        if token not in constants and token not in found:
            found.append(token)
    return found


def fill(text: str, data: dict) -> str:
    """The same document with every quoted number rewritten from the data."""
    return PAIR.sub(lambda m: f"<!--q:{m.group(1)}{'|' + m.group(2) if m.group(2) else ''}-->{expected(data, m.group(1), m.group(2))}<!--/q-->", text)


def main() -> None:
    ap = argparse.ArgumentParser(description="Check, or refill, the numbers a Markdown document quotes from page/data.json.")
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--data", type=Path, default=Path("page/data.json"))
    ap.add_argument("--fill", action="store_true", help="rewrite the quoted numbers from the data instead of reporting")
    args = ap.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    bad = 0
    for f in args.files:
        text = f.read_text(encoding="utf-8")
        if args.fill:
            f.write_text(fill(text, data), encoding="utf-8", newline="\n")
        text = f.read_text(encoding="utf-8")
        rows = check(text, data)
        wrong = [r for r in rows if not r["ok"]]
        loose = unaddressed(text, CONSTANTS.get(f.as_posix(), {}))
        bad += len(wrong) + len(loose)
        print(f"{f}: {len(rows)} quoted numbers, {len(wrong)} differ from the data, {len(loose)} numerals with no address")
        for r in wrong:
            print(f"   {r['path']}: the document says {r['says']!r}, the data says {r['data']!r}")
        if loose:
            print("   no address and not a named constant: " + ", ".join(loose))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

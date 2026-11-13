# offtarget · offtarget/verify.py
# v0.1 · 13NOV2026
#
# Practical: one command that recomputes what this repository claims and says where
# the claim and the recomputation differ. It needs no GPU, no model and no download.
#   python -m offtarget.verify                         # everything this repository can check by itself
#   python -m offtarget.verify --logs <exp8_math>      # also what needs the authors' published logs
#   python -m offtarget.verify --base <base snapshot>  # also the two lines quoted from the model card
# Exit code 0 when every check that ran passed, 1 when any failed. A check that could
# not run (because it needs a file you did not point it at) is reported as SKIPPED
# with what it needs. A skip is not a pass and is never counted as one.
#
# What it checks, in the order it reports:
#   1. Each registered run's verdicts and tables, recomputed from the raw run file by
#      the same rule modules that were frozen before the run, against the committed
#      verdict and report files.
#   2. The page's data file, rebuilt from the result files, against page/data.json.
#   3. Every row of the table of sources (offtarget/claims.py), reached a second way.
#   4. docs/SOURCES.md, reprinted, against the file in the repository.
#   5. Every number the README and docs/FINDINGS.md quote, against the page's data.
#   6. The frozen registrations, hashed, against docs/freeze-log.json.
#   With --logs: the half of registration 003 that needs the authors' scores, the
#   problem-by-problem pairing of their scores, and the words quoted from their notes.
#
# Philosophical: this file is the difference between "we were careful" and "you can
# check". A reviewer with five minutes cannot rerun a night of GPU work, and should
# not have to take the summary on faith either. What they can do is watch the rules
# be applied again to the raw answers, and see the same verdicts fall out. That is
# the part of the chain that is cheap to recheck, so it should cost nothing to do.
#
# It is also written for the next agent. An agent picking this repository up has no
# memory of which numbers were checked and which were typed. It can run this, read
# the failures, and know exactly where the record and the words have come apart. A
# fail-loud check is how a team whose members forget everything stays honest.
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from offtarget import default_report, default_verdict, example_report, example_verdict, ghostbeat_report, ghostbeat_verdict
from offtarget.claims import CARD, CITED, LOGS, check_claims, render_sources, same
from offtarget.pagedata import refresh

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIPPED"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


def _read(path: Path) -> dict:
    if not path.is_file():
        # A missing result file is a broken record, and it should read as one. A bare
        # FileNotFoundError with a traceback tells a reviewer nothing about what to do next.
        raise SystemExit(f"WIRING FAILURE: {path} is missing. Run this from the repository root (or pass --root), "
                         "and check that no result file has been removed.")
    return json.loads(path.read_text(encoding="utf-8"))


def _first_difference(a, b, where: str = "") -> str:
    """Where two nested values first disagree, in words short enough to print."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                return f"{where}.{k} is in one and not the other"
            if not same(a[k], b[k]):
                return _first_difference(a[k], b[k], f"{where}.{k}")
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{where} has {len(a)} items against {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            if not same(x, y):
                return _first_difference(x, y, f"{where}[{i}]")
    return f"{where or 'value'}: claimed {json.dumps(a)[:80]}, recomputed {json.dumps(b)[:80]}"


def _compare(name: str, claimed, recomputed) -> Check:
    if same(claimed, recomputed):
        return Check(name, PASS)
    return Check(name, FAIL, _first_difference(claimed, recomputed))


def registered_runs(root: Path) -> list[Check]:
    """Apply the frozen rules again to the raw runs. No authors' file is needed for these."""
    res = root / "results"
    out = []
    run2 = _read(res / "ghostbeat_registered.json")
    out.append(_compare("registration 002: verdicts recomputed from the raw run", _read(res / "ghostbeat_verdict.json"), ghostbeat_verdict.judge(run2)))
    out.append(_compare("registration 002: tables recomputed from the raw run", _read(res / "ghostbeat_report.json"), ghostbeat_report.report(run2)))
    run4 = _read(res / "example_registered.json")
    out.append(_compare("registration 004: verdicts recomputed from the raw run", _read(res / "example_verdict.json"), example_verdict.judge(run4)))
    out.append(_compare("registration 004: tables recomputed from the raw run", _read(res / "example_report.json"), example_report.report(run4)))
    # Registration 003 has two halves. The half that is ours on both sides (the edit with thinking
    # off, and how the answers ended) needs only our raw run.
    run3, v3 = _read(res / "default_mode_full.json"), _read(res / "default_mode_verdict.json")
    rows, ids = default_verdict.per_problem(run3), default_verdict.complete(run3)
    unedited, edited = (rows[a] for a in default_verdict.ARMS)
    out.append(_compare("registration 003: the edit with thinking off, recomputed from the raw run", v3["Q2"], default_verdict.q2(unedited, edited, ids)))
    out.append(_compare("registration 003: how the answers ended, recomputed from the raw run", v3["endings"], default_verdict.endings(rows, ids)))
    ours = sum(int(unedited[i]["correct"]) for i in ids) / len(ids)
    out.append(_compare("registration 003: the default setting's accuracy, recomputed from the raw run", v3["Q1"]["default_mode_accuracy"], ours))
    return out


def page_data(root: Path) -> list[Check]:
    name = "the page's data, rebuilt from the result files"
    existing = _read(root / "page" / "data.json")
    try:
        rebuilt = refresh(root, existing)
    except RuntimeError as e:
        # The rebuild cross-checks the result files against each other and raises when two of
        # them disagree. That is a failure of the record, and it belongs in the report beside
        # the others, with its own words, so the reader sees every broken link in one run.
        if "WIRING FAILURE" not in str(e):
            raise
        return [Check(name, FAIL, str(e))]
    return [_compare(name, existing, rebuilt)]


def sources(root: Path) -> list[Check]:
    rows = check_claims(root)
    bad = [r for r in rows if not r["ok"]]
    detail = "; ".join(f"{r['claim'].says}: page {json.dumps(r['claimed'])[:50]}, file {json.dumps(r['recomputed'])[:50]}" for r in bad[:3])
    out = [Check(f"the table of sources: {len(rows)} claims traced to their result files", FAIL if bad else PASS,
                 f"{len(bad)} disagree. {detail}" if bad else "")]
    doc = root / "docs" / "SOURCES.md"
    if doc.exists():
        out.append(Check("docs/SOURCES.md is the table printed from the code", PASS if doc.read_text(encoding="utf-8") == render_sources(root) else FAIL,
                         "" if doc.read_text(encoding="utf-8") == render_sources(root) else "reprint it with python -m offtarget.claims --write docs/SOURCES.md"))
    else:
        out.append(Check("docs/SOURCES.md is the table printed from the code", SKIP, "no docs/SOURCES.md in this copy"))
    return out


QUOTING = ("README.md", "docs/FINDINGS.md")    # documents whose numbers carry their address (offtarget/quoted.py)


def documents(root: Path) -> list[Check]:
    """The numbers quoted in the README and the findings, against the page's data."""
    from offtarget import quoted

    data = _read(root / "page" / "data.json")
    out = []
    for rel in QUOTING:
        name = f"{rel}: every number it quotes matches the page's data"
        if not (root / rel).exists():
            out.append(Check(name, SKIP, f"no {rel} in this copy"))
            continue
        text = (root / rel).read_text(encoding="utf-8")
        rows = quoted.check(text, data)
        wrong = [r for r in rows if not r["ok"]]
        if not rows:
            out.append(Check(name, SKIP, "the document quotes no number with an address"))
            continue
        out.append(Check(name, FAIL if wrong else PASS,
                         "; ".join(f"{r['path']}: says {r['says']}, data {r['data']}" for r in wrong[:3]) if wrong else f"{len(rows)} numbers"))
        # The other half. A numeral with no address is either a named constant of the document or a
        # hole in the check. A cold reader changed 910 to 810 with its address removed and the first
        # version of this check passed. Now that fails here.
        constants = quoted.CONSTANTS.get(rel, {})
        loose = quoted.unaddressed(text, constants)
        out.append(Check(f"{rel}: no numeral in digits is without an address or a named source", FAIL if loose else PASS,
                         "no address: " + ", ".join(loose[:8]) if loose else f"{len(constants)} named constants"))
    return out


def sha256_text(path: Path) -> str:
    """Hash of a text file with its line endings normalised, so a checkout on Windows and one on Linux agree."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def frozen(root: Path) -> list[Check]:
    log = root / "docs" / "freeze-log.json"
    if not log.exists():
        return [Check("the frozen registrations are unchanged since their freeze", SKIP, "no docs/freeze-log.json in this copy")]
    out = []
    for entry in _read(log)["registrations"]:
        now = sha256_text(root / entry["file"])
        out.append(Check(f"{entry['file']} is unchanged since its freeze", PASS if now == entry["sha256_at_freeze"] else FAIL,
                         "" if now == entry["sha256_at_freeze"] else f"frozen {entry['sha256_at_freeze'][:12]}, now {now[:12]}"))
    return out


def with_logs(root: Path, logs: Path | None) -> list[Check]:
    """The checks that need a copy of the authors' published logs (the exp8_math folder)."""
    names = ["registration 003: the default setting against the edit, recomputed with the authors' scores",
             "registration 003: tables recomputed with the authors' scores",
             "the authors' scores paired problem by problem, recomputed",
             "words quoted from the authors' notes are in the files named"]
    if logs is None:
        return [Check(n, SKIP, "needs --logs <the authors' exp8_math folder>") for n in names]
    from offtarget import paired

    res, ev = root / "results", logs / "eval"
    edited, unedited = paired.load_per_problem(ev, "p50c"), paired.load_per_problem(ev, "unedited")
    run3 = _read(res / "default_mode_full.json")
    pilot = _read(res / "pilot_default_mode.json")
    out = [_compare(names[0], _read(res / "default_mode_verdict.json"), default_verdict.judge(run3, edited["math500"], unedited["math500"])),
           _compare(names[1], _read(res / "default_mode_report.json"), default_report.report(run3, edited["math500"], unedited["math500"], pilot))]
    paired.verify_against_merged(ev, "unedited", unedited)
    paired.verify_against_merged(ev, "p50c", edited)
    claimed = _read(res / "paired.json")
    recomputed = {"schema": paired.SCHEMA, "base": "unedited", "edited": "p50c", "reliable_threshold": paired.RELIABLE,
                  "benchmarks": {b: paired.compare(unedited[b], edited[b]) for b in sorted(set(unedited) & set(edited))}}
    out.append(_compare(names[2], claimed, recomputed))
    missing = []
    for c in CITED:
        if c.where != LOGS:
            continue
        text = (logs / c.file).read_text(encoding="utf-8", errors="replace")
        if c.look_for not in text:
            missing.append(f"{c.file}: {c.look_for!r}")
    cited = sum(c.where == LOGS for c in CITED)
    out.append(Check(names[3], FAIL if missing else PASS, "; ".join(missing[:3]) if missing else f"{cited} quotations found"))
    return out


def with_base(base: Path | None) -> list[Check]:
    name = "words quoted from the model card are in the card"
    if base is None:
        return [Check(name, SKIP, "needs --base <a snapshot of Qwen/Qwen3.5-0.8B at revision 2fc0636>")]
    card = (base / "README.md").read_text(encoding="utf-8", errors="replace")
    missing = [c.look_for for c in CITED if c.where == CARD and c.look_for not in card]
    return [Check(name, FAIL if missing else PASS, "; ".join(missing))]


def _visible_text(page: str) -> str:
    """A saved web page as the words a reader sees, with typographic quotes made plain."""
    import html
    import re

    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    for fancy, plain in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"')):
        text = text.replace(fancy, plain)
    return re.sub(r"\s+", " ", text)


def with_post(post: Path | None) -> list[Check]:
    """What we say the post says, and what we say it does not say, against a copy of the post you saved.

    Practical: save the post as HTML and pass --post. Each claim that the post says something
    must be found in it. Each claim that it does not say something lists the terms we searched
    for, and none of them may be found.
    Philosophical: a post can change. This one did, on 12 November 2026, with a response that
    answered one of our findings, and a recheck that only looked for the old sentences sailed
    past it. A claim about what a living document says needs a date and a way to ask again.
    """
    from offtarget.claims import POST

    names = ["what we quote from the post is in the post", "what we say the post leaves out is not in the post"]
    if post is None:
        return [Check(n, SKIP, "needs --post <the post saved as HTML>") for n in names]
    text = _visible_text(post.read_text(encoding="utf-8", errors="replace"))
    quoted_claims = [c for c in CITED if c.where == POST and not c.absent]
    absent_claims = [c for c in CITED if c.where == POST and c.absent]
    missing = [c.look_for for c in quoted_claims if c.look_for not in text]
    found = [f"'{term}' ({c.says[:40]})" for c in absent_claims for term in c.terms() if term.lower() in text.lower()]
    return [Check(names[0], FAIL if missing else PASS, "; ".join(missing) if missing else f"{len(quoted_claims)} quotations found"),
            Check(names[1], FAIL if found else PASS, "now present: " + "; ".join(found) if found else
                  f"{sum(len(c.terms()) for c in absent_claims)} terms searched, none found")]


def run(root: Path, logs: Path | None = None, base: Path | None = None, post: Path | None = None) -> list[Check]:
    if not (root / "page" / "data.json").is_file() or not (root / "results").is_dir():
        raise SystemExit(f"WIRING FAILURE: {root.resolve()} does not look like this repository (no page/data.json or results/). "
                         "Run from the repository root, or pass --root.")
    return (registered_runs(root) + page_data(root) + sources(root) + documents(root) + frozen(root)
            + with_logs(root, logs) + with_base(base) + with_post(post))


def main() -> None:
    ap = argparse.ArgumentParser(description="Recompute what this repository claims, and report every difference.")
    ap.add_argument("--root", type=Path, default=Path("."), help="the repository root (default: the current folder)")
    ap.add_argument("--logs", type=Path, help="the authors' published logs, folder exp8_math")
    ap.add_argument("--base", type=Path, help="a snapshot folder of the base model, for the two model card quotations")
    ap.add_argument("--post", type=Path, help="the post, saved as HTML, to check what we say it says and does not say")
    args = ap.parse_args()
    if args.logs or args.base or args.post:
        from offtarget.isolation import require_isolated

        require_isolated("offtarget.verify with --logs, --base or --post")
    checks = run(args.root, args.logs, args.base, args.post)
    width = max(len(c.name) for c in checks)
    for c in checks:
        print(f"{c.status:8} {c.name:{width}}  {c.detail}".rstrip())
    n = {s: sum(c.status == s for c in checks) for s in (PASS, FAIL, SKIP)}
    print(f"\n{n[PASS]} passed, {n[FAIL]} failed, {n[SKIP]} skipped (a skip is a check that needs a file you did not give it, and it is not a pass)")
    sys.exit(1 if n[FAIL] else 0)


if __name__ == "__main__":
    main()

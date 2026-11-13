# offtarget · offtarget/example_report.py
# v0.2 · 12NOV2026 (v0.2 adds three tables AFTER the verdict was read: lines_by_size,
#                   both_directions and same_logs. They are marked in the output as added afterwards.)
#
# Practical: the tables around the verdict of prereg/004. For each example sentence
# and each arm: how many handoffs were exact, short and long, over all lists and
# over the lists the unedited model got right. How long the short handoffs were,
# arm by arm (the verdict pools the three random arms; here they stand apart). What
# the unedited model wrote when it was wrong. And the picture by label and by size.
# No model, no torch, no thresholds.
#   python -I -m offtarget.example_report --run results/example_registered.json --out results/example_report.json
#
# Philosophical: written while the run was still on the card, with two progress
# lines seen and no handoff read, so that what gets counted was settled before I
# knew which counts would be kind to my prediction. The verdict answers the
# questions I thought to ask. This is where the ones I did not think of can show.
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from offtarget import example_verdict as ev
from offtarget.ghostbeat_verdict import long, short

SCHEMA = "offtarget.example_report/0.1"
EXAMPLES = ("three", "two", "five", "none")


def _counts(lists: list[dict], arm: str) -> dict:
    return {"n": len(lists), "exact": sum(r["arms"][arm]["outcome"] == "exact" for r in lists),
            "short": sum(short(r, arm) for r in lists), "long": sum(long(r, arm) for r in lists)}


def arms_by_example(run: dict) -> dict:
    """{example: {arm: {"all": counts, "S": counts}}}. S is the lists the unedited model got right under that example."""
    out = {}
    for example in EXAMPLES:
        mine = [r for r in run["lists"] if r["example"] == example]
        s = ev.s_of(run["lists"], example)
        out[example] = {arm: {"all": _counts(mine, arm), "S": _counts(s, arm)} for arm in run["arms"]}
    return out


def short_lengths_by_arm(run: dict) -> dict:
    """{example: {arm: {lines written: count}}} for the short handoffs on S, one arm at a time."""
    out = {}
    for example in EXAMPLES:
        s = ev.s_of(run["lists"], example)
        out[example] = {arm: {str(n): v for n, v in sorted(ev.lengths(s, (arm,)).items())} for arm in run["arms"] if arm != "dose:0"}
    return out


def unedited_misses(run: dict) -> dict:
    """What the unedited model wrote when it was not exact: lines written minus events, by example."""
    out = {}
    for example in EXAMPLES:
        wrong = [r for r in run["lists"] if r["example"] == example and r["arms"]["dose:0"]["outcome"] != "exact"]
        off = Counter(r["arms"]["dose:0"]["entries"] - r["n"] for r in wrong)
        out[example] = {"wrong": len(wrong), "lines_minus_events": {f"{d:+d}": v for d, v in sorted(off.items())},
                        "lines_written_when_short": {str(n): v for n, v in sorted(Counter(
                            r["arms"]["dose:0"]["entries"] for r in wrong if short(r, "dose:0")).items())}}
    return out


def by_label(run: dict) -> dict:
    out = {}
    for label in sorted({r["label"] for r in run["lists"]}):
        mine = [r for r in run["lists"] if r["label"] == label]
        s = [r for r in mine if r["arms"]["dose:0"]["outcome"] == "exact"]
        out[label] = {"lists": len(mine), "unedited": _counts(mine, "dose:0"), "S": len(s),
                      "edit_short_in_S": sum(short(r, "dose:6") for r in s), "edit_long_in_S": sum(long(r, "dose:6") for r in s)}
    return out


def by_size(run: dict) -> dict:
    out = {}
    for n in sorted({r["n"] for r in run["lists"]}):
        mine = [r for r in run["lists"] if r["n"] == n]
        s = [r for r in mine if r["arms"]["dose:0"]["outcome"] == "exact"]
        out[str(n)] = {"lists": len(mine), "unedited": _counts(mine, "dose:0"), "S": len(s),
                       "edit_short_in_S": sum(short(r, "dose:6") for r in s)}
    return out


def lines_by_size(run: dict) -> dict:
    """{example: {arm: {events: {lines written: count}}}} on S (for the unedited arm, on every list).

    Added after the verdict was read. A length means nothing without the number of events beside
    it: five lines is the example's number under "five" and one line short of six everywhere.
    """
    out = {}
    for example in EXAMPLES:
        mine = [r for r in run["lists"] if r["example"] == example]
        s = ev.s_of(run["lists"], example)
        out[example] = {}
        for arm in run["arms"]:
            rows = mine if arm == "dose:0" else s
            out[example][arm] = {str(n): {str(k): v for k, v in sorted(Counter(r["arms"][arm]["entries"] for r in rows if r["n"] == n).items())}
                                 for n in sorted({r["n"] for r in rows})}
    return out


def both_directions(run: dict) -> dict:
    """{arm: counts} over every list the unedited model got right, whatever the example.

    Added after the verdict was read. The registered curve is the share exact under the "three"
    example. This splits the misses by which way they went, because the two sides of zero fail
    in opposite directions and one number hides that.
    """
    good = [r for r in run["lists"] if r["arms"]["dose:0"]["outcome"] == "exact"]
    return {arm: _counts(good, arm) for arm in run["arms"]}


def log_of(case_id: str) -> str:
    """The log a list was built from: the case id without its example suffix."""
    for example in EXAMPLES:
        if case_id.endswith(f"-ex-{example}"):
            return case_id[: -len(f"-ex-{example}")]
    return case_id


def same_logs(run: dict) -> dict:
    """Short handoffs by example on the logs the unedited model got right under every example.

    Added after the verdict was read. The good lists differ from one example to the next, so a
    difference between examples could be a difference between lists. Here the lists are the same.
    """
    by_log: dict[str, dict[str, dict]] = {}
    for r in run["lists"]:
        by_log.setdefault(log_of(r["case"]), {})[r["example"]] = r
    if any(set(v) != set(EXAMPLES) for v in by_log.values()):
        raise RuntimeError("WIRING FAILURE: some log was not asked under all four examples")
    common = [v for v in by_log.values() if all(v[e]["arms"]["dose:0"]["outcome"] == "exact" for e in EXAMPLES)]
    arms = [a for a in run["arms"] if a != "dose:0"]
    return {"logs": len(by_log), "exact_under_every_example": len(common),
            "short": {arm: {e: sum(short(v[e], arm) for v in common) for e in EXAMPLES} for arm in arms}}


def report(run: dict) -> dict:
    if not run["lists"]:
        raise RuntimeError("WIRING FAILURE: the run holds no lists, so there is nothing to tabulate")
    return {"schema": SCHEMA, "prereg": run["prereg"], "lists": len(run["lists"]),
            "arms_by_example": arms_by_example(run), "short_lengths_by_arm": short_lengths_by_arm(run),
            "unedited_misses": unedited_misses(run), "by_label": by_label(run), "by_size": by_size(run),
            "added_after_the_verdict_was_read": {"lines_by_size": lines_by_size(run), "both_directions": both_directions(run),
                                                 "same_logs": same_logs(run)}}


def show(rep: dict) -> None:
    for example, arms in rep["arms_by_example"].items():
        print(f"example {example}")
        for arm, c in arms.items():
            a, s = c["all"], c["S"]
            print(f"  {arm:10s} all {a['n']:3d}: exact {a['exact']:3d} short {a['short']:3d} long {a['long']:3d}   "
                  f"S {s['n']:3d}: exact {s['exact']:3d} short {s['short']:3d} long {s['long']:3d}   "
                  f"short lengths {rep['short_lengths_by_arm'][example].get(arm, '')}")
    for example, u in rep["unedited_misses"].items():
        print(f"unedited misses, example {example}: {u['wrong']} wrong, lines minus events {u['lines_minus_events']}")
    for label, b in rep["by_label"].items():
        print(f"  {label:18s} lists {b['lists']:3d}  unedited exact {b['unedited']['exact']:3d} short {b['unedited']['short']:3d} long {b['unedited']['long']:3d}"
              f"  S {b['S']:3d}  edit short {b['edit_short_in_S']:3d} long {b['edit_long_in_S']:3d}")
    for n, b in rep["by_size"].items():
        print(f"  {n} events: lists {b['lists']:3d}  unedited exact {b['unedited']['exact']:3d}  S {b['S']:3d}  edit short {b['edit_short_in_S']:3d}")


def main() -> None:
    ap = argparse.ArgumentParser(description="The tables around the verdict of prereg/004.")
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    rep = report(json.loads(args.run.read_text(encoding="utf-8")))
    args.out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    show(rep)


if __name__ == "__main__":
    main()

# offtarget · offtarget/claims.py
# v0.1 · 13NOV2026
#
# Practical: the table of sources. Every number the article prints is listed here once,
# with three things: where it sits in page/data.json (the file the page reads), which
# result file it comes from, and how to get it out of that file. offtarget/verify.py
# walks the list and checks that the two agree. docs/SOURCES.md is printed from the
# same list, so the document a reader sees cannot drift from the check a machine runs.
#   python -m offtarget.claims --write docs/SOURCES.md
#
# Claims that rest on someone else's file (the authors' logs, the model card, the
# post) are listed too, each with the file, the line and the words to look for. Those
# are checked when you point verify at a copy of the logs, and cited when you do not.
#
# Philosophical: "trust me" scales badly, and it scales worst with agents. A person
# who wrote a sentence yesterday remembers why. An agent that wrote it yesterday is,
# for practical purposes, a different worker today, and the next one inherits the
# sentence with no memory of the evidence. So the evidence has to live next to the
# sentence in a form a machine can walk. This file is that form. It is a manager's
# control more than a programmer's: nobody is asked to be careful, the list is asked
# to be complete, and a missing row is visible in a way a missing memory never is.
#
# Two derivations on purpose. offtarget/pagedata.py builds the page's data from the
# result files one way. The lambdas below reach into the result files another way.
# When both agree with page/data.json, a slip in either one shows up as a failure in
# the other. The pilot's "50 of 100" stayed on the page for a night because there was
# one path from the record to the words and nothing watching it.
from __future__ import annotations

import argparse
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from offtarget.default_verdict import Q1_LOWER, Q1_POINT

WEIGHTS, ANSWERS, SCORES = "the published weights", "the authors' published answers", "the authors' published scores"
REGISTERED, AFTERWARDS, EXPLORATION = "a registered run of ours", "a registered run, tabulated afterwards", "an exploration of ours"


@dataclass(frozen=True)
class Claim:
    section: str                      # where on the page a reader meets it
    says: str                         # the claim in words, without its number
    page: tuple                       # path into page/data.json
    source: str                       # the result file it comes from
    field: str                        # where in that file, in words a reader can follow
    get: Callable[[dict], Any]        # how to take it out of that file
    kind: str                         # what sort of evidence this is
    made_by: str                      # the tool that wrote the result file


@dataclass(frozen=True)
class Cited:
    section: str
    says: str
    where: str                        # "logs", "model card" or "post"
    file: str                         # path inside the authors' log repository, or the document's name
    look_for: str                     # words that must be present. For an absence, the terms searched, separated by "; "
    line: int | None = None
    absent: bool = False              # the claim is that the document does NOT say this

    def terms(self) -> list[str]:
        """For a claim of absence: every term that was searched for and must not be found."""
        return [t.strip() for t in self.look_for.split(";") if t.strip()]


def _twice(outcome: str) -> bool:
    return outcome in ("ghost", "both")


def _resent(run: dict) -> dict:
    """The resent-packet error paired log by log, straight from the raw registered run."""
    t = {"unedited": 0, "edited": 0, "repaired": 0, "introduced": 0, "persistent": 0}
    for tw in run["twins"]:
        if tw["variant"] != "replay":
            continue
        a, b = _twice(tw["arms"]["dose:0"]["outcome"]), _twice(tw["arms"]["dose:6"]["outcome"])
        t["unedited"] += a
        t["edited"] += b
        t["repaired"] += a and not b
        t["introduced"] += b and not a
        t["persistent"] += a and b
    return t


def _ids(run: dict) -> dict:
    def ex(tw: dict, arm: str) -> bool:
        return tw["arms"][arm]["outcome"] == "exact"

    tws = run["twins"]
    return {"all": len(tws), "exact_unedited": sum(ex(t, "dose:0") for t in tws), "exact_edited": sum(ex(t, "dose:6") for t in tws),
            "wrong_before": sum(not ex(t, "dose:0") for t in tws),
            "wrong_made_right": sum((not ex(t, "dose:0")) and ex(t, "dose:6") for t in tws)}


def _loops_moved(run: dict, arm: str) -> dict:
    """Against the unedited model on the same seeds: loops an arm stopped, and loops it started."""
    base = {p["id"]: p["kind"] for p in run["arms"]["dose:0"]["per_problem"]}
    this = {p["id"]: p["kind"] for p in run["arms"][arm]["per_problem"]}
    return {"stopped": sum(1 for i, k in base.items() if k == "loop" and this[i] != "loop"),
            "started": sum(1 for i, k in base.items() if k != "loop" and this[i] == "loop")}


def _pooled(report: dict, arm: str, key: str) -> int:
    return sum(report["arms_by_example"][x][arm]["all"][key] for x in ("three", "five", "two", "none"))


S1, S2, S3, S4, S5 = "What changed", "The dose", "Benefit and side effect", "The baseline", "The duplicate alarm test"

CLAIMS: tuple[Claim, ...] = (
    # ---- what changed ---------------------------------------------------------------
    Claim(S1, "weight tensors in the checkpoint", ("diff", "tensors"), "results/diff.json", "tensors.compared",
          lambda d: d["tensors"]["compared"], WEIGHTS, "offtarget.diff"),
    Claim(S1, "tensors the edit changes", ("diff", "changed"), "results/diff.json", "tensors.changed",
          lambda d: d["tensors"]["changed"], WEIGHTS, "offtarget.diff"),
    Claim(S1, "tensors bit for bit the public base model", ("diff", "identical"), "results/diff.json", "tensors.identical",
          lambda d: d["tensors"]["identical"], WEIGHTS, "offtarget.diff"),
    Claim(S1, "stored values that differ", ("diff", "values_that_differ"), "results/diff.json", "params.values_that_differ",
          lambda d: d["params"]["values_that_differ"], WEIGHTS, "offtarget.diff"),
    Claim(S1, "share of the checkpoint that differs, in percent", ("diff", "pct_of_checkpoint"), "results/diff.json",
          "100 x params.values_that_differ / params.total", lambda d: 100 * d["params"]["values_that_differ"] / d["params"]["total"],
          WEIGHTS, "offtarget.diff"),
    Claim(S1, "columns changed in each of the two tensors", ("diff", "layers"), "results/diff.json", "changed[].cols (64 in each, of 3,584)",
          lambda d: [{"layer": c["layer"], "shape": c["shape"], "cols": c["cols"], "name": c["name"]} for c in d["changed"]],
          WEIGHTS, "offtarget.diff"),
    Claim(S1, "provenance checks that pass", ("provenance", "passed"), "results/provenance.json", "count of checks[] with pass = true",
          lambda d: sum(c["pass"] for c in d["checks"]), WEIGHTS, "offtarget.provenance"),
    Claim(S1, "provenance checks run", ("provenance", "checks"), "results/provenance.json", "length of checks[]",
          lambda d: len(d["checks"]), WEIGHTS, "offtarget.provenance"),
    Claim(S1, "of those, comparisons of a hash", ("provenance", "hash_comparisons"), "results/provenance.json",
          "checks[] whose name is one of the three hash checks",
          lambda d: sum("tensor" in c["check"] and "entries" not in c["check"] for c in d["checks"]), WEIGHTS, "offtarget.provenance"),
    Claim(S1, "files besides the weights that are byte for byte the base model's (tokenizer, configuration, chat template among them)",
          ("sidecar", "same"), "results/sidecar.json", "same", lambda d: d["same"], WEIGHTS, "offtarget.sidecar"),
    # ---- benefit and side effect ----------------------------------------------------
    Claim(S3, "MATH-500 accuracy before the edit, thinking on", ("paired", "benchmarks", "math500", "acc_base"), "results/paired.json",
          "benchmarks.math500.acc_base", lambda d: d["benchmarks"]["math500"]["acc_base"], SCORES, "offtarget.paired"),
    Claim(S3, "MATH-500 accuracy after the edit, thinking on", ("paired", "benchmarks", "math500", "acc_edited"), "results/paired.json",
          "benchmarks.math500.acc_edited", lambda d: d["benchmarks"]["math500"]["acc_edited"], SCORES, "offtarget.paired"),
    Claim(S3, "MATH-500 problems that scored better", ("paired", "benchmarks", "math500", "improved"), "results/paired.json",
          "benchmarks.math500.improved", lambda d: d["benchmarks"]["math500"]["improved"], SCORES, "offtarget.paired"),
    Claim(S3, "MATH-500 problems that scored worse", ("paired", "benchmarks", "math500", "regressed"), "results/paired.json",
          "benchmarks.math500.regressed", lambda d: d["benchmarks"]["math500"]["regressed"], SCORES, "offtarget.paired"),
    Claim(S3, "published answers per model, one per problem, nine benchmarks", ("published", "unedited", "n"), "results/published_samples.json",
          "models.unedited._all.n", lambda d: d["models"]["unedited"]["_all"]["n"], ANSWERS, "offtarget.published"),
    Claim(S3, "answers stuck in a loop before the edit", ("published", "unedited", "loop"), "results/published_samples.json",
          "models.unedited._all.loop", lambda d: d["models"]["unedited"]["_all"]["loop"], ANSWERS, "offtarget.published"),
    Claim(S3, "answers stuck in a loop after the edit", ("published", "edited", "loop"), "results/published_samples.json",
          "models.p50c._all.loop", lambda d: d["models"]["p50c"]["_all"]["loop"], ANSWERS, "offtarget.published"),
    Claim(S3, "answers ending in blank space before the edit", ("published", "unedited", "whitespace"), "results/published_samples.json",
          "models.unedited._all.whitespace", lambda d: d["models"]["unedited"]["_all"]["whitespace"], ANSWERS, "offtarget.published"),
    Claim(S3, "answers ending in blank space after the edit", ("published", "edited", "whitespace"), "results/published_samples.json",
          "models.p50c._all.whitespace", lambda d: d["models"]["p50c"]["_all"]["whitespace"], ANSWERS, "offtarget.published"),
    Claim(S3, "where the blank-space answers came from, and how many of those problems the authors had marked right before",
          ("published", "pairs", "into_blank_space"), "results/published_pairs.json", "moves ending in '-> whitespace'",
          lambda d: {k: v for k, v in d["moves"].items() if k.endswith("-> whitespace")}, ANSWERS, "offtarget.published --pairs"),
    Claim(S3, "characters in the longest answer that ended in blank space", ("published", "pairs", "longest_blank_answer_chars"),
          "results/published_pairs.json", "longest_blank_answer_chars", lambda d: d["longest_blank_answer_chars"], ANSWERS,
          "offtarget.published --pairs"),
    Claim(S3, "problems in the harder random control", ("loop_control", "n"), "explore/loop_control_pilot.json", "n",
          lambda d: d["n"], EXPLORATION, "explore/loop_control_pilot.py"),
    Claim(S3, "answers that looped in each arm of that control", ("loop_control", "arms"), "explore/loop_control_pilot.json",
          "arms[].loop, long, finished, whitespace, and the loops each arm stopped and started against the unedited model",
          lambda d: {a: {**{k: arm[k] for k in ("loop", "long", "finished", "whitespace")}, "push": arm.get("push_relative_to_edit"),
                         **_loops_moved(d, a)} for a, arm in d["arms"].items()}, EXPLORATION, "explore/loop_control_pilot.py"),
    # ---- the baseline (registration 003) ---------------------------------------------
    Claim(S4, "problems in the default-setting run", ("default_mode", "n"), "results/default_mode_verdict.json", "problems_complete",
          lambda d: d["problems_complete"], REGISTERED, "offtarget.default_verdict"),
    Claim(S4, "the four accuracies (unedited and edited, thinking on and off)", ("default_mode", "four"), "results/default_mode_report.json",
          "four_accuracies", lambda d: d["four_accuracies"], REGISTERED, "offtarget.default_report"),
    Claim(S4, "the default setting against the edit: difference, interval and the rule's label", ("default_mode", "gap"),
          "results/default_mode_verdict.json", "Q1.difference, Q1.interval, Q1.verdict",
          lambda d: {k: d["Q1"][k] for k in ("difference", "interval", "verdict")}, REGISTERED, "offtarget.default_verdict"),
    Claim(S4, "the edit with thinking off: both accuracies, difference, interval and label", ("default_mode", "edit_with_thinking_off"),
          "results/default_mode_verdict.json", "Q2",
          lambda d: {k: d["Q2"][k] for k in ("difference", "interval", "unedited_accuracy", "edited_accuracy", "only_unedited_right",
                                              "only_edited_right", "verdict")}, REGISTERED, "offtarget.default_verdict"),
    Claim(S4, "how the answers ended with thinking off, unedited", ("default_mode", "endings", "unedited"), "results/default_mode_verdict.json",
          "endings['0.0']", lambda d: d["endings"]["0.0"], REGISTERED, "offtarget.default_verdict"),
    Claim(S4, "how the answers ended with thinking off, edited", ("default_mode", "endings", "edited"), "results/default_mode_verdict.json",
          "endings['6.0']", lambda d: d["endings"]["6.0"], REGISTERED, "offtarget.default_verdict"),
    Claim(S4, "our token limit in that run", ("default_mode", "setup", "ours", "cap"), "results/default_mode_full.json", "cap",
          lambda d: d["cap"], REGISTERED, "offtarget.default_full"),
    Claim(S4, "the authors' token limit", ("default_mode", "setup", "theirs", "cap"), "results/published_samples.json", "cap",
          lambda d: d["cap"], ANSWERS, "offtarget.published"),
    Claim(S4, "the authors' samples per problem", ("default_mode", "setup", "theirs", "samples_per_problem"), "results/paired.json",
          "benchmarks.math500.samples_per_problem", lambda d: d["benchmarks"]["math500"]["samples_per_problem"], SCORES, "offtarget.paired"),
    Claim(S4, "the margins of the rule fixed before the run", ("default_mode", "rule"), "prereg/003-default-mode-full.md",
          "the named constants Q1_POINT and Q1_LOWER in offtarget/default_verdict.py", lambda d: {"point": Q1_POINT, "lower": Q1_LOWER},
          REGISTERED, "prereg/003"),
    Claim(S4, "the pilot's hundred problems, in the pilot and on fresh seeds", ("default_mode", "pilots_hundred"),
          "results/default_mode_report.json", "pilots_hundred", lambda d: d["pilots_hundred"], REGISTERED, "offtarget.default_report"),
    # ---- the duplicate alarm test, first run (registration 002) -----------------------
    Claim(S5, "lists in the first run", ("alarm", "lists"), "results/ghostbeat_verdict.json", "lists", lambda d: d["lists"],
          REGISTERED, "offtarget.ghostbeat_verdict"),
    Claim(S5, "lists of four to eight events the unedited model got right", ("alarm", "good"), "results/ghostbeat_verdict.json",
          "analysis_set", lambda d: d["analysis_set"], REGISTERED, "offtarget.ghostbeat_verdict"),
    Claim(S5, "exact handoffs over every list, unedited", ("alarm", "unedited_all"), "results/ghostbeat_report.json", "arms['dose:0'].all",
          lambda d: d["arms"]["dose:0"]["all"], REGISTERED, "offtarget.ghostbeat_report"),
    Claim(S5, "exact handoffs over every list, edited", ("alarm", "edited_all"), "results/ghostbeat_report.json", "arms['dose:6'].all",
          lambda d: d["arms"]["dose:6"]["all"], REGISTERED, "offtarget.ghostbeat_report"),
    Claim(S5, "good lists the edit left short, with its interval and the rule's label", ("alarm", "short"), "results/ghostbeat_verdict.json",
          "Q1", lambda d: d["Q1"], REGISTERED, "offtarget.ghostbeat_verdict"),
    Claim(S5, "the same count at each dose", ("alarm", "by_dose"), "results/ghostbeat_report.json", "arms['dose:0' .. 'dose:6'].S",
          lambda d: {a: {**d["arms"][a]["S"], "push": d["arms"][a]["push_relative_to_edit"], "p_stop_line3": d["arms"][a]["mean_p_stop_line3"]}
                     for a in ("dose:0", "dose:1", "dose:2", "dose:4", "dose:6")}, REGISTERED, "offtarget.ghostbeat_report"),
    Claim(S5, "the eight random directions scaled to push as hard as the edit", ("alarm", "matched"), "results/ghostbeat_report.json",
          "arms['matched:0' .. 'matched:7'].S and push_relative_to_edit",
          lambda d: {a: {**v["S"], "push": v["push_relative_to_edit"], "p_stop_line3": v["mean_p_stop_line3"]}
                     for a, v in d["arms"].items() if a.startswith("matched:")}, REGISTERED, "offtarget.ghostbeat_report"),
    Claim(S5, "the three random directions of the same size in the weights", ("alarm", "usual"), "results/ghostbeat_report.json",
          "arms['random:0' .. 'random:2'].S and push_relative_to_edit",
          lambda d: {a: {**v["S"], "push": v["push_relative_to_edit"], "p_stop_line3": v["mean_p_stop_line3"]}
                     for a, v in d["arms"].items() if a.startswith("random:")}, REGISTERED, "offtarget.ghostbeat_report"),
    Claim(S5, "matched directions that left at least half as many lists short as the edit, and the rule's label", ("alarm", "control"),
          "results/ghostbeat_verdict.json", "Q3",
          lambda d: {"doing_at_least_half": d["Q3"]["matched_directions_doing_at_least_half_as_much"], "of": d["Q3"]["of"],
                     "verdict": d["Q3"]["verdict"], "mean_push": d["Q3"]["matched"]["push_relative_to_edit"]},
          REGISTERED, "offtarget.ghostbeat_verdict"),
    Claim(S5, "lines the edited model wrote on the good lists (how many short handoffs were exactly three lines)", ("alarm", "three_lines", "k"),
          "results/ghostbeat_report.json", "lines_written_by_the_edit_on_S", lambda d: d["lines_written_by_the_edit_on_S"],
          REGISTERED, "offtarget.ghostbeat_report"),
    Claim(S5, "the full reversed dose on the good lists", ("alarm", "reversed_full"), "results/ghostbeat_report.json", "arms['dose:-6'].S",
          lambda d: d["arms"]["dose:-6"]["S"], REGISTERED, "offtarget.ghostbeat_report"),
    Claim(S5, "handoffs with an ID on every line: worse among those right before, and the rule's label", ("alarm", "with_ids", "k"),
          "results/ghostbeat_verdict.json", "Q5.k (of Q5.n)", lambda d: d["Q5"]["k"], REGISTERED, "offtarget.ghostbeat_verdict"),
    Claim(S5, "handoffs with IDs right before the edit", ("alarm", "with_ids", "exact_unedited"), "results/ghostbeat_registered.json",
          "twins[] with arms['dose:0'].outcome = exact", lambda d: _ids(d)["exact_unedited"], AFTERWARDS, "offtarget.ghostbeat_registered"),
    Claim(S5, "handoffs with IDs right after the edit", ("alarm", "with_ids", "exact_edited"), "results/ghostbeat_registered.json",
          "twins[] with arms['dose:6'].outcome = exact", lambda d: _ids(d)["exact_edited"], AFTERWARDS, "offtarget.ghostbeat_registered"),
    Claim(S5, "handoffs with IDs wrong before the edit", ("alarm", "with_ids", "wrong_before"), "results/ghostbeat_registered.json",
          "twins[] not exact at dose 0", lambda d: _ids(d)["wrong_before"], AFTERWARDS, "offtarget.ghostbeat_registered"),
    Claim(S5, "of those, handoffs that came out right after the edit", ("alarm", "with_ids", "wrong_made_right"),
          "results/ghostbeat_registered.json", "twins[] not exact at dose 0 and exact at dose 6", lambda d: _ids(d)["wrong_made_right"],
          AFTERWARDS, "offtarget.ghostbeat_registered"),
    Claim(S5, "a resent packet reported as a second event: before, after, repaired, introduced, left", ("alarm", "twins", "resent_reported_twice"),
          "results/ghostbeat_registered.json", "twins[] of variant 'replay', outcome 'ghost' or 'both', paired log by log", _resent,
          AFTERWARDS, "offtarget.ghostbeat_registered"),
    # ---- the duplicate alarm test, second run (registration 004) ----------------------
    Claim(S5, "lists in the second run", ("example", "lists"), "results/example_verdict.json", "lists", lambda d: d["lists"],
          REGISTERED, "offtarget.example_verdict"),
    Claim(S5, "the registered question about the example's number", ("example", "q1"), "results/example_verdict.json", "Q1.verdict",
          lambda d: d["Q1"]["verdict"], REGISTERED, "offtarget.example_verdict"),
    Claim(S5, "good lists the edit left short under each instruction sentence, with intervals", ("example", "short_by_example"),
          "results/example_verdict.json", "described.short_under_the_edit_by_example",
          lambda d: {x: {k: d["described"]["short_under_the_edit_by_example"][x][k] for k in ("S", "short", "share", "interval")}
                     for x in ("three", "five", "two", "none")}, REGISTERED, "offtarget.example_verdict"),
    Claim(S5, "lengths of the short handoffs under the sentence that says two", ("example", "short_lengths_under_two"),
          "results/example_verdict.json", "described.short_under_the_edit_by_example.two.lengths",
          lambda d: d["described"]["short_under_the_edit_by_example"]["two"]["lengths"], REGISTERED, "offtarget.example_verdict"),
    Claim(S5, "the small reversed dose: lists fixed, lists broken, and the rule's label", ("example", "reversed"), "results/example_verdict.json",
          "Q3", lambda d: {k: d["Q3"][k] for k in ("n", "difference", "interval", "unedited_exact", "reversed_exact", "made_exact", "broken",
                                                      "verdict")}, REGISTERED, "offtarget.example_verdict"),
    Claim(S5, "exact handoffs over every list, unedited", ("example", "unedited_all", "exact"), "results/example_report.json",
          "sum over the four sentences of arms_by_example[].['dose:0'].all.exact", lambda d: _pooled(d, "dose:0", "exact"),
          REGISTERED, "offtarget.example_report"),
    Claim(S5, "exact handoffs over every list, edited", ("example", "edited_all", "exact"), "results/example_report.json",
          "sum over the four sentences of arms_by_example[].['dose:6'].all.exact", lambda d: _pooled(d, "dose:6", "exact"),
          REGISTERED, "offtarget.example_report"),
    Claim(S5, "exact handoffs over every list, by instruction sentence", ("example", "exact_all_by_example"), "results/example_report.json",
          "arms_by_example[].['dose:0' and 'dose:6'].all",
          lambda d: {x: {"n": d["arms_by_example"][x]["dose:0"]["all"]["n"], "unedited": d["arms_by_example"][x]["dose:0"]["all"]["exact"],
                         "edited": d["arms_by_example"][x]["dose:6"]["all"]["exact"]} for x in ("three", "five", "two", "none")},
          REGISTERED, "offtarget.example_report"),
    Claim(S5, "exact handoffs over every list, at each dose", ("example", "exact_all_by_dose"), "results/example_report.json",
          "sum over the four sentences of arms_by_example[].[dose].all.exact",
          lambda d: {a: _pooled(d, a, "exact") for a in d["arms_by_example"]["three"] if a.startswith("dose:")},
          REGISTERED, "offtarget.example_report"),
    Claim(S5, "what went wrong at each dose on the good lists", ("example", "added_after_the_verdict_was_read", "both_directions"),
          "results/example_report.json", "added_after_the_verdict_was_read.both_directions",
          lambda d: d["added_after_the_verdict_was_read"]["both_directions"], AFTERWARDS, "offtarget.example_report"),
    Claim(S5, "the logs right under all four sentences, and how many the edit left short under each",
          ("example", "added_after_the_verdict_was_read", "same_logs"), "results/example_report.json",
          "added_after_the_verdict_was_read.same_logs",
          lambda d: {"exact_under_every_example": d["added_after_the_verdict_was_read"]["same_logs"]["exact_under_every_example"],
                     "short_at_the_published_dose": d["added_after_the_verdict_was_read"]["same_logs"]["short"]["dose:6"]},
          AFTERWARDS, "offtarget.example_report"),
)

# Claims that rest on a document we did not write. The log paths are inside the authors'
# repository, github.com/RikiyaT/lm_understand-logs at commit 4d09ba6, folder exp8_math.
LOGS, CARD, POST = "logs", "model card", "post"
CITED: tuple[Cited, ...] = (
    Cited(S2, "The editor model's notebook names the shipped edit by its strength, six.", LOGS, "runs/p50c/work_notes/notes.md",
          "KEEP the frozen top64 alpha6 edit", 2),
    Cited(S2, "The post describes the edit as a direction subtracted from 64 output columns.", POST,
          "https://rikiyat.github.io/blog/weight-space-programming/", "subtracted that direction from 64 output columns"),
    Cited(S2, "The post does not give the strength of the edit.", POST, "https://rikiyat.github.io/blog/weight-space-programming/",
          "alpha6; six times; sixfold; strength; coefficient", absent=True),
    Cited(S2, "By the editor's own practice test, a strength of one on every neuron of both layers gained 24 points.", LOGS,
          "runs/p50c/work_notes/experiment_history.md", "original 11/128=8.59%, edited42/128=32.81%, gain24.22pp", 9),
    Cited(S2, "The shipped edit gained 50 points on the 1,152 practice problems held back for confirmation.", LOGS,
          "runs/p50c/work_notes/experiment_history.md", '"items": 1152', 374),
    Cited(S3, "The editor model saw answers ending in blank space in its own tests and logged the failure as unresolved.", LOGS,
          "runs/p50c/work_notes/experiment_history.md", "unresolved alternative degeneration", 190),
    Cited(S3, "It counted them at two strengths and noted the comparison was not clean.", LOGS,
          "runs/p50c/work_notes/experiment_history.md", "These sets differ, not a clean dose comparison", 59),
    Cited(S3, "Its final answer says some degeneration remains.", LOGS, "runs/p50c/final_answer.md", "some degeneration remain", 19),
    Cited(S3, "The post does not mention answers that end in blank space.", POST, "https://rikiyat.github.io/blog/weight-space-programming/",
          "whitespace; blank space; indent; degenerat", absent=True),
    Cited(S4, "The post's runs had thinking switched on.", POST, "https://rikiyat.github.io/blog/weight-space-programming/",
          "Qwen3.5-0.8B, thinking on"),
    # Added 13 NOV. The post gained a "Response to Comments" on 12 November 2026. It answers the point
    # this section makes, and our recheck that morning missed it because it only looked for the old
    # sentences. A fair account has to quote the answer, so here it is, word for word.
    Cited(S4, "In a response added to the post on 12 November 2026, the authors say turning thinking off raises the base score and does not fix the weights.",
          POST, "https://rikiyat.github.io/blog/weight-space-programming/",
          "Turning thinking off raises the base score, but it does not fix the weights."),
    Cited(S4, "They describe their question as whether the weights behind the loops can be found and fixed, in a setting where the model loops.",
          POST, "https://rikiyat.github.io/blog/weight-space-programming/",
          "the question is whether the weights behind its reasoning loops can be found and fixed"),
    Cited(S4, "They say thinking off avoids the loops by not using the mode that has them.",
          POST, "https://rikiyat.github.io/blog/weight-space-programming/",
          "It avoids the loops by not using the mode that has them."),
    Cited(S4, "The model's documentation says thinking is off by default.", CARD, "Qwen/Qwen3.5-0.8B README.md at revision 2fc0636",
          "Qwen3.5-0.8B operates in non-thinking mode by default", 585),
    Cited(S4, "The documentation warns that with thinking on this model is more prone to loops.", CARD,
          "Qwen/Qwen3.5-0.8B README.md at revision 2fc0636", "is more prone to entering thinking loops", 856),
    Cited(S4, "The authors' own configuration keeps a non-thinking profile with a limit of 8,192 tokens, the limit our run used.", LOGS,
          "code/profiles.py", '"max_tokens": 8192', 28),
    Cited("The record", "The editor froze the edit and then confirmed it on problems it had held back.", LOGS,
          "runs/p50c/work_notes/final_report.md", "All1152 unique problems were independent of edit selection", 27),
    Cited("How the edit was made", "The task prompt offered repetition as an example of a failure worth fixing.", LOGS,
          "runs/p50c/turns/t001/prompt.txt", "if the model often fails because it repeats itself and never finishes", 5),
    Cited("How the edit was made", "The prompt laid out the protocol: localise causally and try several strengths.", LOGS,
          "runs/p50c/turns/t001/prompt.txt", "try several strengths to see a dose-response", 20),
)


def dig(obj: Any, path: tuple) -> Any:
    for key in path:
        obj = obj[key]
    return obj


def same(a: Any, b: Any, tol: float = 1e-9) -> bool:
    """Deep equality that forgives the last bits of a float and nothing else."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b or a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=tol, abs_tol=tol)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y, tol) for x, y in zip(a, b))
    return a == b


def check_claims(root: Path) -> list[dict]:
    """One row per claim: what the page's data says, what the result file says, and whether they agree."""
    page = json.loads((root / "page" / "data.json").read_text(encoding="utf-8"))
    cache: dict[str, dict] = {}
    rows = []
    for c in CLAIMS:
        if c.source.endswith(".json") and c.source not in cache:
            cache[c.source] = json.loads((root / c.source).read_text(encoding="utf-8"))
        claimed = dig(page, c.page)
        recomputed = c.get(cache.get(c.source, {}))
        if c.page == ("diff", "layers"):          # the page adds each tensor's position in the file, which needs the checkpoint
            claimed = [{k: v for k, v in layer.items() if k != "index"} for layer in claimed]
        rows.append({"claim": c, "claimed": claimed, "recomputed": recomputed, "ok": same(claimed, recomputed)})
    return rows


def _short(v: Any, limit: int = 60) -> str:
    if isinstance(v, float):
        return f"{v:.4g}"
    s = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
    return s if len(s) <= limit else "see the file (" + ("a table" if isinstance(v, dict) else "a list") + ")"


def render_sources(root: Path) -> str:
    """docs/SOURCES.md, printed from the lists above and the values in page/data.json."""
    rows = check_claims(root)
    out = ["# Sources for each claim", "",
           "*Made by `python -m offtarget.claims --write docs/SOURCES.md` from `offtarget/claims.py`. Do not edit by hand.*", "",
           "Every number the article prints is in `page/data.json`. This table says which result file each one comes from, and",
           "`python -m offtarget.verify` checks every row. The last table lists the claims that rest on someone else's document,",
           "with the file, the line and the words to look for.", "",
           f"{len(rows)} claims are checked against result files. {len(CITED)} are cited from the authors' logs, the model card or the post.", ""]
    section = None
    for r in rows:
        c = r["claim"]
        if c.section != section:
            section = c.section
            out += ["", f"## {section}", "", "| The claim | Value | Result file | Field | Evidence | Written by |", "|---|---|---|---|---|---|"]
        out.append(f"| {c.says} | {_short(r['claimed'])} | `{c.source}` | {c.field} | {c.kind} | `{c.made_by}` |")
    out += ["", "## Claims that rest on a document we did not write", "",
            "The logs are `github.com/RikiyaT/lm_understand-logs` at commit `4d09ba6`, folder `exp8_math`. The post is a living",
            "document. It gained a section, \"Response to Comments\", on 12 November 2026, and these rows were checked against the post as",
            "it read on 13 November 2026. For a claim that the post does not say something, the last column lists every term we",
            "searched for and did not find. Save the post as HTML and run `python -I -m offtarget.verify --post <file>` to ask again.", "",
            "| Section | The claim | Document | File | Line | Words to look for |", "|---|---|---|---|---|---|"]
    for c in CITED:
        words = ("none of: " + ", ".join(f"`{t}`" for t in c.terms())) if c.absent else "`" + c.look_for + "`"
        out.append(f"| {c.section} | {c.says} | {c.where} | `{c.file}` | {c.line or ''} | {words} |")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Print the table of sources, or write it to a file.")
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--write", type=Path, help="where to write the table, for example docs/SOURCES.md")
    args = ap.parse_args()
    text = render_sources(args.root)
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {args.write} ({len(CLAIMS)} checked claims, {len(CITED)} cited)")
    else:
        print(text)


if __name__ == "__main__":
    main()

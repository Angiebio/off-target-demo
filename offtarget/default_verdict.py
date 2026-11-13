# offtarget · offtarget/default_verdict.py
# v0.1 · 11NOV2026
#
# Practical: applies the decision rules of prereg/003 to the full-size default-mode
# run. Two questions. Does the unedited model with thinking off do about as well on
# MATH-500 as the edited model did with thinking on, in the authors' own published
# scores? And does the edit change anything when thinking is off? No model, no
# torch. Every threshold in the registration is a named constant here.
#   python -I -m offtarget.default_verdict --run results/default_mode_full.json \
#       --eval <logs>/exp8_math/eval --out results/default_mode_verdict.json
#
# Philosophical: the pilot said "about as well" on a hundred problems and one roll
# of the dice each. That sentence is the one a headline would be built on, so this
# file exists to give it a fair chance to be wrong. A rule that can only confirm is
# a compliment. This one has a way to say the edit is ahead and a way to say we
# cannot tell.
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SCHEMA = "offtarget.default_verdict/0.1"
ARMS = ("0.0", "6.0")                  # the unedited model and the published edit, as the run names them
MIN_PROBLEMS = 300                     # under this many complete problems nothing is read
# Default minus edited-with-thinking: the point estimate, and the interval's lower bound.
# These two numbers have a story, and it is not a flattering one. They were written before the
# run (prereg/003) by the agent alone, with no outside reviewer, and they were drawn loosely. A
# result five points behind, with an interval reaching ten behind, earns the label "AS GOOD OR
# BETTER". The run came in 3.7 points behind with the whole interval below zero, and the rule
# said "as good or better" about a result that was neither. The label cannot be changed after
# the fact, so the write-up reports it, says it flatters the result, and gives the plain reading.
# Do not tighten these constants: the registration is frozen and the verdict must stay what the
# frozen rule returns. Do better next time: name a margin verdict for what it shows ("within the
# margin"), and have someone else look at the margin before the freeze.
Q1_POINT, Q1_LOWER = -0.05, -0.10
Z = 1.96


def paired(d: list[float]) -> dict:
    """Mean of paired differences with a 95% interval from their own spread."""
    n = len(d)
    if n < 2:
        raise ValueError("WIRING FAILURE: an interval on fewer than two pairs")
    mean = sum(d) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in d) / (n - 1))
    half = Z * sd / math.sqrt(n)
    return {"n": n, "difference": mean, "interval": [mean - half, mean + half]}


def per_problem(run: dict) -> dict[str, dict[str, dict]]:
    """{arm: {problem id: row}} from the blocks that finished."""
    out: dict[str, dict[str, dict]] = {a: {} for a in ARMS}
    for key, block in run["blocks"].items():
        arm = key.split("/")[0]
        if arm not in out:
            raise KeyError(f"WIRING FAILURE: the run has an arm the registration does not: {arm}")
        for row in block["rows"]:
            if row["id"] in out[arm]:
                raise RuntimeError(f"WIRING FAILURE: problem {row['id']} appears twice under arm {arm}")
            out[arm][row["id"]] = row
    return out


def complete(run: dict) -> list[str]:
    """Problems answered under both arms, in the run's fixed order. A half-finished block is left out."""
    rows = per_problem(run)
    return [i for i in run["problem_ids"] if all(i in rows[a] for a in ARMS)]


def q1(ours: dict[str, dict], edited_published: dict[str, list[int]], ids: list[str]) -> dict:
    if len(ids) < MIN_PROBLEMS:
        return {"verdict": "NOT TESTABLE", "n": len(ids)}
    missing = [i for i in ids if i not in edited_published]
    if missing:
        raise KeyError(f"WIRING FAILURE: {len(missing)} of our problems are not in the authors' scores, e.g. {missing[:3]}")
    theirs = [sum(edited_published[i]) / len(edited_published[i]) for i in ids]
    mine = [int(ours[i]["correct"]) for i in ids]
    out = paired([m - t for m, t in zip(mine, theirs)])
    lo, hi = out["interval"]
    out.update({"default_mode_accuracy": sum(mine) / len(mine), "published_edited_thinking_accuracy": sum(theirs) / len(theirs)})
    out["verdict"] = ("AS GOOD OR BETTER" if out["difference"] >= Q1_POINT and lo > Q1_LOWER
                      else "THE EDIT IS AHEAD" if hi < Q1_POINT else "INCONCLUSIVE")
    return out


def q2(unedited: dict[str, dict], edited: dict[str, dict], ids: list[str]) -> dict:
    if len(ids) < MIN_PROBLEMS:
        return {"verdict": "NOT TESTABLE", "n": len(ids)}
    a, b = [int(unedited[i]["correct"]) for i in ids], [int(edited[i]["correct"]) for i in ids]
    out = paired([y - x for x, y in zip(a, b)])
    lo, hi = out["interval"]
    out.update({"unedited_accuracy": sum(a) / len(a), "edited_accuracy": sum(b) / len(b),
                "only_unedited_right": sum(x and not y for x, y in zip(a, b)), "only_edited_right": sum(y and not x for x, y in zip(a, b))})
    out["verdict"] = ("THE EDIT HELPS IN THE DEFAULT MODE" if lo > 0 else "THE EDIT HURTS IN THE DEFAULT MODE" if hi < 0
                      else "NO DIFFERENCE DETECTED")
    return out


def endings(rows: dict[str, dict[str, dict]], ids: list[str]) -> dict:
    """How the answers ended under each arm, and how each problem's ending moved. No rule."""
    kinds = ("finished", "loop", "whitespace", "long")
    out = {a: {k: sum(rows[a][i]["kind"] == k for i in ids) for k in kinds} for a in ARMS}
    for a in ARMS:
        out[a]["mean_tokens"] = sum(rows[a][i]["tokens"] for i in ids) / len(ids) if ids else None
    moved: dict[str, int] = {}
    for i in ids:
        key = f"{rows[ARMS[0]][i]['kind']} -> {rows[ARMS[1]][i]['kind']}"
        moved[key] = moved.get(key, 0) + 1
    out["unedited_to_edited"] = dict(sorted(moved.items()))
    return out


def judge(run: dict, edited_published: dict[str, list[int]], unedited_published: dict[str, list[int]]) -> dict:
    rows, ids = per_problem(run), complete(run)
    out = {"schema": SCHEMA, "prereg": run["prereg"], "problems_complete": len(ids), "problems_planned": len(run["problem_ids"]),
           "Q1": q1(rows[ARMS[0]], edited_published, ids), "Q2": q2(rows[ARMS[0]], rows[ARMS[1]], ids),
           "endings": endings(rows, ids)}
    if ids:
        base = [sum(unedited_published[i]) / len(unedited_published[i]) for i in ids]
        out["published_unedited_thinking_accuracy"] = sum(base) / len(base)
    return out


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.default_verdict")     # this tool reads files written by someone else
    from offtarget.paired import load_per_problem

    ap = argparse.ArgumentParser(description="Apply the rules of prereg/003 to the full-size default-mode run.")
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--eval", required=True, type=Path, help="the logs repo's exp8_math/eval folder")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    run = json.loads(args.run.read_text(encoding="utf-8"))
    verdict = judge(run, load_per_problem(args.eval, "p50c")["math500"], load_per_problem(args.eval, "unedited")["math500"])
    args.out.write_text(json.dumps(verdict, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"complete problems: {verdict['problems_complete']} of {verdict['problems_planned']}")
    for q in ("Q1", "Q2"):
        print(q, verdict[q]["verdict"], {k: (round(v, 4) if isinstance(v, float) else v) for k, v in verdict[q].items() if k != "verdict"})
    print("endings", verdict["endings"])


if __name__ == "__main__":
    main()

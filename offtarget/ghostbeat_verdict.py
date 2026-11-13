# offtarget · offtarget/ghostbeat_verdict.py
# v0.2 · 11NOV2026 (at the freeze: a control too soft to count now reads CONTROL FAILED, as the registration says)
#
# Practical: applies the decision rules of prereg/002 to the registered run and
# writes the verdicts. No model, no torch. Every threshold in the registration is a
# named constant here, and the tests feed this file planted outcomes to prove each
# rule lands on the side the registration says it should.
#   python -I -m offtarget.ghostbeat_verdict --run results/ghostbeat_registered.json --out results/ghostbeat_verdict.json
#
# Philosophical: the judging was done when the registration was written. This file
# is the clerk who reads the verdict out. It is deliberately dull, and it is written
# before the run so that nobody, me least of all, gets to pick the reading after
# seeing which way the numbers fell.
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SCHEMA = "offtarget.ghostbeat_verdict/0.1"
S_MIN_EVENTS, S_MAX_EVENTS = 4, 8      # the analysis set for lists
MIN_SET = 30                           # under this, a question is not testable
Q1_MIN_SHARE, Q1_LOWER = 0.25, 0.10
Q2_MIN_RISE, Q2_MAX_DIP = 0.15, 0.03
Q2_LINE, Q2_MIN_EVENTS = 3, 5          # p(stop) is read at the end of line 3, on lists of 5 or more
Q3_HALF, Q3_MAX_FOR_SPECIAL, Q3_MIN_FOR_DAMAGE, Q3_WEAK_CONTROL = 0.5, 1, 4, 0.5    # counts are out of eight directions
Q4_MIN_POINTS, Q4_MIN_FIXED, Q4_MIN_BASE_SHORT = 0.75, 0.5, 15
Q5_MAX_SHARE, Q5_UPPER, Q5_HARM_LOWER = 0.10, 0.20, 0.10
DOSES = ("dose:0", "dose:1", "dose:2", "dose:4", "dose:6")
RANDOM = ("random:0", "random:1", "random:2")        # same distance in weight space, as usually specified
MATCHED = tuple(f"matched:{k}" for k in range(8))     # eight random directions, scaled to push as hard as the edit
PUSH_IN = "dose:-6"                                   # the published dose with its sign reversed


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        raise ValueError("WIRING FAILURE: an interval on nothing")
    p = k / n
    d = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, mid - half), min(1.0, mid + half)


def _share(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "share": k / n, "interval": [lo, hi]}


def analysis_set(lists: list[dict]) -> list[dict]:
    """Lists of 4 to 8 events the unedited model got exactly right. Fixed by the unedited model alone."""
    return [r for r in lists if S_MIN_EVENTS <= r["n"] <= S_MAX_EVENTS and r["arms"]["dose:0"]["outcome"] == "exact"]


def short(r: dict, arm: str) -> bool:
    return r["arms"][arm]["entries"] < r["n"]


def long(r: dict, arm: str) -> bool:
    return r["arms"][arm]["entries"] > r["n"]


def q1(s: list[dict]) -> dict:
    if len(s) < MIN_SET:
        return {"verdict": "NOT TESTABLE", "n": len(s)}
    out = _share(sum(short(r, "dose:6") for r in s), len(s))
    lo, hi = out["interval"]
    out["verdict"] = ("SUPPORTED" if out["share"] >= Q1_MIN_SHARE and lo > Q1_LOWER
                      else "NOT SUPPORTED" if hi < Q1_LOWER else "INCONCLUSIVE")
    return out


def mean_p_stop(lists: list[dict], arm: str, line: int = Q2_LINE, min_events: int = Q2_MIN_EVENTS) -> float:
    vals = [r["arms"][arm]["p_stop"][line - 1] for r in lists if r["n"] >= min_events]
    if not vals:
        raise ValueError("WIRING FAILURE: no list long enough to read p(stop) at that line")
    return sum(vals) / len(vals)


def q2(s: list[dict], lists: list[dict]) -> dict:
    if len(s) < MIN_SET:
        return {"verdict": "NOT TESTABLE", "n": len(s)}
    shares = {a: sum(short(r, a) for r in s) / len(s) for a in DOSES[1:]}
    stops = {a: mean_p_stop(lists, a) for a in DOSES}
    seq, p = [shares[a] for a in DOSES[1:]], [stops[a] for a in DOSES]
    rises = seq[-1] - seq[0] >= Q2_MIN_RISE
    no_dip = all(b >= a - Q2_MAX_DIP for a, b in zip(seq, seq[1:]))
    p_up = all(b > a for a, b in zip(p, p[1:]))
    return {"short_share": shares, "mean_p_stop_line3": stops, "rise_dose1_to_6": seq[-1] - seq[0],
            "no_dip": no_dip, "p_stop_rises_every_step": p_up,
            "verdict": "SUPPORTED" if rises and no_dip and p_up else "NOT SUPPORTED"}


def q3(s: list[dict], delivered: dict, q1_verdict: str) -> dict:
    if q1_verdict != "SUPPORTED":
        return {"verdict": "NOT READ", "why": "only read if Q1 is supported"}
    edit = sum(short(r, "dose:6") for r in s) / len(s)

    def read(arms: tuple[str, ...]) -> dict:
        per = {a: sum(short(r, a) for r in s) / len(s) for a in arms}
        push = {layer: sum(delivered[a][layer] for a in arms) / len(arms) / delivered["dose:6"][layer] for layer in delivered["dose:6"]}
        return {"short_share": per, "mean": sum(per.values()) / len(per), "push_relative_to_edit": push,
                "other_breakage": {a: sum(r["arms"][a]["outcome"] != "exact" and not short(r, a) for r in s) / len(s) for a in arms}}

    matched, usual = read(MATCHED), read(RANDOM)
    as_much = sum(v >= Q3_HALF * edit for v in matched["short_share"].values())      # directions that do at least half as much
    # A control that pushes under half as hard as the edit, on either layer, has not tested anything.
    # Then the count below means nothing, and the verdict says so instead of flattering the edit.
    weak = any(v < Q3_WEAK_CONTROL for v in matched["push_relative_to_edit"].values())
    verdict = ("CONTROL FAILED" if weak
               else "THE DIRECTION MATTERS" if as_much <= Q3_MAX_FOR_SPECIAL
               else "DAMAGE IN THE RIGHT PLACE" if as_much >= Q3_MIN_FOR_DAMAGE else "INCONCLUSIVE")
    return {"edit_short_share": edit, "edit_not_exact_share": sum(r["arms"]["dose:6"]["outcome"] != "exact" for r in s) / len(s),
            "matched_directions_doing_at_least_half_as_much": as_much, "of": len(MATCHED),
            "matched": matched, "as_usually_specified": usual, "control_is_weak": weak,
            "verdict": verdict}


def q4(s: list[dict], lists: list[dict]) -> dict:
    below = total = 0
    for r in lists:
        for k in range(r["n"] - 1):                    # line ends where true events remain
            total += 1
            below += r["arms"][PUSH_IN]["p_stop"][k] < r["arms"]["dose:0"]["p_stop"][k]
    points = below / total
    base_short = [r for r in lists if short(r, "dose:0")]                 # where the unedited model itself drops a line
    out = {"points_where_p_stop_is_lower": points, "points": total, "unedited_short": len(base_short),
           "long_share_of_S": {a: (sum(long(r, a) for r in s) / len(s) if s else None) for a in (PUSH_IN, "dose:-2")}}
    if len(base_short) < Q4_MIN_BASE_SHORT:
        out["verdict"] = "MECHANISM ONLY, SUPPORTED" if points >= Q4_MIN_POINTS else "NOT SUPPORTED"
        return out
    fixed = _share(sum(not short(r, PUSH_IN) for r in base_short), len(base_short))
    out["no_longer_short"] = fixed
    out["made_exact"] = sum(r["arms"][PUSH_IN]["outcome"] == "exact" for r in base_short) / len(base_short)
    out["verdict"] = "SUPPORTED" if points >= Q4_MIN_POINTS and fixed["share"] >= Q4_MIN_FIXED else "NOT SUPPORTED"
    return out


def q5(twins: list[dict]) -> dict:
    base_exact = [r for r in twins if r["arms"]["dose:0"]["outcome"] == "exact"]
    if len(base_exact) < MIN_SET:
        return {"verdict": "NOT TESTABLE", "n": len(base_exact)}
    out = _share(sum(r["arms"]["dose:6"]["outcome"] != "exact" for r in base_exact), len(base_exact))
    lo, hi = out["interval"]
    out["verdict"] = ("NO HARM AT THIS SIZE" if out["share"] <= Q5_MAX_SHARE and hi < Q5_UPPER
                      else "HARM" if lo > Q5_HARM_LOWER else "INCONCLUSIVE")
    out["fixed_by_the_edit"] = sum(r["arms"]["dose:0"]["outcome"] != "exact" and r["arms"]["dose:6"]["outcome"] == "exact" for r in twins)
    return out


def q6(s: list[dict], lists: list[dict]) -> dict:
    if not s:
        return {"n": 0}
    base = mean_p_stop(lists, "dose:0")
    return {a: {"short_share": sum(short(r, a) for r in s) / len(s), "p_stop_line3_change": mean_p_stop(lists, a) - base}
            for a in ("only:15", "only:19", "dose:6")}


def judge(run: dict) -> dict:
    lists, twins = run["lists"], run["twins"]
    s = analysis_set(lists)
    one = q1(s)
    return {"schema": SCHEMA, "prereg": run["prereg"], "analysis_set": len(s), "lists": len(lists), "twins": len(twins),
            "Q1": one, "Q2": q2(s, lists), "Q3": q3(s, run["delivered"], one["verdict"]), "Q4": q4(s, lists),
            "Q5": q5(twins), "Q6": q6(s, lists)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply the rules of prereg/002 to the registered run.")
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    verdict = judge(json.loads(args.run.read_text(encoding="utf-8")))
    args.out.write_text(json.dumps(verdict, indent=1) + "\n", encoding="utf-8", newline="\n")
    for q in ("Q1", "Q2", "Q3", "Q4", "Q5"):
        print(q, verdict[q]["verdict"], {k: v for k, v in verdict[q].items()
                                         if k in ("k", "n", "share", "interval", "rise_dose1_to_6", "matched_directions_doing_at_least_half_as_much")})
    print("Q6", verdict["Q6"])


if __name__ == "__main__":
    main()

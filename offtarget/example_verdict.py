# offtarget · offtarget/example_verdict.py
# v0.1 · 12NOV2026
#
# Practical: applies the decision rules of prereg/004. The instruction's example
# sentence is swapped between "two", "three", "five" and one with no number, and
# this file asks whether the length of the edited model's short handoffs follows
# the example, whether three random pushes of the same size follow it too, and
# whether a small reversed dose makes the model better at the task. No model, no
# torch. Every threshold in the registration is a named constant here.
#   python -I -m offtarget.example_verdict --run results/example_registered.json --out results/example_verdict.json
#
# Philosophical: registration 002 handed me a tidy story (the edited model stops at
# the third identical line) with a loose thread hanging out of it (the word "three"
# is in the instruction). Pulling the thread is the whole job here. If the story
# comes apart, better that it comes apart in my hands than in a reader's.
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from offtarget.default_verdict import paired
from offtarget.ghostbeat_verdict import short, wilson

SCHEMA = "offtarget.example_verdict/0.1"
NUMBER = {"two": 2, "three": 3, "five": 5}      # the numbered examples and the line count each one names
MIN_SET, MIN_SHORT = 30, 15                     # under these a question cannot be read
MIN_SHARE = 0.40                                # the example's number must be this common under "two" and "five"
EDIT = ("dose:6",)
MATCHED = ("matched:2", "matched:4", "matched:5")
REVERSED = "dose:-2"
CURVE = ("dose:-4", "dose:-3", "dose:-2", "dose:-1", "dose:0", "dose:1", "dose:2", "dose:3", "dose:4", "dose:6")


def s_of(lists: list[dict], example: str) -> list[dict]:
    """The lists asked with this example that the unedited model reported exactly."""
    return [r for r in lists if r["example"] == example and r["arms"]["dose:0"]["outcome"] == "exact"]


def lengths(s: list[dict], arms: tuple[str, ...]) -> Counter:
    """How many lines the short handoffs have, pooled over the given arms."""
    return Counter(r["arms"][a]["entries"] for r in s for a in arms if short(r, a))


def follows(lists: list[dict], arms: tuple[str, ...]) -> dict:
    """Does the length of the short handoffs under these arms follow the example's number?"""
    per, testable = {}, True
    for example, k in NUMBER.items():
        s = s_of(lists, example)
        c = lengths(s, arms)
        total = sum(c.values())
        top = max(c.values()) if c else 0
        modal = sorted(n for n, v in c.items() if v == top) if c else []
        per[example] = {"S": len(s), "short": total, "lengths": {str(n): v for n, v in sorted(c.items())}, "most_common": modal,
                        "share_at_the_examples_number": (c[k] / total if total else None),
                        "share_at_three": (c[3] / total if total else None)}
        testable = testable and len(s) >= MIN_SET and total >= MIN_SHORT
    if not testable:
        return {"verdict": "NOT TESTABLE", "by_example": per}
    # "most common" means alone at the top. A tie is not a win for anybody.
    on_example = all(per[e]["most_common"] == [k] for e, k in NUMBER.items())
    strong = all(per[e]["share_at_the_examples_number"] >= MIN_SHARE for e in ("two", "five"))
    on_three = all(per[e]["most_common"] == [3] for e in NUMBER)
    verdict = "FOLLOWS THE EXAMPLE" if on_example and strong else "THREE REGARDLESS" if on_three else "MIXED"
    return {"verdict": verdict, "by_example": per}


def reversed_dose(lists: list[dict]) -> dict:
    """Net effect of the small reversed dose on exactness, over every list asked with the "three" example."""
    mine = [r for r in lists if r["example"] == "three"]
    if len(mine) < MIN_SET:
        return {"verdict": "NOT TESTABLE", "n": len(mine)}
    base = [int(r["arms"]["dose:0"]["outcome"] == "exact") for r in mine]
    rev = [int(r["arms"][REVERSED]["outcome"] == "exact") for r in mine]
    out = paired([b - a for a, b in zip(base, rev)])
    lo, hi = out["interval"]
    misses = [r for r in mine if short(r, "dose:0")]
    out.update({"unedited_exact": sum(base), "reversed_exact": sum(rev),
                "made_exact": sum(b and not a for a, b in zip(base, rev)), "broken": sum(a and not b for a, b in zip(base, rev)),
                "unedited_misses": len(misses), "misses_made_exact": sum(r["arms"][REVERSED]["outcome"] == "exact" for r in misses)})
    out["verdict"] = "HELPS" if lo > 0 else "HURTS" if hi < 0 else "NO DIFFERENCE DETECTED"
    return out


def described(lists: list[dict]) -> dict:
    """Reported without a rule: the short share by example, the two-sided curve, and how short handoffs ended."""
    by_example = {}
    for example in ("three", "two", "five", "none"):
        s = s_of(lists, example)
        k = sum(short(r, "dose:6") for r in s)
        by_example[example] = {"S": len(s), "short": k, "share": k / len(s) if s else None,
                               "interval": list(wilson(k, len(s))) if s else None,
                               "lengths": {str(n): v for n, v in sorted(lengths(s, EDIT).items())}}
    three = [r for r in lists if r["example"] == "three"]
    curve = {a: (sum(r["arms"][a]["outcome"] == "exact" for r in three) / len(three) if three else None) for a in CURVE}
    arms = sorted({a for r in lists for a in r["arms"]})
    good = [r for r in lists if r["arms"]["dose:0"]["outcome"] == "exact"]
    endings = {}
    for a in arms:
        sh = [r for r in good if short(r, a)]
        endings[a] = {"short": len(sh), "with_END": sum(r["arms"][a]["ended"] for r in sh),
                      "went_quiet": sum(not r["arms"][a]["ended"] for r in sh)}
    return {"short_under_the_edit_by_example": by_example, "exact_share_by_dose_three_example": curve,
            "how_short_handoffs_ended": endings}


def judge(run: dict) -> dict:
    lists = run["lists"]
    return {"schema": SCHEMA, "prereg": run["prereg"], "lists": len(lists),
            "Q1": follows(lists, EDIT), "Q2": follows(lists, MATCHED), "Q3": reversed_dose(lists), "described": described(lists)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply the rules of prereg/004.")
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    v = judge(json.loads(args.run.read_text(encoding="utf-8")))
    args.out.write_text(json.dumps(v, indent=1) + "\n", encoding="utf-8", newline="\n")
    for q in ("Q1", "Q2"):
        print(q, v[q]["verdict"])
        for example, r in v[q]["by_example"].items():
            print(f"   {example:<5} S {r['S']:>3}  short {r['short']:>3}  lengths {r['lengths']}  most common {r['most_common']}")
    q3 = v["Q3"]
    print("Q3", q3["verdict"], {k: (round(x, 4) if isinstance(x, float) else x) for k, x in q3.items() if k != "verdict"})
    d = v["described"]
    print("short under the edit by example:", {e: f"{r['short']}/{r['S']}" for e, r in d["short_under_the_edit_by_example"].items()})
    print("exact share by dose, three example:", {a: (round(x, 3) if x is not None else None) for a, x in d["exact_share_by_dose_three_example"].items()})
    print("how short handoffs ended:", d["how_short_handoffs_ended"])


if __name__ == "__main__":
    main()

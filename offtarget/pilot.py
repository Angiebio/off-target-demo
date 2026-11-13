# offtarget · offtarget/pilot.py
# v0.1 · 11NOV2026
#
# Practical: applies the decision rules of prereg/001 to the two pilot runs and
# writes the verdicts. Run A: did loops fall by at least 40 points between alpha 0
# and alpha 6? Run B: is the base model in its default mode within 5 points of the
# edited model, on the same problems? Run it as:
#   python -I -m offtarget.pilot --dose results/pilot_dose.json --default results/pilot_default_mode.json \
#       --eval <logs>/exp8_math/eval --out results/pilot_verdict.json
#
# Philosophical: the rules were written down before the runs so that this file
# could be boring. It does no judging of its own. It reads two numbers, compares
# them with thresholds somebody committed to in advance, and prints which side they
# fell on. The interesting thinking happened in the pre-registration. All that is
# left here is to keep the promise.
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from offtarget.paired import load_per_problem

SCHEMA = "offtarget.pilot/0.1"
A_MIN_DROP = 0.40      # prereg 001, run A
B_MARGIN = 0.05        # prereg 001, run B


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a proportion. Behaves at 0 and n, unlike the textbook one."""
    if n == 0:
        raise ValueError("WIRING FAILURE: an interval needs at least one observation")
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def subset_accuracy(per_problem: dict[str, list[int]], ids: list[str]) -> dict:
    """The authors' accuracy (mean over all samples) on a chosen subset of problems."""
    missing = [i for i in ids if i not in per_problem]
    if missing:
        raise KeyError(f"WIRING FAILURE: {len(missing)} of our problems are not in the authors' scores, e.g. {missing[:3]}")
    samples = [c for i in ids for c in per_problem[i]]
    return {"problems": len(ids), "samples": len(samples), "accuracy": sum(samples) / len(samples)}


def verdict_a(dose: dict) -> dict:
    doses = dose["doses"]
    for needed in ("0.0", "6.0"):
        if needed not in doses:
            raise KeyError(f"WIRING FAILURE: the dose run has no alpha {needed}")
    n = doses["0.0"]["n"]
    loops = {a: d["loop_share"] for a, d in doses.items()}
    drop = loops["0.0"] - loops["6.0"]
    between = "1.0" in loops and loops["6.0"] < loops["1.0"] < loops["0.0"]
    return {
        "n_per_dose": n,
        "loop_share": loops,
        "loop_share_interval": {a: wilson(round(d["loop_share"] * d["n"]), d["n"]) for a, d in doses.items()},
        "drop_alpha0_to_alpha6": drop,
        "threshold": A_MIN_DROP,
        "pass": drop >= A_MIN_DROP,
        "predictions": {
            "alpha0_at_least_70pct": loops["0.0"] >= 0.70,
            "alpha6_at_most_30pct": loops["6.0"] <= 0.30,
            "alpha1_strictly_between": between,
        },
    }


def verdict_b(default: dict, eval_dir: Path) -> dict:
    d = default["doses"]["0.0"]
    ids = default["problem_ids"]
    n = d["n"]
    k = round(d["accuracy"] * n)
    edited = subset_accuracy(load_per_problem(eval_dir, "p50c")["math500"], ids)
    base_think = subset_accuracy(load_per_problem(eval_dir, "unedited")["math500"], ids)
    gap = edited["accuracy"] - d["accuracy"]
    return {
        "n": n,
        "default_mode_accuracy": d["accuracy"],
        "default_mode_interval": wilson(k, n),
        "default_mode_kinds": {key: d[key] for key in ("finished", "loop", "whitespace", "long")},
        "default_mode_mean_tokens": d["mean_tokens"],
        "published_edited_thinking_same_problems": edited,
        "published_base_thinking_same_problems": base_think,
        "edited_minus_default": gap,
        "margin": B_MARGIN,
        "report": (
            "the documented default setting does about as well as the weight edit on MATH-500"
            if gap <= B_MARGIN else
            "the edit has an advantage over the default setting"
        ),
    }


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.pilot")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="Apply the pre-registered decision rules to the pilot runs.")
    ap.add_argument("--dose", type=Path)
    ap.add_argument("--default", type=Path)
    ap.add_argument("--eval", type=Path, help="the logs repo's exp8_math/eval folder (needed for run B)")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    out: dict = {"schema": SCHEMA, "prereg": "prereg/001-pilot-dose-and-default-mode.md"}
    if args.dose:
        a = out["run_a"] = verdict_a(json.loads(args.dose.read_text(encoding="utf-8")))
        print(f"Run A: loop share {', '.join(f'alpha {k}: {v:.1%}' for k, v in a['loop_share'].items())}")
        print(f"  drop from alpha 0 to alpha 6: {a['drop_alpha0_to_alpha6']:.1%} (needs {A_MIN_DROP:.0%}) -> "
              f"{'PASS' if a['pass'] else 'FAIL'}")
        print(f"  predictions held: {a['predictions']}")
    if args.default:
        if not args.eval:
            raise SystemExit("WIRING FAILURE: run B needs --eval to find the published comparators")
        b = out["run_b"] = verdict_b(json.loads(args.default.read_text(encoding="utf-8")), args.eval)
        lo, hi = b["default_mode_interval"]
        print(f"Run B: default mode {b['default_mode_accuracy']:.1%} (95% {lo:.1%} to {hi:.1%}, n {b['n']})")
        print(f"  published, same problems: edited thinking {b['published_edited_thinking_same_problems']['accuracy']:.1%}, "
              f"base thinking {b['published_base_thinking_same_problems']['accuracy']:.1%}")
        print(f"  edited minus default: {b['edited_minus_default']:+.1%} -> {b['report']}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()

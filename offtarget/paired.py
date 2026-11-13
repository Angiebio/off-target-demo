# offtarget · offtarget/paired.py
# v0.1 · 11NOV2026
#
# Practical: the authors published, for every benchmark problem, whether each sample
# was right, for the base model and for each edited model. This file lines the two
# models up problem by problem and counts what a table of averages hides: problems
# rescued, problems lost, and how the edit treated the problems the base model could
# already do. Run it as:
#   python -I -m offtarget.paired --eval <logs>/exp8_math/eval --edited p50c --out results/paired.json
#
# Philosophical: an average going up is a statement about a crowd. A regulator, a
# clinician and a careful engineer all ask the next question, which is about
# individuals: who got worse? A treatment that helps most patients and quietly harms
# a few is a different product from one that helps most and harms none, and the two
# can post the same mean. Before the numbers are trusted, the tool recomputes each
# benchmark's accuracy from the per-problem files and insists it equals the authors'
# own merged score. If our reading of their files is wrong, we find out here.
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "offtarget.paired/0.1"
SUFFIX = "_per_problem.json"
RELIABLE = 0.75   # the base model "could already do" a problem at this share of samples


def load_per_problem(eval_dir: Path, model: str) -> dict[str, dict[str, list[int]]]:
    """{benchmark: {problem id: [0/1 per sample]}} for one model."""
    parts = eval_dir / model / "parts"
    if not parts.is_dir():
        raise FileNotFoundError(f"WIRING FAILURE: no evaluation parts at {parts}")
    out: dict[str, dict[str, list[int]]] = {}
    for part in sorted(parts.iterdir()):
        for f in sorted(part.glob(f"*{SUFFIX}")):
            bench = f.name[: -len(SUFFIX)]
            for row in json.loads(f.read_text(encoding="utf-8")):
                problems = out.setdefault(bench, {})
                if row["id"] in problems:
                    raise RuntimeError(f"WIRING FAILURE: problem {row['id']} appears twice in {model}/{bench}")
                problems[row["id"]] = [int(c) for c in row["correct"]]
    return out


def accuracy(problems: dict[str, list[int]]) -> float:
    """Mean over all samples, the authors' definition."""
    samples = [c for corr in problems.values() for c in corr]
    return sum(samples) / len(samples)


def verify_against_merged(eval_dir: Path, model: str, data: dict[str, dict[str, list[int]]], tol: float = 1e-9) -> None:
    merged = json.loads((eval_dir / model / "merged.json").read_text(encoding="utf-8"))
    for bench, problems in data.items():
        if bench not in merged:
            raise KeyError(f"WIRING FAILURE: {bench} has per-problem files but no merged score for {model}")
        ours, theirs = accuracy(problems), merged[bench]["acc"]
        if abs(ours - theirs) > tol:
            raise RuntimeError(
                f"WIRING FAILURE: {model}/{bench} accuracy recomputed as {ours:.6f}, merged.json says {theirs:.6f}"
            )


def compare(base: dict[str, list[int]], edited: dict[str, list[int]]) -> dict:
    """Pair two models on the problems they share."""
    if set(base) != set(edited):
        raise RuntimeError(
            f"WIRING FAILURE: the two models were scored on different problems "
            f"({len(set(base) - set(edited))} only in base, {len(set(edited) - set(base))} only in edited)"
        )
    improved = regressed = same = rescued = lost = 0
    reliable: list[float] = []
    for pid, b in base.items():
        e = edited[pid]
        mb, me = sum(b) / len(b), sum(e) / len(e)
        improved += me > mb
        regressed += me < mb
        same += me == mb
        rescued += (not any(b)) and any(e)
        lost += any(b) and (not any(e))
        if mb >= RELIABLE:
            reliable.append(me)
    return {
        "problems": len(base),
        "samples_per_problem": len(next(iter(base.values()))),
        "acc_base": accuracy(base),
        "acc_edited": accuracy(edited),
        "improved": improved,
        "regressed": regressed,
        "same": same,
        "rescued_from_zero": rescued,
        "lost_to_zero": lost,
        "base_reliable_problems": len(reliable),
        "edited_acc_on_base_reliable": sum(reliable) / len(reliable) if reliable else None,
    }


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.paired")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="Pair the base and an edited model problem by problem.")
    ap.add_argument("--eval", required=True, type=Path)
    ap.add_argument("--base", default="unedited")
    ap.add_argument("--edited", default="p50c")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    b, e = load_per_problem(args.eval, args.base), load_per_problem(args.eval, args.edited)
    verify_against_merged(args.eval, args.base, b)
    verify_against_merged(args.eval, args.edited, e)
    report = {"schema": SCHEMA, "base": args.base, "edited": args.edited, "reliable_threshold": RELIABLE,
              "benchmarks": {bench: compare(b[bench], e[bench]) for bench in sorted(set(b) & set(e))}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")

    print("recomputed accuracies equal the authors' merged scores for every benchmark")
    print(f"{'bench':10} {'n':>5} {'k':>2} {'base':>6} {'edit':>6} {'better':>6} {'worse':>6} {'rescued':>7} "
          f"{'lost':>5} {'base-reliable n':>15} {'edit acc there':>14}")
    for bench, c in report["benchmarks"].items():
        there = f"{c['edited_acc_on_base_reliable']:.1%}" if c["base_reliable_problems"] else "-"
        print(f"{bench:10} {c['problems']:>5} {c['samples_per_problem']:>2} {c['acc_base']:>6.1%} {c['acc_edited']:>6.1%} "
              f"{c['improved']:>6} {c['regressed']:>6} {c['rescued_from_zero']:>7} {c['lost_to_zero']:>5} "
              f"{c['base_reliable_problems']:>15} {there:>14}")


if __name__ == "__main__":
    main()

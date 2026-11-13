# offtarget · offtarget/default_report.py
# v0.1 · 12NOV2026
#
# Practical: the tables prereg/003 promised "without a rule", and a few more that
# make the verdict readable. The four accuracies side by side (unedited and edited,
# thinking on from the authors and thinking off from us), the pilot's hundred
# problems against their fresh draw, each block of a hundred, accuracy by how the
# answer ended, how each problem's ending moved between arms and what that did to
# its mark, and the picture by subject. No model, no torch, no thresholds.
#   python -I -m offtarget.default_report --run results/default_mode_full.json \
#       --eval <logs>/exp8_math/eval --pilot results/pilot_default_mode.json \
#       --out results/default_mode_report.json
#
# Philosophical: a verdict is one word, and one word can flatter. "AS GOOD OR
# BETTER" came back on a run where the default setting finished a few points
# behind, inside the margin I had drawn. The clerk said what the rule says. This
# file is the room around the clerk: every count that lets a reader see how close
# to the edge of the rule the answer sat, written by someone with no stake in
# which side of it they land on.
from __future__ import annotations

import argparse
import json
from pathlib import Path

from offtarget import default_verdict as dv

SCHEMA = "offtarget.default_report/0.1"
KINDS = ("finished", "loop", "whitespace", "long")
UNEDITED, EDITED = dv.ARMS


def _share(published: dict[str, list[int]], ids: list[str]) -> float | None:
    """The authors' accuracy on these problems: the mean over problems of the share of their samples that were right."""
    return sum(sum(published[i]) / len(published[i]) for i in ids) / len(ids) if ids else None


def _right(rows: dict[str, dict], ids: list[str]) -> int:
    return sum(bool(rows[i]["correct"]) for i in ids)


def four_accuracies(rows: dict, ids: list[str], edited_published: dict, unedited_published: dict) -> dict:
    """Two models by two settings. Thinking on is the authors' (four samples a problem), thinking off is ours (one)."""
    n = len(ids)
    return {
        "n": n,
        "unedited": {"thinking_on_published": _share(unedited_published, ids), "thinking_off_ours": _right(rows[UNEDITED], ids) / n},
        "edited": {"thinking_on_published": _share(edited_published, ids), "thinking_off_ours": _right(rows[EDITED], ids) / n},
    }


def slice_table(rows: dict, ids: list[str], edited_published: dict, unedited_published: dict) -> dict:
    """One group of problems: how many each of our arms got right, and the authors' shares on the same problems."""
    return {"n": len(ids), "unedited_right": _right(rows[UNEDITED], ids), "edited_right": _right(rows[EDITED], ids),
            "published_edited_thinking": _share(edited_published, ids), "published_unedited_thinking": _share(unedited_published, ids)}


def pilots_hundred(run: dict, rows: dict, ids: list[str], edited_published: dict, unedited_published: dict, pilot: dict | None) -> dict:
    """The first hundred problems are the pilot's hundred. Same problems, fresh seeds."""
    first = [i for i in run["problem_ids"][:100] if i in set(ids)]
    out = slice_table(rows, first, edited_published, unedited_published)
    if pilot is not None:
        if pilot["problem_ids"] != run["problem_ids"][:100]:
            raise RuntimeError("WIRING FAILURE: the pilot's problems are not this run's first hundred")
        was = {r["id"]: bool(r["correct"]) for r in pilot["doses"]["0.0"]["per_problem"]}
        now = {i: bool(rows[UNEDITED][i]["correct"]) for i in first}
        out["pilot_unedited_right"] = sum(was[i] for i in first)
        out["right_both_times"] = sum(was[i] and now[i] for i in first)
        out["right_in_the_pilot_only"] = sum(was[i] and not now[i] for i in first)
        out["right_this_time_only"] = sum(now[i] and not was[i] for i in first)
    return out


def by_block(run: dict, rows: dict, ids: list[str], edited_published: dict, unedited_published: dict) -> dict:
    size, done = run["block"], set(ids)
    out = {}
    for b in range(0, len(run["problem_ids"]), size):
        mine = [i for i in run["problem_ids"][b:b + size] if i in done]
        if mine:
            out[f"block{b // size}"] = slice_table(rows, mine, edited_published, unedited_published)
    return out


def by_ending(rows: dict, ids: list[str]) -> dict:
    """For each arm and each way of ending: how many answers, and how many of them were right."""
    return {arm: {k: {"n": sum(rows[arm][i]["kind"] == k for i in ids),
                      "right": sum(rows[arm][i]["kind"] == k and bool(rows[arm][i]["correct"]) for i in ids)} for k in KINDS}
            for arm in dv.ARMS}


def moves(rows: dict, ids: list[str]) -> dict:
    """Each problem's ending under the unedited arm and under the edited one, with the marks on both sides."""
    out: dict[str, dict] = {}
    for i in ids:
        a, b = rows[UNEDITED][i], rows[EDITED][i]
        cell = out.setdefault(f"{a['kind']} -> {b['kind']}", {"n": 0, "right_unedited": 0, "right_edited": 0, "gained": 0, "lost": 0})
        cell["n"] += 1
        cell["right_unedited"] += bool(a["correct"])
        cell["right_edited"] += bool(b["correct"])
        cell["gained"] += bool(b["correct"]) and not bool(a["correct"])
        cell["lost"] += bool(a["correct"]) and not bool(b["correct"])
    return dict(sorted(out.items()))


def subject(problem_id: str) -> str:
    """'test/number_theory/1065.json' -> 'number_theory'."""
    parts = problem_id.split("/")
    if len(parts) != 3:
        raise ValueError(f"WIRING FAILURE: a problem id that does not name its subject: {problem_id}")
    return parts[1]


def by_subject(rows: dict, ids: list[str], edited_published: dict, unedited_published: dict) -> dict:
    return {s: slice_table(rows, [i for i in ids if subject(i) == s], edited_published, unedited_published)
            for s in sorted({subject(i) for i in ids})}


def report(run: dict, edited_published: dict, unedited_published: dict, pilot: dict | None = None) -> dict:
    rows, ids = dv.per_problem(run), dv.complete(run)
    if not ids:
        raise RuntimeError("WIRING FAILURE: no problem was answered under both arms, so there is nothing to tabulate")
    return {
        "schema": SCHEMA, "prereg": run["prereg"], "problems_complete": len(ids),
        "four_accuracies": four_accuracies(rows, ids, edited_published, unedited_published),
        "pilots_hundred": pilots_hundred(run, rows, ids, edited_published, unedited_published, pilot),
        "by_block": by_block(run, rows, ids, edited_published, unedited_published),
        "by_ending": by_ending(rows, ids),
        "moves": moves(rows, ids),
        "by_subject": by_subject(rows, ids, edited_published, unedited_published),
        "mean_tokens": {arm: sum(rows[arm][i]["tokens"] for i in ids) / len(ids) for arm in dv.ARMS},
    }


def show(rep: dict) -> None:
    pct = lambda x: "n/a" if x is None else f"{100 * x:.1f}%"
    f = rep["four_accuracies"]
    print(f"{rep['problems_complete']} problems")
    for model in ("unedited", "edited"):
        print(f"  {model:9s} thinking on (theirs) {pct(f[model]['thinking_on_published'])}   thinking off (ours) {pct(f[model]['thinking_off_ours'])}")
    p = rep["pilots_hundred"]
    print(f"the pilot's hundred: unedited {p['unedited_right']}, edited {p['edited_right']}, pilot {p.get('pilot_unedited_right', 'n/a')}, "
          f"theirs edited {pct(p['published_edited_thinking'])}")
    for name, b in rep["by_block"].items():
        print(f"  {name}: unedited {b['unedited_right']}/{b['n']}  edited {b['edited_right']}/{b['n']}  theirs edited {pct(b['published_edited_thinking'])}")
    for arm, kinds in rep["by_ending"].items():
        print(f"  arm {arm}: " + "  ".join(f"{k} {v['right']}/{v['n']}" for k, v in kinds.items()))
    for move, c in rep["moves"].items():
        print(f"  {move:24s} n {c['n']:3d}  right {c['right_unedited']:3d} -> {c['right_edited']:3d}  gained {c['gained']:2d} lost {c['lost']:2d}")
    for s, b in rep["by_subject"].items():
        print(f"  {s:26s} n {b['n']:3d}  unedited {b['unedited_right']:3d}  edited {b['edited_right']:3d}  theirs edited {pct(b['published_edited_thinking'])}")


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.default_report")     # this tool reads files written by someone else
    from offtarget.paired import load_per_problem

    ap = argparse.ArgumentParser(description="The tables of prereg/003 that carry no rule.")
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--eval", required=True, type=Path, help="the logs repo's exp8_math/eval folder")
    ap.add_argument("--pilot", type=Path, help="results/pilot_default_mode.json, to set the pilot beside its fresh draw")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    run = json.loads(args.run.read_text(encoding="utf-8"))
    pilot = json.loads(args.pilot.read_text(encoding="utf-8")) if args.pilot else None
    rep = report(run, load_per_problem(args.eval, "p50c")["math500"], load_per_problem(args.eval, "unedited")["math500"], pilot)
    args.out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    show(rep)


if __name__ == "__main__":
    main()

# offtarget · offtarget/ghostbeat_report.py
# v0.1 · 11NOV2026
#
# Practical: the tables prereg/002 promised "without a rule". Every arm on one
# line, the picture by label and by size, how many lines went missing, the twins
# by kind, and the sampled runs beside the noise between two runs of the same
# model. No model, no torch, no thresholds.
#   python -I -m offtarget.ghostbeat_report --run results/ghostbeat_registered.json --out results/ghostbeat_report.json
#
# Philosophical: the verdict module is a clerk who may only say what the rules
# say. This one is the court reporter. It writes down everything that happened in
# the room, in the order the registration listed it, and it has no opinion. It was
# written while the run was still going, before any number from the held-out
# labels had been read, so that what gets tabulated was not chosen by what looked
# good.
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from offtarget import ghostbeat_verdict as gv

SCHEMA = "offtarget.ghostbeat_report/0.1"


def _p3(lists: list[dict], arm: str) -> float | None:
    """Mean chance of stopping at the end of line 3, on lists of five or more. None if there are none."""
    if not any(r["n"] >= gv.Q2_MIN_EVENTS for r in lists):
        return None
    return gv.mean_p_stop(lists, arm)


def arms_table(run: dict) -> dict:
    """One row per arm: what it did to the lists the unedited model got right, and to all of them."""
    lists, s = run["lists"], gv.analysis_set(run["lists"])
    edit = run["delivered"].get("dose:6", {})
    out = {}
    for arm in run["arms"]:
        out[arm] = {
            "S": {"n": len(s), "short": sum(gv.short(r, arm) for r in s), "long": sum(gv.long(r, arm) for r in s),
                  "exact": sum(r["arms"][arm]["outcome"] == "exact" for r in s)},
            "all": {"n": len(lists), "short": sum(gv.short(r, arm) for r in lists), "long": sum(gv.long(r, arm) for r in lists),
                    "exact": sum(r["arms"][arm]["outcome"] == "exact" for r in lists)},
            "mean_p_stop_line3": _p3(lists, arm),
            "push_relative_to_edit": {layer: (run["delivered"][arm][layer] / edit[layer] if edit.get(layer) else None)
                                      for layer in run["delivered"].get(arm, {})},
        }
    return out


def by_label(run: dict) -> dict:
    out = {}
    for label in run["labels"]:
        mine = [r for r in run["lists"] if r["label"] == label]
        s = gv.analysis_set(mine)
        out[label] = {
            "lists": len(mine), "unedited_exact": sum(r["arms"]["dose:0"]["outcome"] == "exact" for r in mine),
            "unedited_short": sum(gv.short(r, "dose:0") for r in mine), "unedited_long": sum(gv.long(r, "dose:0") for r in mine),
            "S": len(s), "edit_short_in_S": sum(gv.short(r, "dose:6") for r in s),
            "edit_long_in_S": sum(gv.long(r, "dose:6") for r in s),
            "mean_p_stop_line3": {a: _p3(mine, a) for a in ("dose:0", "dose:6")},
        }
    return out


def by_size(run: dict) -> dict:
    out = {}
    for n in sorted({r["n"] for r in run["lists"]}):
        mine = [r for r in run["lists"] if r["n"] == n]
        right = [r for r in mine if r["arms"]["dose:0"]["outcome"] == "exact"]
        out[str(n)] = {
            "lists": len(mine), "unedited_exact": len(right), "unedited_short": sum(gv.short(r, "dose:0") for r in mine),
            "unedited_long": sum(gv.long(r, "dose:0") for r in mine),
            "edit_exact": sum(r["arms"]["dose:6"]["outcome"] == "exact" for r in mine),
            "edit_short_where_unedited_exact": sum(gv.short(r, "dose:6") for r in right),
            "edit_long_where_unedited_exact": sum(gv.long(r, "dose:6") for r in right),
        }
    return out


def shortfall(run: dict, arm: str = "dose:6") -> dict:
    """On the analysis set: for each number of true events, how many lines the arm wrote, and how often."""
    table: dict[str, Counter] = {}
    for r in gv.analysis_set(run["lists"]):
        table.setdefault(str(r["n"]), Counter())[str(r["arms"][arm]["entries"])] += 1
    return {n: dict(sorted(c.items(), key=lambda kv: int(kv[0]))) for n, c in sorted(table.items(), key=lambda kv: int(kv[0]))}


def twins_table(run: dict) -> dict:
    out = {}
    for variant in sorted({r["variant"] for r in run["twins"]}):
        mine = [r for r in run["twins"] if r["variant"] == variant]
        out[variant] = {
            "logs": len(mine),
            "outcomes": {a: dict(Counter(r["arms"][a]["outcome"] for r in mine)) for a in ("dose:0", "dose:6")},
            "exact_then_not": sum(r["arms"]["dose:0"]["outcome"] == "exact" and r["arms"]["dose:6"]["outcome"] != "exact" for r in mine),
            "not_then_exact": sum(r["arms"]["dose:0"]["outcome"] != "exact" and r["arms"]["dose:6"]["outcome"] == "exact" for r in mine),
        }
    return out


def sampled_table(run: dict) -> dict:
    """The vendor's sampling on the same logs. Two unedited runs give the noise an edited run has to beat."""
    if not run.get("sampled"):
        return {}
    a, b, e = "dose:0/seed0", "dose:0/seed1", "dose:6/seed0"
    out = {}
    for kind, truth in (("lists", [r["n"] for r in run["lists"]]), ("twins", [r["events"] for r in run["twins"]])):
        rows = {k: run["sampled"][k][kind] for k in (a, b, e)}
        out[kind] = {
            "logs": len(truth),
            "exact": {k: sum(r["outcome"] == "exact" for r in v) for k, v in rows.items()},
            "short": {k: sum(r["entries"] < n for r, n in zip(v, truth)) for k, v in rows.items()},
            "long": {k: sum(r["entries"] > n for r, n in zip(v, truth)) for k, v in rows.items()},
            "exactness_differs_between_two_unedited_runs": sum((x["outcome"] == "exact") != (y["outcome"] == "exact") for x, y in zip(rows[a], rows[b])),
            "exactness_differs_unedited_to_edited": sum((x["outcome"] == "exact") != (y["outcome"] == "exact") for x, y in zip(rows[a], rows[e])),
        }
    return out


def report(run: dict) -> dict:
    return {"schema": SCHEMA, "prereg": run["prereg"], "status": run.get("status"), "analysis_set": len(gv.analysis_set(run["lists"])),
            "arms": arms_table(run), "by_label": by_label(run), "by_size": by_size(run),
            "lines_written_by_the_edit_on_S": shortfall(run), "twins": twins_table(run), "sampled": sampled_table(run)}


def _pct(v: float | None) -> str:
    return "  n/a" if v is None else f"{v:5.2f}"


def show(rep: dict) -> None:
    print(f"analysis set S: {rep['analysis_set']} lists (4 to 8 events, exact for the unedited model)\n")
    print(f"{'arm':<10} {'S short':>8} {'S long':>7} {'S exact':>8} | {'all exact':>9} {'all short':>9} {'all long':>8} | {'p(stop)3':>8} | push L15  L19")
    for arm, r in rep["arms"].items():
        push = r["push_relative_to_edit"]
        print(f"{arm:<10} {r['S']['short']:>8} {r['S']['long']:>7} {r['S']['exact']:>8} | {r['all']['exact']:>9} {r['all']['short']:>9} "
              f"{r['all']['long']:>8} | {_pct(r['mean_p_stop_line3']):>8} | {_pct(push.get('L15'))} {_pct(push.get('L19'))}")
    print("\nby label (unedited exact / short / long of all its lists, then S and the edit's short and long in S, p(stop) at line 3 unedited and edited)")
    for label, r in rep["by_label"].items():
        p = r["mean_p_stop_line3"]
        print(f"  {label:<22} {r['unedited_exact']:>3} / {r['unedited_short']:>3} / {r['unedited_long']:>3} of {r['lists']:<3}  S {r['S']:>3}  "
              f"short {r['edit_short_in_S']:>3}  long {r['edit_long_in_S']:>3}   {_pct(p['dose:0'])} -> {_pct(p['dose:6'])}")
    print("\nby size (events: unedited exact / short / long, edit exact, and where the unedited model was exact the edit's short / long)")
    for n, r in rep["by_size"].items():
        print(f"  {n:>2}: {r['unedited_exact']:>3} / {r['unedited_short']:>3} / {r['unedited_long']:>3} of {r['lists']:<3}  edit exact {r['edit_exact']:>3}   "
              f"{r['edit_short_where_unedited_exact']:>3} / {r['edit_long_where_unedited_exact']:>3}")
    print("\nlines the published edit wrote on S, by number of true events")
    for n, c in rep["lines_written_by_the_edit_on_S"].items():
        print(f"  {n} events: " + ", ".join(f"{k} lines x{v}" for k, v in c.items()))
    print("\ntwins with IDs")
    for variant, r in rep["twins"].items():
        print(f"  {variant:<7} {r['logs']} logs  unedited {r['outcomes']['dose:0']}  edited {r['outcomes']['dose:6']}  "
              f"exact then not {r['exact_then_not']}, not then exact {r['not_then_exact']}")
    for kind, r in rep["sampled"].items():
        print(f"\nsampled, {kind} ({r['logs']} logs): exact {r['exact']}  short {r['short']}  long {r['long']}")
        print(f"  exactness differs between two unedited runs: {r['exactness_differs_between_two_unedited_runs']}, "
              f"unedited to edited: {r['exactness_differs_unedited_to_edited']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="The descriptive tables of prereg/002. No rules are applied here.")
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    rep = report(json.loads(args.run.read_text(encoding="utf-8")))
    if args.out:
        args.out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    show(rep)


if __name__ == "__main__":
    main()

# offtarget · offtarget/pagedata.py
# v0.1 · 13NOV2026 (lifted out of page/export_data.py v0.3, unchanged in what it computes)
#
# Practical: gathers every number the article prints or draws that comes from a file
# in results/ or explore/, and returns it as one dictionary. No model, no GPU, no
# download. page/export_data.py calls this and then adds the one small case it
# measures on the model. offtarget/verify.py calls it too, and compares what comes
# back with the committed page/data.json, so "the page's numbers are the result
# files' numbers" is something a stranger can check in a few seconds.
#   from offtarget.pagedata import collect; data = collect(Path("."))
#
# Philosophical: a picture on a page is a claim, and a claim needs a chain of
# custody like any other record. If someone asks where a bar's height came from,
# the answer should be a file and a field, never "I drew it about there". This
# module is that chain written as code. It used to live inside a script that also
# loaded the model, which meant nobody without a GPU could rerun it. A check that
# only its author can run is a signature, and a signature is not a check.
#
# The pilot lesson is kept here on purpose. The pilot said 50 and the full run said
# 44.4, and the page said 50 for a night because nothing forced the words to follow
# the data. Where a sentence on the page leans on a verdict ("behind", "inside the
# limit"), the verdict travels with the number, so the page can refuse to build if a
# rerun ever changes it.
from __future__ import annotations

import json
from pathlib import Path

from offtarget.default_verdict import Q1_LOWER, Q1_POINT

EXAMPLES = ("three", "five", "two", "none")
# The three provenance checks that compare a hash. The other two compare a count and a
# set of columns. A second reader caught "ten of ten hash checks" on the page: it was six.
HASH_CHECKS = ("base tensor is the one the edit was made on", "edit rebuilt from the logs matches the evaluated tensor",
               "published checkpoint holds the evaluated tensor")


def collect(root: Path) -> dict:
    """Everything the page shows that is already in a result file. Raises on any disagreement between files."""

    def read(rel: str) -> dict:
        return json.loads((root / rel).read_text(encoding="utf-8"))

    # No "status" field. Earlier files said "draft" here, and the word outlived the draft: the
    # page was released with its data still calling itself one. Whether a page is a draft is the
    # site's to say. This file only says where its numbers come from.
    data: dict = {"generated_by": "offtarget/pagedata.py and page/export_data.py"}

    # ---- the audit: numbers already in results/ -------------------------------------
    diff = read("results/diff.json")
    data["diff"] = {
        "tensors": diff["tensors"]["compared"], "identical": diff["tensors"]["identical"], "changed": diff["tensors"]["changed"],
        "values_that_differ": diff["params"]["values_that_differ"], "params_total": diff["params"]["total"],
        # Made from the values that differ, which is the count the page prints beside it. An
        # earlier version used the addressed entries, a few of which round to no change. The
        # two agree to three decimals. A number next to another number should be made from it.
        "pct_of_checkpoint": 100 * diff["params"]["values_that_differ"] / diff["params"]["total"],
        "direction_cosine": diff["direction_cosines"][0]["abs_cos"],
        "layers": [{"layer": c["layer"], "shape": c["shape"], "cols": c["cols"], "name": c["name"]} for c in diff["changed"]],
    }
    pub = read("results/published_samples.json")["models"]

    def totals(model: str) -> dict:
        """The authors' nine benchmarks pooled. published.py wrote the pool as "_all". We check it against the parts."""
        keys = ("n", "finished", "loop", "whitespace", "long")
        parts = {k: sum(b[k] for name, b in pub[model].items() if name != "_all") for k in keys}
        pooled_counts = {k: pub[model]["_all"][k] for k in keys}
        if parts != pooled_counts:
            raise RuntimeError(f"WIRING FAILURE: the pooled counts for {model} do not equal the sum of the benchmarks: {pooled_counts} vs {parts}")
        return pooled_counts

    data["published"] = {"unedited": totals("unedited"), "edited": totals("p50c"),
                         "benchmarks": [k for k in pub["unedited"] if k != "_all"]}
    data["paired"] = read("results/paired.json")

    prov = read("results/provenance.json")
    data["provenance"] = {"checks": len(prov["checks"]), "passed": sum(c["pass"] for c in prov["checks"]),
                          "hash_comparisons": sum(c["check"] in HASH_CHECKS for c in prov["checks"])}
    if prov["all_pass"] != (data["provenance"]["passed"] == data["provenance"]["checks"]):
        raise RuntimeError("WIRING FAILURE: provenance.json disagrees with itself about whether every check passed")

    side = read("results/sidecar.json")
    data["sidecar"] = {"same": side["same"], "different": side["different"]}

    pairs = read("results/published_pairs.json")
    if (pairs["a"], pairs["b"]) != ("unedited", "p50c") or pairs["problems"] != data["published"]["edited"]["n"]:
        raise RuntimeError("WIRING FAILURE: published_pairs.json is not the unedited model against the published edit")
    data["published"]["pairs"] = {"note": pairs["note"], "text_is_the_first_sample": pairs["text_is_the_first_sample"],
                                  "into_blank_space": {k: v for k, v in pairs["moves"].items() if k.endswith("-> whitespace")},
                                  "moves": pairs["moves"],
                                  "longest_blank_answer_chars": pairs["longest_blank_answer_chars"]}
    data["pilot"] = read("results/pilot_verdict.json")

    # ---- the exploration: numbers already in explore/ --------------------------------
    feas, ctl = read("explore/ghostbeat_feasibility.json"), read("explore/ghostbeat_controls.json")
    greedy = feas["behaviour"]["nothink/greedy"]
    data["first_look"] = {
        "greedy": {a: {cell: {k: greedy[a]["cells"][cell][k] for k in ("n", "exact", "dropped", "ghost")}
                       for cell in ("id", "bare", "id/replay", "id/second", "bare/replay", "bare/second")} for a in ("0.0", "6.0")},
        "wording_L19": {style: ctl["wording"][style]["L19"]["32-99"] for style in ctl["wording"]},
        "reference_L19": {
            "loop_tail": ctl["reference"]["thinking on"]["by_kind"]["loop"]["L19"]["last 256"],
            "ordinary": ctl["reference"]["thinking on"]["by_kind"]["long"]["L19"]["last 256"],
        },
    }

    # ---- registration 003: the default setting, all problems --------------------------
    dv, dr = read("results/default_mode_verdict.json"), read("results/default_mode_report.json")
    dfull = {k: v for k, v in read("results/default_mode_full.json").items() if k in ("cap", "sampling", "mode")}
    if dv["problems_complete"] != dv["problems_planned"]:
        raise RuntimeError("WIRING FAILURE: the default-mode run is incomplete, and the page says it ran every problem")
    four = dr["four_accuracies"]
    data["default_mode"] = {
        "prereg": dv["prereg"], "n": dv["problems_complete"], "four": four,
        # default setting (unedited, thinking off, ours) minus the authors' edited model with thinking on
        "gap": {k: dv["Q1"][k] for k in ("difference", "interval", "verdict")},
        "rule": {"point": Q1_POINT, "lower": Q1_LOWER},
        "edit_with_thinking_off": {k: dv["Q2"][k] for k in ("difference", "interval", "unedited_accuracy", "edited_accuracy",
                                                             "only_unedited_right", "only_edited_right", "verdict")},
        # how far each lever moved the unedited model's published 7.9%
        "moved": {"by_turning_thinking_off": round(four["unedited"]["thinking_off_ours"] - four["unedited"]["thinking_on_published"], 4),
                  "by_the_edit_with_thinking_on": round(four["edited"]["thinking_on_published"] - four["unedited"]["thinking_on_published"], 4)},
        "endings": {"unedited": dv["endings"]["0.0"], "edited": dv["endings"]["6.0"]},
        "pilots_hundred": dr["pilots_hundred"],
        # The two columns of the four accuracies were not measured the same way. The limits travel with them.
        "setup": {"ours": {"cap": dfull["cap"], "samples_per_problem": 1, "sampling": dfull["sampling"]},
                  "theirs": {"cap": read("results/published_samples.json")["cap"],
                             "samples_per_problem": data["paired"]["benchmarks"]["math500"]["samples_per_problem"]}},
    }

    # ---- registration 002: the duplicate alarm test -----------------------------------
    gv, gr = read("results/ghostbeat_verdict.json"), read("results/ghostbeat_report.json")
    graw = read("results/ghostbeat_registered.json")

    def arm002(name: str) -> dict:
        a = gr["arms"][name]
        return {**a["S"], "push": a["push_relative_to_edit"], "p_stop_line3": a["mean_p_stop_line3"]}

    def resent_reported_twice(dose: str) -> int:
        o = gr["twins"]["replay"]["outcomes"][dose]
        return o.get("ghost", 0) + o.get("both", 0)

    def resent_paired() -> dict:
        """The resent-packet error, log by log, before and after the edit.

        Tabulated on 12 NOV after the second reader's review. The report gives the totals
        (11 before, 8 after) and I had read them as "the edit does not cause this". Paired,
        the edit repaired some, introduced some and left some. The totals hid that.
        """
        def twice(o: str) -> bool:
            return o in ("ghost", "both")

        t = {"repaired": 0, "introduced": 0, "persistent": 0}
        for tw in graw["twins"]:
            if tw["variant"] != "replay":
                continue
            a, b = twice(tw["arms"]["dose:0"]["outcome"]), twice(tw["arms"]["dose:6"]["outcome"])
            t["repaired"] += a and not b
            t["introduced"] += b and not a
            t["persistent"] += a and b
        return t

    def ids_in_full() -> dict:
        """Handoffs with an ID on every line, all of them: exact before, exact after, and the moves between."""
        def ex(tw: dict, arm: str) -> bool:
            return tw["arms"][arm]["outcome"] == "exact"

        tws = graw["twins"]
        return {"all": len(tws), "exact_unedited": sum(ex(t, "dose:0") for t in tws), "exact_edited": sum(ex(t, "dose:6") for t in tws),
                "wrong_before": sum(not ex(t, "dose:0") for t in tws),
                "wrong_made_right": sum((not ex(t, "dose:0")) and ex(t, "dose:6") for t in tws)}

    matched_pushes = [v for a in gr["arms"] if a.startswith("matched:") for v in gr["arms"][a]["push_relative_to_edit"].values()]
    data["alarm"] = {
        "prereg": gv["prereg"], "lists": gv["lists"], "good": gv["analysis_set"],
        "unedited_all": gr["arms"]["dose:0"]["all"],
        "short": gv["Q1"],
        "by_dose": {a: arm002(a) for a in ("dose:0", "dose:1", "dose:2", "dose:4", "dose:6")},
        "dose_verdict": gv["Q2"]["verdict"],
        "matched": {a: arm002(a) for a in gr["arms"] if a.startswith("matched:")},
        "usual": {a: arm002(a) for a in gr["arms"] if a.startswith("random:")},
        "control": {"doing_at_least_half": gv["Q3"]["matched_directions_doing_at_least_half_as_much"], "of": gv["Q3"]["of"],
                    "verdict": gv["Q3"]["verdict"], "mean_push": gv["Q3"]["matched"]["push_relative_to_edit"]},
        "three_lines": {"k": gr["lines_written_by_the_edit_on_S"], "note": "lines the edited model wrote, by number of events, on the good lists"},
        "edited_all": gr["arms"]["dose:6"]["all"],
        "reversed_full": gr["arms"]["dose:-6"]["S"],
        "matched_push_range": [min(matched_pushes), max(matched_pushes)],
        "with_ids": {**gv["Q5"], **ids_in_full()},
        "twins": {"logs": gr["twins"]["replay"]["logs"],
                  "resent_reported_twice": {"unedited": resent_reported_twice("dose:0"), "edited": resent_reported_twice("dose:6"),
                                            **resent_paired()}},
    }
    resent = data["alarm"]["twins"]["resent_reported_twice"]
    if resent["persistent"] + resent["repaired"] != resent["unedited"] or resent["persistent"] + resent["introduced"] != resent["edited"]:
        raise RuntimeError("WIRING FAILURE: the paired count of resent-packet errors does not add up to the report's totals")
    ids = data["alarm"]["with_ids"]
    if ids["exact_unedited"] != ids["n"] or ids["wrong_made_right"] != ids["fixed_by_the_edit"]:
        raise RuntimeError("WIRING FAILURE: the ID handoffs counted from the raw run do not match the verdict of registration 002")
    if data["alarm"]["by_dose"]["dose:6"]["short"] != gv["Q1"]["k"] or len(data["alarm"]["matched"]) != gv["Q3"]["of"]:
        raise RuntimeError("WIRING FAILURE: the report and the verdict of registration 002 disagree about the edit or the control")

    # ---- registration 004: the instruction's example, and both directions -------------
    ev, er = read("results/example_verdict.json"), read("results/example_report.json")
    after = er["added_after_the_verdict_was_read"]

    def pooled(arm: str) -> dict:
        return {k: sum(er["arms_by_example"][x][arm]["all"][k] for x in EXAMPLES) for k in ("n", "exact", "short", "long")}

    data["example"] = {
        "prereg": ev["prereg"], "lists": ev["lists"], "logs": after["same_logs"]["logs"],
        "q1": ev["Q1"]["verdict"],
        "reversed": {k: ev["Q3"][k] for k in ("n", "difference", "interval", "unedited_exact", "reversed_exact", "made_exact", "broken", "verdict")},
        "short_by_example": {x: {k: ev["described"]["short_under_the_edit_by_example"][x][k] for k in ("S", "short", "share", "interval")}
                             for x in EXAMPLES},
        "exact_by_dose_three": {a: er["arms_by_example"]["three"][a]["all"]["exact"] for a in er["arms_by_example"]["three"] if a.startswith("dose:")},
        "unedited_all": pooled("dose:0"), "edited_all": pooled("dose:6"),
        "exact_all_by_example": {x: {"n": er["arms_by_example"][x]["dose:0"]["all"]["n"],
                                     "unedited": er["arms_by_example"][x]["dose:0"]["all"]["exact"],
                                     "edited": er["arms_by_example"][x]["dose:6"]["all"]["exact"]} for x in EXAMPLES},
        "exact_all_by_dose": {a: pooled(a)["exact"] for a in er["arms_by_example"]["three"] if a.startswith("dose:")},
        "short_lengths_under_two": ev["described"]["short_under_the_edit_by_example"]["two"]["lengths"],
        # Everything under this key was tabulated after the verdict was read. The page marks it so.
        "added_after_the_verdict_was_read": {
            "both_directions": after["both_directions"],
            "same_logs": {"exact_under_every_example": after["same_logs"]["exact_under_every_example"],
                          "short_at_the_published_dose": after["same_logs"]["short"]["dose:6"]},
        },
    }
    if pooled("dose:0")["n"] != ev["lists"]:
        raise RuntimeError("WIRING FAILURE: the four example sentences do not add up to the lists of registration 004")

    # ---- the loop-control look: exploration, and it travels with its own label --------
    lc = read("explore/loop_control_pilot.json")
    if not lc["status"].startswith("EXPLORATION"):
        raise RuntimeError("WIRING FAILURE: the loop-control file no longer says it is exploration")
    kinds = {a: {p["id"]: p["kind"] for p in arm["per_problem"]} for a, arm in lc["arms"].items()}
    data["loop_control"] = {
        "status": lc["status"], "n": lc["n"], "cap": lc["cap"],
        "arms": {a: {**{k: arm[k] for k in ("loop", "long", "finished", "whitespace")}, "push": arm.get("push_relative_to_edit"),
                     # problem by problem against the unedited model on the same seeds
                     "stopped": sum(1 for i, k in kinds["dose:0"].items() if k == "loop" and kinds[a][i] != "loop"),
                     "started": sum(1 for i, k in kinds["dose:0"].items() if k != "loop" and kinds[a][i] == "loop")}
                 for a, arm in lc["arms"].items()},
    }
    return data


# The three blocks page/export_data.py measures on the model. They do not depend on any
# result file, so a refresh keeps them exactly as they are.
MEASURED = ("wiring", "neurons", "demo")


def refresh(root: Path, existing: dict) -> dict:
    """The page's data rebuilt from the result files, keeping what was measured on the model.

    Practical: lets a result file change reach page/data.json without a GPU, and lets
    verify.py ask "does the committed file equal what the record says today".
    Philosophical: the measured blocks are kept, never recomputed here, and the function
    says so in its name. A refresh that quietly re-measured would be a second experiment.
    """
    data = collect(root)
    index = {layer["name"]: layer["index"] for layer in existing["diff"]["layers"]}
    for layer in data["diff"]["layers"]:
        if layer["name"] not in index:
            raise RuntimeError(f"WIRING FAILURE: the existing page data has no position for the changed tensor {layer['name']}")
        layer["index"] = index[layer["name"]]
    for key in MEASURED:
        if key not in existing:
            raise RuntimeError(f"WIRING FAILURE: the existing page data has no '{key}' block. Run page/export_data.py on the model first.")
        data[key] = existing[key]
    return data


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Rebuild page/data.json from the result files, keeping the blocks measured on the model.")
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--refresh", type=Path, required=True, help="the page data file to rebuild in place, for example page/data.json")
    args = ap.parse_args()
    existing = json.loads(args.refresh.read_text(encoding="utf-8"))
    data = refresh(args.root, existing)
    args.refresh.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    changed = sorted(k for k in data if data[k] != existing.get(k))
    print(f"wrote {args.refresh}. Blocks that changed: {', '.join(changed) if changed else 'none'}")


if __name__ == "__main__":
    main()

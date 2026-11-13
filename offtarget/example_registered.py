# offtarget · offtarget/example_registered.py
# v0.1 · 12NOV2026
#
# Practical: the registered run of prereg/004. Plain lists of six, seven and eight
# identical events on five new labels, each log asked four ways (the instruction's
# example says "two", "three", "five", or gives no number), under thirteen settings
# of the edit, with greedy decoding. It records the handoff the model wrote and
# how it ended. Nothing else.
#   python -I -m offtarget.example_registered --base <base> --edit-dir <logs>/runs/p50c/edit \
#       --out results/example_registered.json --raw results/raw/example_registered
#   add --dry-run to exercise the pipeline on the label already explored
#
# It refuses to touch the held-out labels until the registration says FROZEN.
#
# Philosophical: the last run found a number, three, and the instruction turned
# out to have the same number written in it. A coincidence like that is either the
# finding or the artefact, and there is exactly one way to tell: change the number
# in the instruction and see whether the model's number moves with it.
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from offtarget import ghostbeat as gb
from offtarget.ghostbeat_probe import chat, pack
from offtarget.ghostbeat_registered import write_handoffs
from offtarget.run import load, set_arm
from offtarget.stamp import run_stamp

SCHEMA = "offtarget.example_registered/0.1"
PREREG = "prereg/004-the-example-and-both-directions.md"
HELD_OUT = ("AF onset", "pause detected", "ST elevation", "asystole alarm", "artifact, motion")
EXAMPLES = ("three", "two", "five", "none")
SIZES, SEEDS, CAP = (6, 7, 8), 8, 120
ARMS = ("dose:0", "dose:1", "dose:2", "dose:3", "dose:4", "dose:6", "dose:-1", "dose:-2", "dose:-3", "dose:-4",
        "matched:2", "matched:4", "matched:5")
CALIBRATION = "prereg/002-push-calibration.json"      # the scales registration 002 used for its matched arms


def frozen(root: Path) -> bool:
    text = (root / PREREG).read_text(encoding="utf-8")
    return any(line.startswith("**Status: FROZEN") for line in text.splitlines())


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.example_registered")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="The registered run of prereg/004.")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--edit-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--raw", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="the explored label, one log per cell, never the held-out labels")
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--gpu-fraction", type=float, default=0.5)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    root = Path(__file__).resolve().parent.parent

    if args.dry_run:
        labels, seeds = (gb.LABEL,), 1
        if args.out.name == "example_registered.json":
            raise SystemExit("WIRING FAILURE: a dry run must not write to the registered result's name")
    else:
        labels, seeds = HELD_OUT, SEEDS
        if not frozen(root):
            raise SystemExit(f"WIRING FAILURE: {PREREG} is not FROZEN. The held-out labels stay sealed until it is. Use --dry-run.")
    cal_file = root / CALIBRATION
    if not cal_file.exists():
        raise SystemExit(f"WIRING FAILURE: {CALIBRATION} is missing.")
    calibration = json.loads(cal_file.read_text(encoding="utf-8"))["scales"]

    model, tok, edits, wiring, device = load(args.base, args.edit_dir, args.gpu_fraction)
    lists = [gb.make_case(n, "list", "bare", s, lab, ex) for ex in EXAMPLES for lab in labels for n in SIZES for s in range(seeds)]
    prompts = [chat(tok, c.prompt, False) for c in lists]
    chunks = pack([len(tok(p, add_special_tokens=False).input_ids) for p in prompts], args.batch, 4000)
    # The stamp is what this file says about its own birth: start time, the hash of the registration
    # it ran under, and the commit of this code. Runs made before 13 NOV 2026 do not have one.
    report = {"schema": SCHEMA, "prereg": PREREG, "stamp": run_stamp(root, PREREG),
              "status": "dry run on the explored label" if args.dry_run else "registered run",
              "labels": list(labels), "examples": list(EXAMPLES), "arms": list(ARMS), "wiring": wiring, "decoding": "greedy",
              "calibration": {a: calibration[a.replace("matched", "random")] for a in ARMS if a.startswith("matched")},
              "lists": [{"case": c.case_id, "label": c.label, "example": c.example, "n": len(c.truth), "arms": {}} for c in lists]}

    def save() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")

    for arm in ARMS:
        set_arm(model, edits, arm, calibration)
        t0 = time.time()
        rows = write_handoffs(model, tok, prompts, chunks, lists, CAP, None, 0, device)
        if args.raw:
            args.raw.mkdir(parents=True, exist_ok=True)
            with open(args.raw / f"lists_{arm.replace(':', '_')}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for c, r in zip(lists, rows):
                    fh.write(json.dumps({"case": c.case_id, "outcome": r["outcome"], "text": r["text"]}) + "\n")
        for rec, row in zip(report["lists"], rows):
            rec["arms"][arm] = {k: row[k] for k in ("entries", "outcome", "ended", "finished", "tokens")}
        exact = sum(r["outcome"] == "exact" for r in rows)
        fewer = sum(r["entries"] < len(c.truth) for c, r in zip(lists, rows))
        print(f"{arm:<10} exact {exact}/{len(lists)}  short {fewer}  ({time.time() - t0:.0f}s)", flush=True)
        save()
    set_arm(model, edits, "dose:0")
    print("done", flush=True)


if __name__ == "__main__":
    main()

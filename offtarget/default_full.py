# offtarget · offtarget/default_full.py
# v0.1 · 11NOV2026
#
# Practical: the registered run of prereg/003. All 500 MATH-500 problems with
# thinking off (the model's documented default), once under the unedited weights
# and once under the published edit, same problems, same sampling seeds. It works
# through the problems in blocks of 100, both arms per block, and saves after
# every block, so a run that is stopped at dawn or dies in the night leaves pairs
# and can be picked up where it stopped.
#   python -I -m offtarget.default_full --base <base> --edit-dir <logs>/runs/p50c/edit \
#       --problems <math500>/test.jsonl --out results/default_mode_full.json \
#       --raw results/raw/default_mode_full --stop-after 06:00
#   add --dry-run for eight problems at a short cap, to prove the plumbing
#
# It refuses to run for real until the registration says FROZEN.
#
# Philosophical: the pilot was a hundred problems and one roll each, and it said
# something a headline would love. This is the unglamorous return visit. Same
# door, same question, five times the houses, and a second question the pilot
# never asked: the edit was tested with thinking switched on, so what does it do
# to the setting people actually get?
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

from offtarget.diff import describe_snapshot, sha256_tensor
from offtarget.grade import grade
from offtarget.published import classify
from offtarget.run import SAMPLING, build_prompt, find_param, generate, load, pick_problems, set_dose
from offtarget.stamp import run_stamp

SCHEMA = "offtarget.default_full/0.1"
PREREG = "prereg/003-default-mode-full.md"
N, BLOCK, CAP, BATCH = 500, 100, 8192, 20
ORDER_SEED = 0          # the pilot's problem order, so block 0 is the pilot's hundred problems
SEED = 1000             # the pilot sampled with seeds 0 to 80. These are fresh draws
MODE = "nothink"


def frozen(root: Path) -> bool:
    text = (root / PREREG).read_text(encoding="utf-8")
    return any(line.startswith("**Status: FROZEN") for line in text.splitlines())


def deadline(stop_after: str | None, now: dt.datetime) -> dt.datetime | None:
    """The next time the clock reads HH:MM. A run started in the evening stops the following morning."""
    if not stop_after:
        return None
    hour, minute = (int(x) for x in stop_after.split(":"))
    at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return at if at > now else at + dt.timedelta(days=1)


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.default_full")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="The registered run of prereg/003.")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--edit-dir", required=True, type=Path)
    ap.add_argument("--problems", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--raw", type=Path)
    ap.add_argument("--stop-after", help="HH:MM local time. No new block starts after it")
    ap.add_argument("--gpu-fraction", type=float, default=0.65)
    ap.add_argument("--dry-run", action="store_true", help="eight problems, cap 256, never the registered output name")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    root = Path(__file__).resolve().parent.parent

    n, block, cap, batch = (8, 4, 256, 4) if args.dry_run else (N, BLOCK, CAP, BATCH)
    if args.dry_run and args.out.name == "default_mode_full.json":
        raise SystemExit("WIRING FAILURE: a dry run must not write to the registered result's name")
    if not args.dry_run and not frozen(root):
        raise SystemExit(f"WIRING FAILURE: {PREREG} is not FROZEN. Freeze it and commit before the run. Use --dry-run to test.")
    stop_at = deadline(args.stop_after, dt.datetime.now())

    model, tok, edits, wiring, device = load(args.base, args.edit_dir, args.gpu_fraction)
    problems = pick_problems(args.problems, n, ORDER_SEED)
    prompts = [build_prompt(tok, p["problem"], False) for p in problems]
    if any(abs(e.published_alpha - 6.0) > 1e-3 for e in edits):
        raise SystemExit(f"WIRING FAILURE: the published dose is not 6: {[e.published_alpha for e in edits]}")
    arms = (("0.0", 0.0), ("6.0", edits[0].published_alpha))      # names are fixed strings. The verdict module looks them up
    config ={"schema": SCHEMA, "prereg": PREREG, "status": "dry run" if args.dry_run else "registered run",
              "base": describe_snapshot(args.base), "mode": MODE, "cap": cap, "sampling": SAMPLING[MODE], "seed": SEED,
              "batch": batch, "block": block, "problem_ids": [p["unique_id"] for p in problems]}
    # The stamp sits outside `config` on purpose. `config` is compared when a stopped run is picked
    # up again, and a start time would never match. The first start's stamp is the one that is kept.
    report = dict(config, stamp=run_stamp(root, PREREG), wiring=wiring, blocks={})
    if args.out.exists():                              # pick up a run that was stopped. Only if it is the same run
        old = json.loads(args.out.read_text(encoding="utf-8"))
        if any(old.get(k) != v for k, v in config.items()):
            raise SystemExit(f"WIRING FAILURE: {args.out} holds a different run. Move it away before starting this one.")
        report["blocks"] = old["blocks"]
        report["stamp"] = old.get("stamp", report["stamp"])
        print(f"resuming: {len(old['blocks'])} blocks already done", flush=True)

    def save() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")

    stopped = False
    for b in range(n // block):
        for name, alpha in arms:
            key = f"{name}/block{b}"
            if key in report["blocks"]:
                continue
            if stop_at and dt.datetime.now() > stop_at:
                stopped = True
                break
            set_dose(model, edits, alpha)
            if alpha:                                  # the edited arm must be the tensors the authors evaluated, bit for bit
                for e in edits:
                    if sha256_tensor(find_param(model, e.name).data.cpu()) != sha256_tensor(e.published):
                        raise RuntimeError(f"WIRING FAILURE: {e.name} is not the published tensor under the edited arm")
            lo, hi = b * block, (b + 1) * block
            t0 = time.time()
            gens = generate(model, tok, prompts[lo:hi], cap, SAMPLING[MODE], SEED + lo, batch, device)
            secs = time.time() - t0
            rows = []
            for p, g in zip(problems[lo:hi], gens):
                r = classify(g["text"], g["ids"], cap=cap, thinking=False, finished=g["finished"])
                r.update(grade(g["text"], p["answer"]))
                rows.append({"id": p["unique_id"], "kind": r["kind"], "tokens": r["tokens"], "correct": r["correct"],
                             "boxed": r["boxed"], "onset": r["onset"]})
            report["blocks"][key] = {"seconds": round(secs, 1), "rows": rows}
            if args.raw:
                args.raw.mkdir(parents=True, exist_ok=True)
                with open(args.raw / f"alpha_{name}_block{b}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                    for p, g, r in zip(problems[lo:hi], gens, rows):
                        fh.write(json.dumps({"id": p["unique_id"], "kind": r["kind"], "correct": r["correct"],
                                             "finished": g["finished"], "text": g["text"]}) + "\n")
            right = sum(r["correct"] for r in rows)
            ends = {k: sum(r["kind"] == k for r in rows) for k in ("finished", "loop", "whitespace", "long")}
            print(f"alpha {name} block {b}: correct {right}/{len(rows)}  {ends}  {secs:.0f}s", flush=True)
            save()
        if stopped:
            break
    set_dose(model, edits, 0)
    report["stopped_by_the_clock"] = stopped
    save()
    print("stopped by the clock" if stopped else "done", flush=True)


if __name__ == "__main__":
    main()

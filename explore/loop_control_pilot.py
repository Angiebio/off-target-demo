# offtarget · explore/loop_control_pilot.py
# v0.2 · 11NOV2026 (v0.2 matches the push two ways: on ordinary reasoning text and on loop text)
#
# Practical: an exploration, not a registered run. Nothing it prints is evidence.
# It asks the question the dry runs of prereg/002 left open: is the fix for looping
# special to the published direction, or does any push of the same size on the
# same 64 neurons cut the looping too? Thinking on, the authors' sampling, a short
# limit (4,096 tokens, where the edit's benefit shows as fewer loops and not yet as
# right answers). Arms: the unedited model, the published edit, one random
# direction at the usual same-distance strength, and two random directions each
# scaled two ways. "matched" pushes as hard as the edit on the unedited model's
# ordinary reasoning text. "loopmatched" pushes as hard as the edit on the tail of
# the unedited model's own loops, where the edit pushes hardest. The edit's push is
# selective and a random direction's is not, so no single scale is fair in both
# places. Two scales bracket the answer.
#   python -I explore/loop_control_pilot.py --base <base> --edit-dir <logs>/runs/p50c/edit \
#       --problems <math500>/test.jsonl --calib results/raw/pilot_dose/alpha_0.0.jsonl \
#       --out explore/loop_control_pilot.json --raw explore/raw/loop_control_pilot --stop-after 06:30
#
# Philosophical: the editor model ran a sham and it did nothing, so the direction
# looked special. But the sham was given a fifth of the dose. This is the first
# look at what a sham does when it is given the same dose, on the failure the edit
# was made for. It is a scouting trip. Its job is to tell me how big the registered
# version has to be, and which way I should be afraid of being wrong.
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import torch

from offtarget.default_full import deadline
from offtarget.dose import arm_tensors, layer_of
from offtarget.ghostbeat_probe import PushMeter
from offtarget.grade import grade
from offtarget.published import classify, summarise
from offtarget.run import SAMPLING, build_prompt, generate, load, pick_problems, set_arm

SCHEMA = "offtarget.explore.loop_control_pilot/0.1"
ARMS = ("dose:0", "dose:6", "matched:0", "loopmatched:0", "matched:1", "loopmatched:1", "random:0")   # an early stop keeps the contrast
N_RANDOM = 2
CALIB_ANSWERS, CALIB_TOKENS, LOOP_TAIL = 16, 2048, 1024
SEED = 2000            # pilot A sampled these problems with seed 0. These are fresh draws, the same for every arm


@torch.inference_mode()
def calibrate(model, tok, edits, device: str, raw_file: Path, problems: dict[str, dict]):
    """Scales that make each random direction push as hard as the edit, on two kinds of the unedited model's own text."""
    meter = PushMeter(model, edits, device)
    rows = [json.loads(line) for line in raw_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    loops = [r for r in rows if r["kind"] == "loop"]
    if len(loops) < 4:
        raise RuntimeError(f"WIRING FAILURE: only {len(loops)} looped answers to calibrate on")

    def grab(r: dict, lo: int | None, hi: int | None) -> list[torch.Tensor]:
        prompt = tok(build_prompt(tok, problems[r["id"]]["problem"], True), add_special_tokens=False).input_ids
        ids = r["ids"] if hi is None else r["ids"][:hi]
        model.model(input_ids=torch.tensor([prompt + ids], device=device))
        start = len(prompt) + (lo if lo is not None else 0)
        return [meter.inputs[i][0][start:, it["cols"]].float().cpu() for i, it in enumerate(meter.items)]

    text = [grab(r, None, CALIB_TOKENS) for r in rows[:CALIB_ANSWERS]]            # the first stretch of each answer
    wiring = meter.wiring()
    tails = [grab(r, len(r["ids"]) - LOOP_TAIL, None) for r in loops]             # the end of each answer that looped
    meter.close()

    def push(tensors: list[torch.Tensor], acts: list) -> dict:
        res = {}
        for i, (e, t) in enumerate(zip(edits, tensors)):
            delta = (t.float() - e.base.float())[:, e.cols]
            res[f"L{layer_of(e)}"] = sum(float((a[i] @ delta.T).norm(dim=-1).sum()) for a in acts) / sum(a[i].shape[0] for a in acts)
        return res

    out = {"push_wiring": wiring}
    scales = {}
    for name, acts in (("text", text), ("loop", tails)):
        edit = push(arm_tensors(edits, "dose:6"), acts)
        usual = {f"random:{k}": push(arm_tensors(edits, f"random:{k}"), acts) for k in range(N_RANDOM)}
        scales[name] = {a: {layer: edit[layer] / v[layer] for layer in edit} for a, v in usual.items()}
        out[name] = {"answers": len(acts), "tokens": sum(a[0].shape[0] for a in acts), "push_of_the_edit": edit,
                     "usual_random_relative_to_edit": {a: {layer: v[layer] / edit[layer] for layer in edit} for a, v in usual.items()},
                     "scales": scales[name]}
    out["measured_on"] = (f"text: the first {CALIB_TOKENS} tokens of {len(text)} unedited thinking-mode answers from pilot A. "
                          f"loop: the last {LOOP_TAIL} tokens of the {len(tails)} of those 32 answers that looped.")
    return out, scales, push, {"text": text, "loop": tails}


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("explore/loop_control_pilot.py")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="Exploration: a random control of matched push, on the looping itself.")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--edit-dir", required=True, type=Path)
    ap.add_argument("--problems", required=True, type=Path)
    ap.add_argument("--calib", required=True, type=Path, help="pilot A's unedited answers (alpha_0.0.jsonl)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--raw", type=Path)
    ap.add_argument("--n", type=int, default=96)
    ap.add_argument("--cap", type=int, default=4096)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--arms", nargs="+", default=list(ARMS))
    ap.add_argument("--stop-after", help="HH:MM local time. No new arm starts after it")
    ap.add_argument("--gpu-fraction", type=float, default=0.5)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    stop_at = deadline(args.stop_after, dt.datetime.now())

    model, tok, edits, wiring, device = load(args.base, args.edit_dir, args.gpu_fraction)
    every = {p["unique_id"]: p for p in pick_problems(args.problems, 500, 0)}
    problems = pick_problems(args.problems, args.n, 0)                # the pilot's order. The first 32 are pilot A's problems
    prompts = [build_prompt(tok, p["problem"], True) for p in problems]
    info, scales, push, acts = calibrate(model, tok, edits, device, args.calib, every)
    for where in ("text", "loop"):
        print(f"the edit's push on {where}:", {k: round(x, 3) for k, x in info[where]["push_of_the_edit"].items()}, flush=True)
        for a, v in info[where]["usual_random_relative_to_edit"].items():
            print(f"  {a} at the usual strength delivers", {k: round(x, 2) for k, x in v.items()}, f"of it. Scale to match: "
                  f"{ {k: round(x, 2) for k, x in scales[where][a].items()} }", flush=True)

    report = {"schema": SCHEMA, "status": "EXPLORATION. Not registered, not evidence.", "mode": "think", "cap": args.cap,
              "sampling": SAMPLING["think"], "seed": SEED, "batch": args.batch, "n": args.n,
              "problem_ids": [p["unique_id"] for p in problems], "wiring": wiring, "calibration": info, "arms": {}}

    def save() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")

    for arm in args.arms:
        if stop_at and dt.datetime.now() > stop_at:
            report["stopped_by_the_clock"] = True
            print("stopped by the clock before", arm, flush=True)
            break
        kind, _, k = arm.partition(":")
        real, cal = (f"matched:{k}", scales["loop"]) if kind == "loopmatched" else (arm, scales["text"])
        set_arm(model, edits, real, cal)
        tensors = arm_tensors(edits, real, cal)
        delivered = {where: {layer: v / info[where]["push_of_the_edit"][layer] for layer, v in push(tensors, acts[where]).items()}
                     for where in ("text", "loop")}
        t0 = time.time()
        gens = generate(model, tok, prompts, args.cap, SAMPLING["think"], SEED, args.batch, device)
        secs = time.time() - t0
        rows = []
        for p, g in zip(problems, gens):
            r = classify(g["text"], g["ids"], cap=args.cap, thinking=True, finished=g["finished"])
            r.update(grade(g["text"], p["answer"]))
            rows.append(r)
        s = summarise(rows)
        s.update({"accuracy": sum(r["correct"] for r in rows) / len(rows),
                  "mean_tail_repeat_frac": sum(r["tail_repeat_frac"] for r in rows) / len(rows),
                  "mean_tokens": sum(r["tokens"] for r in rows) / len(rows), "seconds": round(secs, 1),
                  "push_relative_to_edit": delivered,
                  "per_problem": [{"id": p["unique_id"], "kind": r["kind"], "tokens": r["tokens"], "correct": r["correct"],
                                   "tail_repeat_frac": round(r["tail_repeat_frac"], 4), "onset": r["onset"],
                                   "think_closed": r["think_closed"]} for p, r in zip(problems, rows)]})
        report["arms"][arm] = s
        if args.raw:
            args.raw.mkdir(parents=True, exist_ok=True)
            with open(args.raw / (arm.replace(":", "_") + ".jsonl"), "w", encoding="utf-8", newline="\n") as fh:
                for p, g, r in zip(problems, gens, rows):
                    fh.write(json.dumps({"id": p["unique_id"], "kind": r["kind"], "correct": r["correct"],
                                         "finished": g["finished"], "text": g["text"]}) + "\n")
        print(f"{arm:<10} loop {s['loop_share']:.1%}  blank {s['whitespace_share']:.1%}  long {s['long_share']:.1%}  "
              f"finished {s['finished'] / s['n']:.1%}  tail repeat {s['mean_tail_repeat_frac']:.2f}  correct {s['accuracy']:.1%}  "
              f"push on text {[round(x, 2) for x in delivered['text'].values()]} on loops {[round(x, 2) for x in delivered['loop'].values()]}  "
              f"{secs:.0f}s", flush=True)
        save()
    set_arm(model, edits, "dose:0")
    save()
    print("done", flush=True)


if __name__ == "__main__":
    main()

# offtarget · offtarget/ghostbeat_controls.py
# v0.1 · 11NOV2026 · EXPLORATION. Not a registered run. Nothing here is evidence.
#
# Practical: the controls Ying asked for after the first look, plus two the first
# look made necessary.
#   1. wording   the same events handed off three ways (every line worded the same,
#                every line worded differently, identical lines with no IDs), with
#                the edit's push and the layer's whole write reported SEPARATELY,
#                line by line, so a ratio cannot hide which of the two moved
#   2. reference the same two numbers on ordinary answers and on real loops, in
#                both modes, by position in the answer
#   3. decoding  the vendor's sampling profile run a second time on the unedited
#                model (how much do two runs of the SAME model differ), and run
#                with its presence penalty switched off (is it the penalty or the
#                dice that drops events)
#   python -I -m offtarget.ghostbeat_controls --base <base> --edit-dir <logs>/runs/p50c/edit \
#       --out explore/ghostbeat_controls.json
#
# Philosophical: Ying's note was the right kind of unkind. A ratio is two numbers
# wearing one coat, and "the direction fires on repetition" could have been the
# denominator shrinking, or late tokens, or the same four words over and over. Each
# of those is a different claim, so each gets its own measurement. And a sampled
# run compared with another sampled run needs the model compared with itself
# first, which is the control finding 10 says the published data lacks. (An earlier
# version of this line said the audit had asked the authors for it. Nobody was asked.)
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import torch

from offtarget import ghostbeat as gb
from offtarget.ghostbeat_probe import PushMeter, behaviour, chat
from offtarget.loops import repeat_mask
from offtarget.run import build_prompt, load

SCHEMA = "offtarget.ghostbeat_controls/0.1"
DESCS = ["PVC, isolated", "one isolated PVC", "single premature ventricular contraction",
         "isolated ventricular ectopic beat", "a lone PVC, no run", "premature ventricular beat, single",
         "solitary PVC", "one ventricular premature beat, isolated", "isolated PVC seen",
         "single ectopic beat (PVC)", "PVC x1, not sustained", "one-off premature ventricular complex"]
SEPS = [" ", ": ", " - ", ", "]
TAILS = ["", " noted", " recorded", " on monitor", " captured", " logged"]
LINE_BUCKETS = ((0, 0), (1, 3), (4, 7), (8, 15), (16, 31), (32, 99))
TOKEN_BUCKETS = ((0, 127), (128, 511), (512, 1023), (1024, 2047), (2048, 9999))
MAX_ANSWER = 4096


def varied_lines(case: gb.Case, seed: int) -> list[str]:
    """The same events in the same order, no two neighbouring lines worded alike."""
    rng = random.Random(f"varied:{case.case_id}:{seed}")
    lines, last = [], None
    for acq in case.truth:
        desc = rng.choice([d for d in DESCS if d != last])
        last = desc
        lines.append(f"{acq}{rng.choice(SEPS)}{desc}{rng.choice(TAILS)}")
    return lines


def handoffs(case: gb.Case) -> dict[str, list[str]]:
    return {"same wording, IDs": [f"{a} {gb.LABEL}" for a in case.truth],
            "varied wording, IDs": varied_lines(case, 0),
            "identical lines, no IDs": [gb.LABEL for _ in case.truth]}


def bucket(k: int, buckets) -> str:
    for lo, hi in buckets:
        if lo <= k <= hi:
            return f"{lo}" if lo == hi else f"{lo}-{hi}"
    raise ValueError(f"WIRING FAILURE: {k} is in no bucket")


def series(meter: PushMeter) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    """Per token and per layer: the size of the edit's push, and the size of everything the layer writes."""
    out = {}
    for i, it in enumerate(meter.items):
        a = meter.inputs[i][0].float()
        push = (it["alpha"] * (a[:, it["cols"]] @ it["c"])).abs() * it["u"].norm()
        out[it["layer"]] = (push.cpu(), (a @ it["w0"].T).norm(dim=-1).cpu())
    return out


@torch.inference_mode()
def wording(model, tok, meter: PushMeter, cases: list[gb.Case], device: str) -> dict:
    acc = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0])))   # style > layer > bucket > [push, write, tokens]
    for c in cases:
        prompt = chat(tok, c.prompt, False)
        for style, lines in handoffs(c).items():
            full = tok(prompt + "\n".join(lines + ["END"]), add_special_tokens=False).input_ids
            edges = []
            for k in range(len(lines) + 1):
                prefix = tok(prompt + "".join(line + "\n" for line in lines[:k]), add_special_tokens=False).input_ids
                if full[:len(prefix)] != prefix:
                    raise RuntimeError(f"WIRING FAILURE: line {k} of {c.case_id} ({style}) does not start on a token boundary")
                edges.append(len(prefix))
            model.model(input_ids=torch.tensor([full], device=device))      # no vocabulary head: the hooks sit below it
            for layer, (push, write) in series(meter).items():
                for k in range(len(lines)):
                    cell = acc[style][layer][bucket(k, LINE_BUCKETS)]
                    cell[0] += float(push[edges[k]:edges[k + 1]].sum())
                    cell[1] += float(write[edges[k]:edges[k + 1]].sum())
                    cell[2] += edges[k + 1] - edges[k]
    return {style: {layer: {b: {"tokens": v[2], "mean_push": v[0] / v[2], "mean_write": v[1] / v[2],
                                "ratio_of_means": v[0] / v[1]} for b, v in cells.items()}
                    for layer, cells in layers.items()} for style, layers in acc.items()}


@torch.inference_mode()
def reference(model, tok, meter: PushMeter, raw_file: Path, problems_file: Path, thinking: bool, k: int, device: str) -> dict:
    """Push and write, separately, on our own pilot answers: by kind and by position in the answer."""
    problems = {}
    for line in problems_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            p = json.loads(line)
            problems[p["unique_id"]] = p["problem"]
    rows = [json.loads(line) for line in raw_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    acc = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0])))
    counts = {}
    looping_tails: list[bool] = []
    for kind in ("finished", "long", "loop"):
        picked = [r for r in rows if r["kind"] == kind and len(r["ids"]) >= 64][:k]
        counts[kind] = len(picked)
        for r in picked:
            prompt_ids = tok(build_prompt(tok, problems[r["id"]], thinking), add_special_tokens=False).input_ids
            # An 8,192-token answer in one pass does not fit under our memory ceiling
            # (attention grows with the square of the length), so we read the first
            # MAX_ANSWER tokens and say, for loops, whether that cut still ends inside the loop.
            ids = r["ids"][:MAX_ANSWER]
            if kind == "loop":
                tail = repeat_mask(ids, n=8)[-256:]
                looping_tails.append(sum(tail) / len(tail) >= 0.5)
            model.model(input_ids=torch.tensor([prompt_ids + ids], device=device))
            lo, n = len(prompt_ids), len(ids)
            for layer, (push, write) in series(meter).items():
                spans = {bucket(a, TOKEN_BUCKETS): (lo + a, lo + min(b + 1, n)) for a, b in TOKEN_BUCKETS if a < n}
                spans["last 256"] = (lo + n - 256, lo + n) if n >= 256 else (lo, lo + n)
                for name, (s, e) in spans.items():
                    cell = acc[kind][layer][name]
                    cell[0] += float(push[s:e].sum())
                    cell[1] += float(write[s:e].sum())
                    cell[2] += e - s
    return {"answers": counts, "max_answer_tokens": MAX_ANSWER,
            "loops_still_looping_at_the_cut": f"{sum(looping_tails)} of {len(looping_tails)}",
            "by_kind": {kind: {layer: {b: {"tokens": v[2], "mean_push": v[0] / v[2], "mean_write": v[1] / v[2],
                                           "ratio_of_means": v[0] / v[1]} for b, v in cells.items()}
                               for layer, cells in layers.items()} for kind, layers in acc.items()}}


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.ghostbeat_controls")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="Exploration: controls for the Ghost Beat feasibility look.")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--edit-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--raw", type=Path)
    ap.add_argument("--problems", type=Path)
    ap.add_argument("--pilot-think", type=Path)
    ap.add_argument("--pilot-nothink", type=Path)
    ap.add_argument("--wording-ns", type=int, nargs="+", default=[32, 64])
    ap.add_argument("--ns", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32])
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--cap", type=int, default=500)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--gpu-fraction", type=float, default=0.5)
    ap.add_argument("--skip-decoding", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    model, tok, edits, wiring, device = load(args.base, args.edit_dir, args.gpu_fraction)
    report = {"schema": SCHEMA, "status": "exploration, not registered, not evidence", "wiring": wiring}

    def save() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")

    meter = PushMeter(model, edits, device)
    t0 = time.time()
    cases = [gb.make_case(n, "second", "id", s) for n in args.wording_ns for s in range(args.seeds)]
    report["wording"] = wording(model, tok, meter, cases, device)
    report["wording_cases"] = [c.case_id for c in cases]
    report["push_wiring"] = meter.wiring()
    print(f"wording control: {len(cases)} logs, three handoffs each, {time.time() - t0:.0f}s", flush=True)
    save()
    report["reference"] = {}
    for name, path, thinking in (("thinking on", args.pilot_think, True), ("thinking off", args.pilot_nothink, False)):
        if path and args.problems:
            t0 = time.time()
            report["reference"][name] = reference(model, tok, meter, path, args.problems, thinking, 8, device)
            print(f"reference, {name}: {report['reference'][name]['answers']}, {time.time() - t0:.0f}s", flush=True)
            save()
    meter.close()

    if not args.skip_decoding:
        cases = gb.make_cases(args.ns, list(range(args.seeds)))
        report["decoding"] = {}
        for label, decoding, seed, alphas in (("card profile, second run (seed 1)", "card", 1, [0.0]),
                                              ("card profile without the presence penalty", "card_nopenalty", 0, [0.0, 6.0])):
            report["decoding"][label] = behaviour(model, tok, edits, cases, alphas, "nothink", decoding, args.cap,
                                                  args.batch, seed, device,
                                                  args.raw / f"seed{seed}" if args.raw else None)
            save()
    print("done", flush=True)


if __name__ == "__main__":
    main()

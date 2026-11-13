# offtarget · offtarget/ghostbeat_registered.py
# v0.2 · 11NOV2026 (header corrected at the freeze: twenty arms. No change to what runs)
#
# Practical: the registered run of prereg/002. Identical-line lists under twenty
# arms and twins with IDs under two, on five labels the model has never seen from
# us, with greedy decoding so every difference between arms is the weights. For
# each list and arm it records the handoff the model wrote and, with the correct
# handoff fed in, the probability of stopping at the end of every line.
#   python -I -m offtarget.ghostbeat_registered --base <base> --edit-dir <logs>/runs/p50c/edit \
#       --out results/ghostbeat_registered.json --raw results/raw/ghostbeat_registered
#   add --dry-run to exercise the whole pipeline on the label already explored
#
# It refuses to touch the held-out labels until the registration says FROZEN.
#
# Philosophical: a held-out set is a sealed envelope, and the only honest way to
# keep an envelope sealed is to make opening it a deliberate act. So the seal is in
# the code. If I ever want to peek early I will have to edit this file to do it,
# and the diff will say what I did.
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch

from offtarget import ghostbeat as gb
from offtarget.dose import arm_tensors, layer_of
from offtarget.ghostbeat_probe import PushMeter, chat, pack
from offtarget.run import SAMPLING, STOP_TOKENS, generate, load, set_arm
from offtarget.stamp import run_stamp

SCHEMA = "offtarget.ghostbeat_registered/0.1"
PREREG = "prereg/002-identical-lines-and-twins.md"
HELD_OUT = ("VT run, 5 beats", "bradycardia, 44 bpm", "SpO2 low, 87%", "couplet, ventricular", "lead off, V2")
LIST_SIZES, LIST_SEEDS, LIST_CAP = tuple(range(2, 9)), 8, 120
TWIN_SIZES, TWIN_SEEDS, TWIN_CAP = (2, 4, 8, 16), 4, 280
ARMS = ("dose:0", "dose:1", "dose:2", "dose:4", "dose:6", "dose:-2", "dose:-6", "only:15", "only:19",
        "random:0", "random:1", "random:2") + tuple(f"matched:{k}" for k in range(8))
CALIBRATION = "prereg/002-push-calibration.json"
TWIN_ARMS = ("dose:0", "dose:6")
SAMPLED = (("dose:0", 0), ("dose:0", 1), ("dose:6", 0))


def frozen(root: Path) -> bool:
    text = (root / PREREG).read_text(encoding="utf-8")
    return any(line.startswith("**Status: FROZEN") for line in text.splitlines())


def stop_plan(tok, prompt: str, case: gb.Case) -> tuple[list[int], list[int], int]:
    """Token ids of prompt plus the correct entries, and the position that ends each line."""
    lines = case.expected.split("\n")[:-1]
    full = tok(prompt + "\n".join(lines), add_special_tokens=False).input_ids
    ends = []
    for k in range(1, len(lines) + 1):
        upto = tok(prompt + "\n".join(lines[:k]), add_special_tokens=False).input_ids
        if full[:len(upto)] != upto:
            raise RuntimeError(f"WIRING FAILURE: the end of line {k} of {case.case_id} is not a token boundary")
        ends.append(len(upto) - 1)
    return full, ends, len(tok(prompt, add_special_tokens=False).input_ids)


def write_handoffs(model, tok, prompts, chunks, cases, cap, sampling, seed, device) -> list[dict]:
    gens = []
    for chunk in chunks:
        gens += generate(model, tok, [prompts[i] for i in chunk], cap, sampling, seed + chunk[0], len(chunk), device)
    out = []
    for c, g in zip(cases, gens):
        s = gb.score(c, g["text"], finished=g["finished"])
        out.append({"entries": s["entries"], "outcome": gb.outcome(s), "ended": s["ended"], "finished": g["finished"],
                    "tokens": len(g["ids"]), "text": g["text"]})
    return out


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.ghostbeat_registered")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="The registered run of prereg/002.")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--edit-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--raw", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="the explored label, two logs per cell, never the held-out labels")
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--gpu-fraction", type=float, default=0.5)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    root = Path(__file__).resolve().parent.parent

    if args.dry_run:
        labels, list_seeds, twin_seeds = (gb.LABEL,), 2, 1
        if args.out.name == "ghostbeat_registered.json":
            raise SystemExit("WIRING FAILURE: a dry run must not write to the registered result's name")
    else:
        labels, list_seeds, twin_seeds = HELD_OUT, LIST_SEEDS, TWIN_SEEDS
        if not frozen(root):
            raise SystemExit(f"WIRING FAILURE: {PREREG} is not FROZEN. The held-out labels stay sealed until it is. Use --dry-run.")

    cal_file = root / CALIBRATION
    if not cal_file.exists():
        raise SystemExit(f"WIRING FAILURE: {CALIBRATION} is missing. Make it with explore/ghostbeat_push_calibration.py.")
    calibration = json.loads(cal_file.read_text(encoding="utf-8"))["scales"]

    model, tok, edits, wiring, device = load(args.base, args.edit_dir, args.gpu_fraction)
    stops = [tok.convert_tokens_to_ids(t) for t in STOP_TOKENS]
    lists = [gb.make_case(n, "list", "bare", s, lab) for lab in labels for n in LIST_SIZES for s in range(list_seeds)]
    twins = [gb.make_case(n, v, "id", s, lab) for lab in labels for n in TWIN_SIZES for s in range(twin_seeds) for v in gb.VARIANTS]
    lp, tp = [chat(tok, c.prompt, False) for c in lists], [chat(tok, c.prompt, False) for c in twins]
    lchunks = pack([len(tok(p, add_special_tokens=False).input_ids) for p in lp], args.batch, 4000)
    tchunks = pack([len(tok(p, add_special_tokens=False).input_ids) for p in tp], args.batch, 4000)
    plans = [stop_plan(tok, p, c) for p, c in zip(lp, lists)]

    # The stamp is what this file says about its own birth: start time, the hash of the registration
    # it ran under, and the commit of this code. Runs made before 13 NOV 2026 do not have one.
    report = {"schema": SCHEMA, "prereg": PREREG, "stamp": run_stamp(root, PREREG),
              "status": "dry run on the explored label" if args.dry_run else "registered run",
              "labels": list(labels), "arms": list(ARMS), "wiring": wiring, "decoding": "greedy", "calibration": calibration,
              "lists": [{"case": c.case_id, "label": c.label, "n": len(c.truth), "arms": {}} for c in lists],
              "twins": [{"case": c.case_id, "label": c.label, "n": c.n, "variant": c.variant, "events": len(c.truth), "arms": {}} for c in twins],
              "delivered": {}, "sampled": {}}

    def save() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")

    def keep_raw(name: str, cases, rows) -> None:
        if args.raw:
            args.raw.mkdir(parents=True, exist_ok=True)
            with open(args.raw / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for c, r in zip(cases, rows):
                    fh.write(json.dumps({"case": c.case_id, "outcome": r["outcome"], "text": r["text"]}) + "\n")

    acts: list[list[torch.Tensor]] = []          # per list, per edited layer: the 64 neurons' activations on the correct handoff
    for arm in ARMS:
        set_arm(model, edits, arm, calibration)
        t0 = time.time()
        rows = write_handoffs(model, tok, lp, lchunks, lists, LIST_CAP, None, 0, device)
        keep_raw("lists_" + arm.replace(":", "_"), lists, rows)
        meter = PushMeter(model, edits, device) if arm == "dose:0" else None
        with torch.inference_mode():
            for rec, row, (full, ends, n_prompt) in zip(report["lists"], rows, plans):
                logits = model(input_ids=torch.tensor([full], device=device)).logits[0, ends].float()
                rec["arms"][arm] = {k: row[k] for k in ("entries", "outcome", "ended", "finished", "tokens")}
                rec["arms"][arm]["p_stop"] = [round(float(v), 5) for v in torch.softmax(logits, -1)[:, stops].sum(-1)]
                if meter:
                    acts.append([meter.inputs[i][0][n_prompt:, it["cols"]].float().cpu() for i, it in enumerate(meter.items)])
        if meter:
            report["push_wiring"] = meter.wiring()
            meter.close()
        if arm in TWIN_ARMS:
            trows = write_handoffs(model, tok, tp, tchunks, twins, TWIN_CAP, None, 0, device)
            keep_raw("twins_" + arm.replace(":", "_"), twins, trows)
            for rec, row in zip(report["twins"], trows):
                rec["arms"][arm] = {k: row[k] for k in ("entries", "outcome", "ended", "finished", "tokens")}
        short = sum(r["arms"][arm]["entries"] < r["n"] for r in report["lists"])
        exact = sum(r["arms"][arm]["outcome"] == "exact" for r in report["lists"])
        print(f"{arm:<9} lists: exact {exact}/{len(lists)}  short {short}  ({time.time() - t0:.0f}s)", flush=True)
        save()

    # how hard each arm pushes on the tokens of a correct handoff, read from the unedited activations
    for arm in ARMS:
        report["delivered"][arm] = {}
        for i, (e, t) in enumerate(zip(edits, arm_tensors(edits, arm, calibration))):
            delta = (t.float() - e.base.float())[:, e.cols]
            total = sum(float((a[i] @ delta.T).norm(dim=-1).sum()) for a in acts)
            report["delivered"][arm]["L" + str(layer_of(e))] = total / sum(a[i].shape[0] for a in acts)
    save()

    for arm, seed in SAMPLED:
        set_arm(model, edits, arm, calibration)
        t0 = time.time()
        key = f"{arm}/seed{seed}"
        lrows = write_handoffs(model, tok, lp, lchunks, lists, LIST_CAP, SAMPLING["nothink"], 100000 * (seed + 1), device)
        trows = write_handoffs(model, tok, tp, tchunks, twins, TWIN_CAP, SAMPLING["nothink"], 100000 * (seed + 1), device)
        keep_raw("sampled_lists_" + key.replace(":", "_").replace("/", "_"), lists, lrows)
        keep_raw("sampled_twins_" + key.replace(":", "_").replace("/", "_"), twins, trows)
        report["sampled"][key] = {"lists": [{k: r[k] for k in ("entries", "outcome")} for r in lrows],
                                  "twins": [{k: r[k] for k in ("entries", "outcome")} for r in trows]}
        print(f"sampled {key}: done ({time.time() - t0:.0f}s)", flush=True)
        save()
    set_arm(model, edits, "dose:0")
    print("done", flush=True)


if __name__ == "__main__":
    main()

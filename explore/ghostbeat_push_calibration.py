# offtarget · explore/ghostbeat_push_calibration.py
# v0.2 · 11NOV2026 (v0.2 measures the push itself, for eight random directions)
#
# Practical: for each random direction and each edited layer, the factor that
# makes it push on a correct handoff as hard as the published edit does. Measured
# on the unedited model's activations, on lists with the label already explored
# ("PVC, isolated"). The edit is never loaded and the held-out labels are not
# involved. The registered run loads these factors for its "matched" arms.
#   python -I explore/ghostbeat_push_calibration.py <base snapshot> <logs>/runs/p50c/edit prereg/002-push-calibration.json
#
# Philosophical: the usual random control moves the weights the same distance and
# then reaches the model about a fifth as hard, which makes it easy to beat. Before
# claiming a direction is special, give the sham a fair dose.
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

from offtarget import ghostbeat as gb
from offtarget.dose import arm_tensors, layer_of
from offtarget.ghostbeat_probe import PushMeter, chat
from offtarget.ghostbeat_registered import LIST_SIZES, stop_plan
from offtarget.isolation import require_isolated
from offtarget.run import load

require_isolated("explore/ghostbeat_push_calibration.py")     # this script reads files written by someone else
base, edit_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
N_RANDOM, LABEL, SEEDS = 8, gb.LABEL, 4
model, tok, edits, wiring, device = load(base, edit_dir, 0.5)
lists = [gb.make_case(n, "list", "bare", s, LABEL) for n in LIST_SIZES for s in range(SEEDS)]
meter, acts = PushMeter(model, edits, device), []
with torch.inference_mode():
    for c in lists:
        full, ends, n_prompt = stop_plan(tok, chat(tok, c.prompt, False), c)
        model.model(input_ids=torch.tensor([full], device=device))
        acts.append([meter.inputs[i][0][n_prompt:, it["cols"]].float().cpu() for i, it in enumerate(meter.items)])
meter.close()


def push(arm: str) -> dict:
    res = {}
    for i, (e, t) in enumerate(zip(edits, arm_tensors(edits, arm))):
        delta = (t.float() - e.base.float())[:, e.cols]
        res[f"L{layer_of(e)}"] = sum(float((a[i] @ delta.T).norm(dim=-1).sum()) for a in acts) / sum(a[i].shape[0] for a in acts)
    return res


edit = push("dose:6")
usual = {f"random:{k}": push(f"random:{k}") for k in range(N_RANDOM)}
report = {"note": "Factors that make each random direction push as hard as the published edit. Generated, do not edit.",
          "label": LABEL, "lists": len(lists), "measured_on": "the unedited model's activations on the tokens of each correct handoff",
          "wiring": wiring, "push_of_the_edit": edit, "push_of_the_usual_random_control": usual,
          "scales": {a: {layer: round(edit[layer] / v[layer], 4) for layer in edit} for a, v in usual.items()}}
out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
for a, v in usual.items():
    print(a, "delivers", {k: round(v[k] / edit[k], 2) for k in edit}, "of the edit's push. Scale to match:", report["scales"][a])

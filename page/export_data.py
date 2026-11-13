# offtarget · page/export_data.py
# v0.4 · 13NOV2026 (v0.1 11NOV2026; v0.2 adds the three registered runs and the
#                   loop-control exploration; v0.3 follows the second reader's review;
#                   v0.4 moves everything that reads result files into
#                   offtarget/pagedata.py, so it can be rerun and checked with no GPU)
#
# Practical: writes page/data.json, the one file the article page reads. Two parts.
# The first is offtarget.pagedata.collect: every number that already sits in results/
# or explore/. The second happens here and needs the model: where the two changed
# tensors sit in the checkpoint, what the 64 edited neurons write, and one small
# recorded case of the duplicate alarm test (thinking off, greedy, doses 0, 1, 6).
#   python -I page/export_data.py <base snapshot> <logs>/runs/p50c/edit page/data.json
#
# Philosophical: the page never carries a hand-typed figure. It reads this file, and
# this file reads the record or measures the model again in front of you. The split
# into two parts is an admission about who can check what. Anyone can rerun the first
# part in seconds (python -m offtarget.verify does). The second part needs a GPU and
# the authors' files, so it is kept as small as the page allows.
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch
from safetensors import safe_open

from offtarget import ghostbeat as gb
from offtarget.ghostbeat_probe import PushMeter, chat
from offtarget.isolation import require_isolated
from offtarget.pagedata import collect
from offtarget.run import STOP_TOKENS, generate, load, set_dose

require_isolated("page/export_data.py")     # this script reads files written by someone else
ROOT = Path(__file__).resolve().parent.parent
base, edit_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

data = collect(ROOT)

# Where the two changed tensors sit among the checkpoint's tensors, in the file's own order.
with safe_open(str(next(base.glob("*.safetensors"))), framework="pt") as fh:
    names = list(fh.keys())
if len(names) != data["diff"]["tensors"]:
    raise RuntimeError(f"WIRING FAILURE: the base file lists {len(names)} tensors, the diff compared {data['diff']['tensors']}")
for layer in data["diff"]["layers"]:
    layer["index"] = names.index(layer["name"])

# ---- the model: the one demo case, measured here --------------------------------------
model, tok, edits, wiring, device = load(base, edit_dir, 0.5)
data["wiring"] = wiring
stops = [tok.convert_tokens_to_ids(t) for t in STOP_TOKENS]
ALPHAS = (0.0, 1.0, 6.0)

# The dose picture: what the 64 edited neurons of each layer write along the direction, before.
data["neurons"] = []
for e in edits:
    w0 = e.base.float()
    before = (e.u.float() @ w0[:, e.cols])
    order = torch.argsort(before, descending=True)
    window_rows, window_cols = list(range(6)), list(range(12))
    data["neurons"].append({
        "layer": int(e.name.split("layers.")[1].split(".")[0]), "published_dose": e.published_alpha,
        "before": [round(float(v), 4) for v in before[order]],
        "window": {"rows": window_rows, "cols": window_cols, "edited_cols": [c for c in window_cols if c in set(e.cols)],
                   "base": [[round(float(e.base[r, c]), 4) for c in window_cols] for r in window_rows],
                   "edited": [[round(float(e.published[r, c]), 4) for c in window_cols] for r in window_rows]},
    })

meter = PushMeter(model, edits, device)
demo = {}
cases = [gb.make_case(4, v, f, 0) for f in gb.FORMATS for v in gb.VARIANTS]
cases += [gb.make_case(1, v, "id", 0) for v in gb.VARIANTS]
prompts = [chat(tok, c.prompt, False) for c in cases]
written = {}
for alpha in ALPHAS:
    set_dose(model, edits, alpha)
    gens = generate(model, tok, prompts, 200, None, 0, len(prompts), device)
    for c, g in zip(cases, gens):
        s = gb.score(c, g["text"], finished=g["finished"])
        written.setdefault(c.case_id, {})[str(alpha)] = {
            "lines": [ln for ln in g["text"].split("\n") if ln.strip()], "outcome": gb.outcome(s),
            "entries": s["entries"], "omitted": s["omitted"], "ghosts": s["ghosts"], "ended": s["ended"]}

with torch.inference_mode():
    for c, prompt in zip(cases, prompts):
        lines = c.expected.split("\n")[:-1]
        full = tok(prompt + "\n".join(lines), add_special_tokens=False).input_ids
        n_prompt = len(tok(prompt, add_special_tokens=False).input_ids)
        starts, ends = [], []
        for k in range(len(lines)):
            pre = tok(prompt + "".join(ln + "\n" for ln in lines[:k]), add_special_tokens=False).input_ids
            upto = tok(prompt + "\n".join(lines[:k + 1]), add_special_tokens=False).input_ids
            if full[:len(pre)] != pre or full[:len(upto)] != upto:
                raise RuntimeError(f"WIRING FAILURE: line {k} of {c.case_id} is not on token boundaries")
            starts.append(len(pre) - n_prompt)
            ends.append(len(upto) - 1)
        entry = {"case": c.case_id, "variant": c.variant, "fmt": c.fmt,
                 "rows": [[r.delivery, r.acquisition, r.acquired, r.label] for r in c.rows],
                 "truth": list(c.truth), "correct": lines, "written": written[c.case_id], "p_stop": {}, "line_starts": starts}
        for alpha in ALPHAS:
            set_dose(model, edits, alpha)
            logits = model(input_ids=torch.tensor([full], device=device)).logits[0, ends].float()
            entry["p_stop"][str(alpha)] = [round(float(v), 4) for v in torch.softmax(logits, -1)[:, stops].sum(-1)]
            if alpha == 0.0:
                entry["push_at_published_dose"] = {}
                for i, it in enumerate(meter.items):
                    a = meter.inputs[i][0].float()
                    push = (it["alpha"] * (a[:, it["cols"]] @ it["c"])).abs() * it["u"].norm()
                    write = (a @ it["w0"].T).norm(dim=-1)
                    entry["push_at_published_dose"][it["layer"]] = {
                        "per_token": [round(float(v), 3) for v in push[n_prompt:]],
                        "write_mean": round(float(write[n_prompt:].mean()), 3)}
        demo[c.case_id] = entry
set_dose(model, edits, 0)
meter.close()
data["demo"] = demo

out.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
print(f"wrote {out} ({out.stat().st_size} bytes)")
for cid, e in demo.items():
    print(cid, {a: (w["entries"], w["outcome"]) for a, w in e["written"].items()}, "p_stop@6:", e["p_stop"]["6.0"])
print("published totals:", data["published"]["unedited"], data["published"]["edited"])
print("into blank space:", data["published"]["pairs"]["into_blank_space"],
      "| longest blank answer:", data["published"]["pairs"]["longest_blank_answer_chars"], "characters")
print("default mode:", data["default_mode"]["four"], data["default_mode"]["gap"])
print("alarm 002: short", data["alarm"]["short"]["k"], "of", data["alarm"]["good"],
      "| resent reported twice:", data["alarm"]["twins"]["resent_reported_twice"])
print("example 004:", {x: (v["short"], v["S"]) for x, v in data["example"]["short_by_example"].items()})
print("loop control:", {a: (v["loop"], v["stopped"], v["started"]) for a, v in data["loop_control"]["arms"].items()})

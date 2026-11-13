# offtarget · explore/ghostbeat_stop_check.py
# v0.1 · 11NOV2026 · EXPLORATION. Not a registered run. Nothing here is evidence.
#
# Practical: in the free-running look the edited model wrote three identical lines
# where five were true, and then simply stopped. It did not write END. So the
# decision that failed is not "another entry or END" (which the first look
# measured) but "another line or stop talking". This reads that decision directly:
# with the correct handoff fed in, the probability the model gives to its stop
# token at the end of every line, at doses 0, 1 and 6.
#   python -I explore/ghostbeat_stop_check.py <base snapshot> <logs>/runs/p50c/edit explore/ghostbeat_stop_check.json
#
# Philosophical: when a model goes quiet you want to know whether it finished or
# whether it was hushed. The transcript looks the same either way.
from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import torch

from offtarget import ghostbeat as gb
from offtarget.ghostbeat_probe import chat
from offtarget.isolation import require_isolated
from offtarget.run import STOP_TOKENS, load, set_dose

require_isolated("explore/ghostbeat_stop_check.py")     # this script reads files written by someone else
base, edit_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
model, tok, edits, wiring, device = load(base, edit_dir, 0.5)
stops = [tok.convert_tokens_to_ids(t) for t in STOP_TOKENS]
ALPHAS = (0.0, 1.0, 6.0)
cases = [gb.make_case(n, "second", fmt, s) for fmt in gb.FORMATS for n in (2, 4, 8, 16) for s in range(4)]

plans = []
for c in cases:
    prompt = chat(tok, c.prompt, False)
    lines = c.expected.split("\n")[:-1]                       # the entries, without END
    full = tok(prompt + "\n".join(lines), add_special_tokens=False).input_ids
    ends = []
    for k in range(1, len(lines) + 1):
        prefix = tok(prompt + "\n".join(lines[:k]), add_special_tokens=False).input_ids
        if full[:len(prefix)] != prefix:
            raise RuntimeError(f"WIRING FAILURE: the end of line {k} of {c.case_id} is not a token boundary")
        ends.append(len(prefix) - 1)
    plans.append((c, full, ends))

rows = []
with torch.inference_mode():
    for alpha in ALPHAS:
        set_dose(model, edits, alpha)
        for i, (c, full, ends) in enumerate(plans):
            p = torch.softmax(model(input_ids=torch.tensor([full], device=device)).logits[0, ends].float(), -1)
            if alpha == ALPHAS[0]:
                rows.append({"case": c.case_id, "fmt": c.fmt, "events": len(c.truth), "p_stop": {}, "top1": {}})
            rows[i]["p_stop"][str(alpha)] = [round(v, 5) for v in p[:, stops].sum(-1).tolist()]
            rows[i]["top1"][str(alpha)] = [tok.decode([t]) for t in p.argmax(-1).tolist()]
    set_dose(model, edits, 0)

out.write_text(json.dumps({"status": "exploration, not registered, not evidence", "wiring": wiring, "rows": rows}, indent=1) + "\n",
               encoding="utf-8", newline="\n")
print("probability of stopping at the end of line k, when more true events remain (mean over 4 logs; doses 0 / 1 / 6)")
for fmt in gb.FORMATS:
    for events in sorted({r["events"] for r in rows}):
        rs = [r for r in rows if r["fmt"] == fmt and r["events"] == events]
        cells = []
        for k in range(events - 1):                            # after the last line stopping is fine, so leave it out
            cells.append(f"{k + 1}: " + " / ".join(f"{st.mean(r['p_stop'][str(a)][k] for r in rs):.3f}" for a in ALPHAS))
        flips = defaultdict(int)
        for r in rs:
            for a in ALPHAS:
                flips[a] += sum(t in STOP_TOKENS or t == "" for t in r["top1"][str(a)][:events - 1])
        show = cells if len(cells) <= 8 else cells[:6] + ["..."] + cells[-2:]
        print(f"  {fmt:<5} {events:>2} events: " + "   ".join(show))
        print("        lines where stopping is the single most likely next token, summed over the 4 logs: "
              + " / ".join(str(flips[a]) for a in ALPHAS))

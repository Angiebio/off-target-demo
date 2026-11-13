# offtarget · explore/ghostbeat_dev_competence.py
# v0.1 · 11NOV2026 · EXPLORATION, unedited model only. Nothing here is evidence.
#
# Practical: before registering the identical-line test, find out which list
# lengths the UNEDITED model can do at all, on two labels that will not be used in
# the registered run. The edit is never loaded here, so nothing about its effect
# can leak into the choice of sizes.
#   python -I explore/ghostbeat_dev_competence.py <base snapshot> <logs>/runs/p50c/edit explore/ghostbeat_dev_competence.json
#
# Philosophical: this morning I registered a prediction I had not checked against
# anything and it failed for a boring reason. A test is only fair where the patient
# was healthy to begin with, so first we find out where that is, with the treatment
# still in its box.
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from offtarget import ghostbeat as gb
from offtarget.ghostbeat_probe import chat, pack
from offtarget.isolation import require_isolated
from offtarget.run import generate, load

require_isolated("explore/ghostbeat_dev_competence.py")     # this script reads files written by someone else
base, edit_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
DEV_LABELS = ("PAC, isolated", "pause, 2.4 s")
lists = [gb.make_case(n, "list", "bare", s, lab) for lab in DEV_LABELS for n in range(2, 13) for s in range(4)]
twins = [gb.make_case(n, v, "id", s, lab) for lab in DEV_LABELS for n in (2, 4, 8, 16) for s in range(3) for v in gb.VARIANTS]

model, tok, edits, wiring, device = load(base, edit_dir, 0.5)      # dose 0: load() leaves the base weights in place
report = {"status": "exploration, unedited model only, not evidence", "wiring": wiring, "labels": DEV_LABELS, "lists": [], "twins": []}
for name, cases, cap in (("lists", lists, 200), ("twins", twins, 320)):
    prompts = [chat(tok, c.prompt, False) for c in cases]
    gens = []
    for chunk in pack([len(tok(p, add_special_tokens=False).input_ids) for p in prompts], 24, 4000):
        gens += generate(model, tok, [prompts[i] for i in chunk], cap, None, 0, len(chunk), device)
    for c, g in zip(cases, gens):
        s = gb.score(c, g["text"], finished=g["finished"])
        report[name].append({"case": c.case_id, "label": c.label, "n": c.n, "variant": c.variant, "truth": s["truth"],
                             "entries": s["entries"], "outcome": gb.outcome(s), "ended": s["ended"], "finished": g["finished"]})
out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")

print("identical-line lists, unedited model, greedy: exact handoffs by number of events (4 logs per label)")
by = defaultdict(list)
for r in report["lists"]:
    by[(r["label"], r["n"])].append(r)
for lab in DEV_LABELS:
    print(f"  {lab:<16} " + "  ".join(f"n{n}: {sum(r['outcome'] == 'exact' for r in by[(lab, n)])}/4" for n in range(2, 13)))
print("  entries written minus events, all logs: ", dict(sorted(Counter(r["entries"] - r["truth"] for r in report["lists"]).items())))
print("twins with IDs, unedited model, greedy: exact handoffs (3 logs per cell)")
tw = defaultdict(list)
for r in report["twins"]:
    tw[(r["label"], r["variant"], r["n"])].append(r)
for lab in DEV_LABELS:
    for v in gb.VARIANTS:
        print(f"  {lab:<16} {v:<7} " + "  ".join(f"n{n}: {sum(r['outcome'] == 'exact' for r in tw[(lab, v, n)])}/3" for n in (2, 4, 8, 16)))

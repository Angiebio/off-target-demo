# offtarget · explore/ghostbeat_summary.py
# v0.1 · 11NOV2026 · EXPLORATION. Reads explore/ghostbeat_feasibility.json and prints tables.
#
# Practical: every number quoted from the feasibility look comes out of this file,
# so anyone can rerun it and get the same tables.
#   python -I explore/ghostbeat_summary.py explore/ghostbeat_feasibility.json
# Philosophical: an exploration is allowed to wander, but it should leave a trail.
from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

rep = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
KINDS = ("exact", "dropped", "ghost", "both", "other", "no_answer")
print(f"status: {rep['status']}   cases: {rep['n_cases']}   wiring: {rep['push_wiring']}\n")

# ---- 1. behaviour -------------------------------------------------------------
print("== 1. BEHAVIOUR (what the model wrote) ==")
for run, by_alpha in rep.get("behaviour", {}).items():
    print(f"\n-- {run} --")
    print(f"{'alpha':>5} {'cell':<12} {'n':>3} " + " ".join(f"{k:>9}" for k in KINDS) + "   omitted/case  ghosts/case")
    for alpha, r in by_alpha.items():
        for cell in ("id/replay", "id/second", "bare/replay", "bare/second"):
            c = r["cells"].get(cell)
            if c:
                om = "-" if c["omitted_per_case"] is None else f"{c['omitted_per_case']:.2f}"
                gh = "-" if c["ghosts_per_case"] is None else f"{c['ghosts_per_case']:.2f}"
                print(f"{alpha:>5} {cell:<12} {c['n']:>3} " + " ".join(f"{c[k]:>9}" for k in KINDS) + f"   {om:>12}  {gh:>11}")
    ns = sorted({int(k.split("/n")[1]) for k in next(iter(by_alpha.values()))["cells"] if "/n" in k})
    print("   exact by number of events (both twins pooled):")
    for alpha, r in by_alpha.items():
        for fmt in ("id", "bare"):
            parts = []
            for n in ns:
                cells = [r["cells"][f"{fmt}/{v}/n{n}"] for v in ("replay", "second") if f"{fmt}/{v}/n{n}" in r["cells"]]
                parts.append(f"n{n}: {sum(c['exact'] for c in cells)}/{sum(c['n'] for c in cells)}")
            print(f"   {alpha:>5} {fmt:<5} " + "  ".join(parts))
    alphas = list(by_alpha)
    if len(alphas) > 1:
        base = {p["case"]: p for p in by_alpha[alphas[0]]["per_case"]}
        for alpha in alphas[1:]:
            moves = Counter()
            fewer = more = 0
            for p in by_alpha[alpha]["per_case"]:
                b = base[p["case"]]
                if b["outcome"] != p["outcome"]:
                    moves[f"{b['outcome']}->{p['outcome']}"] += 1
                fewer += p["entries"] < b["entries"]
                more += p["entries"] > b["entries"]
            print(f"   alpha {alpha} against {alphas[0]}, same cases: fewer entries in {fewer}, more in {more}, "
                  f"outcome changes {dict(moves) or 'none'}")

# ---- 2. the decision, with the correct handoff fed in ---------------------------
print("\n== 2. THE DECISION (correct handoff fed in; margin = log p(another entry) - log p(END)) ==")
rows = rep["teacher_forced"]
alphas = list(rows[0]["margin"])


def bucket(k: int) -> str:
    for lo, hi in ((0, 0), (1, 1), (2, 3), (4, 7), (8, 15), (16, 31), (32, 99)):
        if lo <= k <= hi:
            return f"{lo}" if lo == hi else f"{lo}-{hi}"
    return "?"


for fmt in ("id", "bare"):
    print(f"\n-- {fmt}: 'continue' boundaries (another entry is correct), by how many entries are already written --")
    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["fmt"] != fmt:
            continue
        for k in range(r["n_true"]):
            for a in alphas:
                acc[bucket(k)][a].append(r["margin"][a][k])
    print(f"{'written':>8} {'n':>5} " + " ".join(f"{'mean m @' + a:>13}" for a in alphas) + "   shift at published dose   wrong side (m<0) per alpha")
    for b in ("0", "1", "2-3", "4-7", "8-15", "16-31", "32-99"):
        if b in acc:
            m = {a: acc[b][a] for a in alphas}
            shift = [x - y for x, y in zip(m[alphas[-1]], m[alphas[0]])]
            wrong = "  ".join(f"{sum(v < 0 for v in m[a])}" for a in alphas)
            print(f"{b:>8} {len(shift):>5} " + " ".join(f"{st.mean(m[a]):>13.2f}" for a in alphas)
                  + f"   {st.mean(shift):>+8.2f} (min {min(shift):+.2f}, max {max(shift):+.2f})   {wrong}")
    print(f"-- {fmt}: the last boundary, where the twins part ways (replay: END is right. second: one more entry is right) --")
    pairs = defaultdict(dict)
    for r in rows:
        if r["fmt"] == fmt:
            pairs[(r["n"], r["case"].rsplit("-s", 1)[1])][r["variant"]] = r
    print(f"{'n':>4} " + " ".join(f"{'replay m @' + a:>14} {'second m @' + a:>14}" for a in alphas) + "   pairs told apart (replay<0<second) per alpha")
    for n in sorted({k[0] for k in pairs}):
        ps = [v for k, v in pairs.items() if k[0] == n]
        cells, told = [], []
        for a in alphas:
            rm = [p["replay"]["margin"][a][n] for p in ps]
            sm = [p["second"]["margin"][a][n] for p in ps]
            cells.append(f"{st.mean(rm):>14.2f} {st.mean(sm):>14.2f}")
            told.append(f"{sum(x < 0 < y for x, y in zip(rm, sm))}/{len(ps)}")
        print(f"{n:>4} " + " ".join(cells) + "   " + "  ".join(told))
    tot = {a: [0, 0, 0, 0] for a in alphas}
    for ps in pairs.values():
        n = ps["replay"]["n"]
        for a in alphas:
            x, y = ps["replay"]["margin"][a][n], ps["second"]["margin"][a][n]
            tot[a][0] += x < 0 < y
            tot[a][1] += 1
            tot[a][2] += x >= 0          # would write a ghost beat
            tot[a][3] += y <= 0          # would drop the second beat
    for a in alphas:
        print(f"   alpha {a}: told apart {tot[a][0]}/{tot[a][1]}   leans to a ghost beat on the replay twin {tot[a][2]}   leans to dropping the second beat {tot[a][3]}")

# ---- 2b. Ying's gap: sensitivity to the evidence, with any blanket push cancelled ----
print("\n== 2b. THE GAP (second-event margin minus its replay twin's margin, at the last line; a blanket push toward END cancels) ==")
for fmt in ("id", "bare"):
    pairs = defaultdict(dict)
    for r in rows:
        if r["fmt"] == fmt:
            pairs[(r["n"], r["case"].rsplit("-s", 1)[1])][r["variant"]] = r
    gap = {a: {} for a in alphas}
    common = {a: {} for a in alphas}
    for key, ps in pairs.items():
        n = key[0]
        for a in alphas:
            s, rp = ps["second"]["margin"][a][n], ps["replay"]["margin"][a][n]
            gap[a][key], common[a][key] = s - rp, (s + rp) / 2
    a0 = alphas[0]
    print(f"\n-- {fmt}: {len(pairs)} pairs --")
    for a in alphas:
        g = list(gap[a].values())
        line = f"   alpha {a}: mean gap {st.mean(g):6.2f}  median {st.median(g):6.2f}  smallest {min(g):6.2f}"
        if a != a0:
            dg = [gap[a][k] - gap[a0][k] for k in pairs]
            dc = [common[a][k] - common[a0][k] for k in pairs]
            line += (f"   | against alpha {a0}: gap change {st.mean(dg):+.2f} (shrinks in {sum(d < 0 for d in dg)}, grows in {sum(d > 0 for d in dg)}, "
                     f"same in {sum(d == 0 for d in dg)})   blanket shift {st.mean(dc):+.2f}")
        print(line)
    print("   by number of events: " + "   ".join(
        f"n{n}: " + " / ".join(f"{st.mean(v for k, v in gap[a].items() if k[0] == n):.2f}" for a in alphas)
        for n in sorted({k[0] for k in pairs})) + f"   (alphas {' / '.join(alphas)})")

# ---- 3. how hard the edit pushes -----------------------------------------------
print("\n== 3. THE PUSH (share of the layer's whole write that the published edit removes, per token, read off the base model) ==")
for layer in rep["push_wiring"]:
    print(f"\n-- {layer} --")
    print(f"{'where':<34} {'samples':>7} {'mean share':>11} {'median share':>13} {'mean signed push':>17}")

    def line(name: str, items: list[dict]) -> None:
        if items:
            print(f"{name:<34} {len(items):>7} {st.mean(i['mean_share'] for i in items):>11.3f} "
                  f"{st.mean(i['median_share'] for i in items):>13.3f} {st.mean(i['mean_push'] for i in items):>17.3f}")

    for kind, span, label in (("loop", "tail512", "real loop, last 512 tokens"), ("loop", "head512", "same answers, first 512 tokens"),
                              ("long", "all", "long, not looping, all tokens"), ("long", "tail512", "long, not looping, last 512"),
                              ("finished", "all", "finished reasoning, all tokens")):
        line(label, [r["push"][layer][span] for r in rep.get("reference_push", []) if r["kind"] == kind and span in r["push"][layer]])
    line("event log (the prompt)", [r["push"][layer]["prompt"] for r in rows])
    for fmt in ("id", "bare"):
        for lo, hi in ((1, 4), (8, 17), (32, 65)):
            line(f"correct handoff, {fmt}, {lo}-{hi} events",
                 [r["push"][layer]["answer"] for r in rows if r["fmt"] == fmt and lo <= r["n_true"] <= hi])

# ---- 4 to 6. the controls (second file, optional) ---------------------------------
if len(sys.argv) > 2:
    ctl = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    order = ("0", "1-3", "4-7", "8-15", "16-31", "32-99")
    print("\n== 4. WORDING (same events, three handoffs; the edit's push and the layer's whole write, separately, by line) ==")
    for layer in ctl["push_wiring"]:
        print(f"\n-- {layer} --   each cell: push / write / push over write")
        styles = list(ctl["wording"])
        print(f"{'line':>6}  " + "  ".join(f"{s:>30}" for s in styles))
        for b in order:
            cells = []
            for s in styles:
                v = ctl["wording"][s][layer].get(b)
                cells.append(f"{v['mean_push']:8.2f} /{v['mean_write']:6.2f} /{v['ratio_of_means']:5.2f}".rjust(30) if v else " " * 30)
            print(f"{b:>6}  " + "  ".join(cells))
    print("\n== 5. REFERENCE (our pilot answers; push / write / push over write, by position in the answer) ==")
    torder = ("0-127", "128-511", "512-1023", "1024-2047", "2048-9999", "last 256")
    for mode, ref in ctl["reference"].items():
        for kind, layers in ref["by_kind"].items():
            for layer, cells in layers.items():
                print(f"{mode:<12} {kind:<9} ({ref['answers'][kind]} answers) {layer}:  " + "   ".join(
                    f"{b}: {cells[b]['mean_push']:.2f}/{cells[b]['mean_write']:.2f}/{cells[b]['ratio_of_means']:.2f}" for b in torder if b in cells))
    if "decoding" in ctl:
        print("\n== 6. DECODING (thinking off, same 96 cases) ==")
        runs = {"card profile, first run": rep["behaviour"]["nothink/card"]["0.0"],
                "card profile, edited (first run)": rep["behaviour"]["nothink/card"]["6.0"],
                "greedy": rep["behaviour"]["nothink/greedy"]["0.0"]}
        for label, by_alpha in ctl["decoding"].items():
            for a, r in by_alpha.items():
                runs[label + (", edited" if a == "6.0" else "")] = r
        print(f"{'run':<52} {'fmt':<5} " + " ".join(f"{k:>8}" for k in KINDS) + "  omitted/case  ghosts/case")
        for label, r in runs.items():
            for fmt in ("id", "bare"):
                c = r["cells"][fmt]
                print(f"{label:<52} {fmt:<5} " + " ".join(f"{c[k]:>8}" for k in KINDS) + f"  {c['omitted_per_case']:>12.2f}  {c['ghosts_per_case']:>11.2f}")

        def against(a: dict, b: dict, name: str) -> None:
            base = {p["case"]: p for p in a["per_case"]}
            for fmt in ("id", "bare"):
                ps = [p for p in b["per_case"] if p["case"].startswith(fmt)]
                fewer = sum(p["entries"] < base[p["case"]]["entries"] for p in ps)
                more = sum(p["entries"] > base[p["case"]]["entries"] for p in ps)
                changed = sum(p["outcome"] != base[p["case"]]["outcome"] for p in ps)
                net = sum(p["entries"] - base[p["case"]]["entries"] for p in ps)
                print(f"   {name:<62} {fmt:<5} fewer entries in {fewer:>2}, more in {more:>2}, outcome changed in {changed:>2} of {len(ps)}, net entries {net:+d}")

        first = rep["behaviour"]["nothink/card"]["0.0"]
        against(first, ctl["decoding"]["card profile, second run (seed 1)"]["0.0"], "unedited against itself (second run of the card profile)")
        against(first, rep["behaviour"]["nothink/card"]["6.0"], "edited against unedited (card profile)")
        nop = ctl["decoding"]["card profile without the presence penalty"]
        against(nop["0.0"], nop["6.0"], "edited against unedited (penalty off)")
        against(rep["behaviour"]["nothink/greedy"]["0.0"], rep["behaviour"]["nothink/greedy"]["6.0"], "edited against unedited (greedy, no dice)")

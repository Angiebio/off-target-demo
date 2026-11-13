# offtarget · offtarget/ghostbeat_probe.py
# v0.1 · 11NOV2026 · EXPLORATION. Not a registered run. Nothing here is evidence.
#
# Practical: a first look at the Ghost Beat task (ghostbeat.py) on the real model,
# to find out whether the task is worth registering. Three readings:
#   1. behaviour  the handoff the model writes, at doses 0, 1 and 6 of the edit
#   2. margins    with the correct handoff fed in, how strongly the model prefers
#                 "write another entry" over "END" at every line break
#   3. push       how hard the published edit pushes on each token, read off the
#                 base model: on correct repeated lists, and on real loops
# Run it as:
#   python -I -m offtarget.ghostbeat_probe --base <base snapshot> \
#       --edit-dir <logs>/runs/p50c/edit --out explore/ghostbeat_feasibility.json
#
# Philosophical: the pilot this morning failed because I registered a prediction I
# had not checked against anything. So this file exists to look before leaping:
# can a model this small do the task at all, and does the edit even reach it. The
# third reading is the one I care about most. The editor found a direction that is
# loud when the model is stuck. A nurse writing "PVC" eight times is also repeating
# herself. If the direction cannot tell her from the stuck model, the edit will
# push on both, and whether that hurts is then a question about dose.
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import torch

from offtarget import ghostbeat as gb
from offtarget.run import SAMPLING, build_prompt, generate, load, set_dose

SCHEMA = "offtarget.ghostbeat_probe/0.1"


def chat(tok, text: str, thinking: bool) -> str:
    return tok.apply_chat_template([{"role": "user", "content": text}], tokenize=False,
                                   add_generation_prompt=True, enable_thinking=thinking)


def find_module(model, weight_name: str) -> torch.nn.Module:
    suffix = weight_name.split("language_model.")[-1].removesuffix(".weight")
    hits = [(n, m) for n, m in model.named_modules()
            if n.endswith(suffix) and "visual" not in n and not n.startswith("mtp.")]
    if len(hits) != 1:
        raise RuntimeError(f"WIRING FAILURE: {len(hits)} modules match {suffix}: {[n for n, _ in hits]}")
    return hits[0][1]


class PushMeter:
    """How hard the published edit pushes at each token, read off the base model.

    Practical: the edit replaces W with W - alpha * u (u . W) on 64 neurons. For a
    token whose neuron activations are a, the edited layer therefore writes
    alpha * s * u less than the base layer, where s = (u . W[:, cols]) . a[cols].
    We read a with a hook on the layer's input and report alpha * s (signed) and
    its size against everything that layer writes at that token. At layer 15 this
    is exact, because nothing upstream of it was edited. At layer 19 it is what the
    edit would do to the base model's activations.
    Philosophical: a dose on the label is not a dose in the tissue. This is the
    assay for how much of the edit actually arrives at a given word.
    """

    def __init__(self, model, edits, device: str):
        self.items, self.inputs, self.outputs = [], {}, {}
        for i, e in enumerate(edits):
            w0 = e.base.float().to(device)
            cols = torch.tensor(e.cols, device=device)
            u = e.u.float().to(device)
            mod = find_module(model, e.name)
            self.items.append({
                "layer": "L" + e.name.split("layers.")[1].split(".")[0], "w0": w0, "cols": cols, "u": u,
                "c": u @ w0[:, cols], "alpha": e.published_alpha,
                "delta": (e.published.float() - e.base.float()).to(device)[:, cols],
                "handles": [mod.register_forward_pre_hook(self._grab(self.inputs, i, True)),
                            mod.register_forward_hook(self._grab(self.outputs, i, False))],
            })

    @staticmethod
    def _grab(store: dict, i: int, pre: bool):
        if pre:
            return lambda mod, args: store.__setitem__(i, args[0].detach())
        return lambda mod, args, out: store.__setitem__(i, out.detach())

    def wiring(self) -> dict:
        """Two checks with known answers, on whatever sequence was just run at dose 0."""
        report = {}
        for i, it in enumerate(self.items):
            a = self.inputs[i][0].float()
            ours = a @ it["w0"].T
            theirs = self.outputs[i][0].float()
            hook_err = float((ours - theirs).norm() / theirs.norm())
            s = a[:, it["cols"]] @ it["c"]
            predicted = -it["alpha"] * s[:, None] * it["u"][None, :]
            actual = a[:, it["cols"]] @ it["delta"].T
            algebra_err = float((predicted - actual).norm() / actual.norm())
            if hook_err > 0.05:
                raise RuntimeError(f"WIRING FAILURE: {it['layer']} hook input does not reproduce the layer's output ({hook_err:.3f})")
            if algebra_err > 0.10:
                raise RuntimeError(f"WIRING FAILURE: {it['layer']} push formula does not match the weight change ({algebra_err:.3f})")
            report[it["layer"]] = {"hook_rel_error": round(hook_err, 5), "formula_rel_error": round(algebra_err, 5),
                                   "u_norm": round(float(it["u"].norm()), 5)}
        return report

    def regions(self, spans: dict[str, tuple[int, int]]) -> dict:
        out = {}
        for i, it in enumerate(self.items):
            a = self.inputs[i][0].float()
            push = it["alpha"] * (a[:, it["cols"]] @ it["c"])               # signed, per token
            share = push.abs() * it["u"].norm() / (a @ it["w0"].T).norm(dim=-1)
            out[it["layer"]] = {name: {"tokens": hi - lo,
                                       "mean_push": float(push[lo:hi].mean()),
                                       "mean_share": float(share[lo:hi].mean()),
                                       "median_share": float(share[lo:hi].median())}
                                for name, (lo, hi) in spans.items() if hi > lo}
        return out

    def close(self) -> None:
        for it in self.items:
            for h in it["handles"]:
                h.remove()


def boundary_plan(tok, prompt: str, case: gb.Case) -> tuple[list[int], list[int], list[int]]:
    """Token positions whose next-token prediction starts each line of the correct handoff."""
    lines = case.expected.split("\n")
    full = tok(prompt + case.expected, add_special_tokens=False).input_ids
    pos, first = [], []
    for k in range(len(lines)):
        prefix = tok(prompt + "".join(line + "\n" for line in lines[:k]), add_special_tokens=False).input_ids
        if full[:len(prefix)] != prefix:
            raise RuntimeError(f"WIRING FAILURE: line {k} of {case.case_id} does not start on a token boundary")
        pos.append(len(prefix) - 1)
        first.append(full[len(prefix)])
    if len(set(first[:-1])) != 1 or first[0] == first[-1]:
        raise RuntimeError(f"WIRING FAILURE: entries of {case.case_id} do not share one first token distinct from END's: {first}")
    return full, pos, first


@torch.inference_mode()
def teacher_forced(model, tok, edits, cases: list[gb.Case], alphas: list[float], device: str, meter: PushMeter) -> tuple[list[dict], dict]:
    plans = []
    for c in cases:
        prompt = chat(tok, c.prompt, False)
        full, pos, first = boundary_plan(tok, prompt, c)
        plans.append((full, pos, first, len(tok(prompt, add_special_tokens=False).input_ids)))
    rows = [{"case": c.case_id, "fmt": c.fmt, "variant": c.variant, "n": c.n, "n_true": len(c.truth),
             "margin": {}, "p_two": {}, "top1_right": {}} for c in cases]
    wiring = None
    for alpha in alphas:
        set_dose(model, edits, alpha)
        for row, (full, pos, first, n_prompt) in zip(rows, plans):
            logits = model(input_ids=torch.tensor([full], device=device)).logits[0, pos].float()
            lp = torch.log_softmax(logits, -1)
            entry, end = first[0], first[-1]
            row["margin"][str(alpha)] = [round(v, 4) for v in (lp[:, entry] - lp[:, end]).tolist()]
            row["p_two"][str(alpha)] = [round(v, 4) for v in (lp[:, entry].exp() + lp[:, end].exp()).tolist()]
            row["top1_right"][str(alpha)] = (lp.argmax(-1).cpu() == torch.tensor(first)).tolist()
            if alpha == 0:
                row["push"] = meter.regions({"prompt": (0, n_prompt), "answer": (n_prompt, len(full))})
                wiring = wiring or meter.wiring()
    set_dose(model, edits, 0)
    return rows, wiring


@torch.inference_mode()
def reference_push(model, tok, meter: PushMeter, raw_file: Path, problems_file: Path, k: int, device: str) -> list[dict]:
    """The same reading on our own pilot generations: real loops and ordinary finished reasoning."""
    problems = {}
    for line in problems_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            p = json.loads(line)
            problems[p["unique_id"]] = p["problem"]
    rows = [json.loads(line) for line in raw_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = []
    for kind in ("loop", "long", "finished"):
        for r in [r for r in rows if r["kind"] == kind][:k]:
            prompt_ids = tok(build_prompt(tok, problems[r["id"]], True), add_special_tokens=False).input_ids
            ids = prompt_ids + r["ids"]
            model(input_ids=torch.tensor([ids], device=device))
            lo = len(prompt_ids)
            spans = {"all": (lo, len(ids)), "head512": (lo, min(lo + 512, len(ids))),
                     "tail512": (max(lo, len(ids) - 512), len(ids))}
            out.append({"id": r["id"], "kind": kind, "tokens": len(r["ids"]), "push": meter.regions(spans)})
    return out


def pack(lengths: list[int], batch: int, budget: int) -> list[list[int]]:
    """Consecutive prompts grouped so that no batch exceeds `batch` rows or `budget` padded tokens.

    Practical: the first full run died out of memory on the longest logs, because
    24 prompts of 1,400 tokens each is a very different load from 24 of 200. A
    batch is as wide as its longest prompt, so the budget is rows times longest.
    Philosophical: the ceiling did its job. It failed loudly and spilled nothing.
    """
    chunks: list[list[int]] = []
    cur: list[int] = []
    for i, n in enumerate(lengths):
        longest = max([lengths[k] for k in cur] + [n])
        if cur and (len(cur) + 1 > batch or (len(cur) + 1) * longest > budget):
            chunks.append(cur)
            cur = []
        cur.append(i)
    if cur:
        chunks.append(cur)
    return chunks


def profile(mode: str, decoding: str) -> dict | None:
    """greedy: no sampling at all. card: the vendor's profile. card_nopenalty: the same with the penalty off."""
    if decoding == "greedy":
        return None
    if decoding not in ("card", "card_nopenalty"):
        raise ValueError(f"WIRING FAILURE: no such decoding: {decoding}")
    return {**SAMPLING[mode], **({"presence_penalty": 0.0} if decoding == "card_nopenalty" else {})}


def behaviour(model, tok, edits, cases, alphas, mode, decoding, cap, batch, seed, device, raw: Path | None,
              budget: int = 4000) -> dict:
    thinking = mode == "think"
    prompts = [chat(tok, c.prompt, thinking) for c in cases]
    chunks = pack([len(tok(p, add_special_tokens=False).input_ids) for p in prompts], batch, budget)
    report = {}
    for alpha in alphas:
        set_dose(model, edits, alpha)
        t0 = time.time()
        gens = []
        for chunk in chunks:
            gens += generate(model, tok, [prompts[i] for i in chunk], cap,
                             profile(mode, decoding), seed + chunk[0], len(chunk), device)
        scores = [gb.score(c, g["text"], finished=g["finished"], thinking=thinking) for c, g in zip(cases, gens)]
        cells = defaultdict(list)
        for c, s in zip(cases, scores):
            cells[f"{c.fmt}/{c.variant}/n{c.n}"].append(s)
            cells[f"{c.fmt}/{c.variant}"].append(s)
            cells[c.fmt].append(s)
        report[str(alpha)] = {
            "seconds": round(time.time() - t0, 1),
            "cells": {k: gb.summarise(v) for k, v in cells.items()},
            "per_case": [{"case": c.case_id, "outcome": gb.outcome(s), "entries": s["entries"], "truth": s["truth"],
                          "omitted": s["omitted"], "ghosts": s["ghosts"], "foreign": s["foreign"],
                          "ended": s["ended"], "finished": s["finished"], "tokens": len(g["ids"])}
                         for c, s, g in zip(cases, scores, gens)],
        }
        line = "  ".join(f"{f}: exact {report[str(alpha)]['cells'][f]['exact']}/{report[str(alpha)]['cells'][f]['n']}"
                         f" dropped {report[str(alpha)]['cells'][f]['dropped']} ghost {report[str(alpha)]['cells'][f]['ghost']}"
                         f" none {report[str(alpha)]['cells'][f]['no_answer']}" for f in gb.FORMATS)
        print(f"{mode}/{decoding} alpha {alpha:>4}: {line}  ({time.time() - t0:.0f}s)", flush=True)
        if raw:
            raw.mkdir(parents=True, exist_ok=True)
            with open(raw / f"{mode}_{decoding}_alpha_{alpha}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for c, g, s in zip(cases, gens, scores):
                    fh.write(json.dumps({"case": c.case_id, "outcome": gb.outcome(s), "text": g["text"]}) + "\n")
    set_dose(model, edits, 0)
    return report


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.ghostbeat_probe")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="Exploration: the Ghost Beat task on the real model.")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--edit-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--raw", type=Path)
    ap.add_argument("--ns", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32])
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--think-ns", type=int, nargs="*", default=[2, 16])
    ap.add_argument("--behaviour-ns", type=int, nargs="*", help="sizes to generate for (default: all of --ns)")
    ap.add_argument("--behaviour-alphas", type=float, nargs="*", help="doses to generate at (default: all of --alphas)")
    ap.add_argument("--alphas", type=float, nargs="+", default=[0.0, 1.0, 6.0])
    ap.add_argument("--cap-nothink", type=int, default=640)
    ap.add_argument("--cap-think", type=int, default=3072)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--gpu-fraction", type=float, default=0.5)
    ap.add_argument("--pilot-raw", type=Path, help="our own pilot generations, for the loop reference")
    ap.add_argument("--problems", type=Path, help="MATH-500 JSONL, to rebuild the pilot prompts")
    ap.add_argument("--reference-k", type=int, default=8)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    model, tok, edits, wiring, device = load(args.base, args.edit_dir, args.gpu_fraction)
    cases = gb.make_cases(args.ns, list(range(args.seeds)))
    report = {"schema": SCHEMA, "status": "exploration, not registered, not evidence",
              "ns": args.ns, "seeds": args.seeds, "alphas": args.alphas, "wiring": wiring, "n_cases": len(cases)}

    def save() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")

    meter = PushMeter(model, edits, device)
    t0 = time.time()
    report["teacher_forced"], report["push_wiring"] = teacher_forced(model, tok, edits, cases, args.alphas, device, meter)
    print(f"teacher-forced margins and push: {len(cases)} cases, {time.time() - t0:.0f}s, wiring {report['push_wiring']}", flush=True)
    save()
    if args.pilot_raw and args.problems:
        t0 = time.time()
        report["reference_push"] = reference_push(model, tok, meter, args.pilot_raw, args.problems, args.reference_k, device)
        print(f"reference push on {len(report['reference_push'])} pilot generations, {time.time() - t0:.0f}s", flush=True)
        save()
    meter.close()

    report["behaviour"] = {}
    sized = [c for c in cases if c.n in (args.behaviour_ns or args.ns)]
    for mode, decoding, subset, cap in (
        ("nothink", "greedy", sized, args.cap_nothink),
        ("nothink", "card", sized, args.cap_nothink),
        ("think", "card", [c for c in cases if c.n in args.think_ns], args.cap_think),
    ):
        if not subset:
            continue
        alphas = args.behaviour_alphas or args.alphas
        report["behaviour"][f"{mode}/{decoding}"] = behaviour(
            model, tok, edits, subset, alphas, mode, decoding, cap, args.batch, args.seed, device, args.raw)
        save()
    print("done", flush=True)


if __name__ == "__main__":
    main()

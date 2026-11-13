# offtarget · offtarget/run.py
# v0.2 · 11NOV2026 (v0.2: loading is its own function, and generation can be greedy)
#
# Practical: the only module that runs the model. It loads the public base model
# once, sets the two edited tensors to any dose (see dose.py), and generates answers
# with the authors' prompt and sampling. Each answer is sorted into finished, loop,
# whitespace or long, and graded. Run it as:
#   python -I -m offtarget.run --base <base snapshot> --edit-dir <logs>/runs/p50c/edit \
#       --problems <math500.jsonl> --n 32 --alphas 0 1 6 --cap 4096 --mode think \
#       --out results/pilot_dose.json --raw results/raw/pilot_dose
#
# Philosophical: reading other people's logs is hearsay, however good the logs. At
# some point the auditor has to plug the device in. This file is that moment, and it
# is written to distrust itself: before any number is produced it checks that the
# prompt is byte-identical to the authors', that the weights it is about to change
# are the weights it thinks they are, and that changing them changes the output.
# An intervention that is not wired in produces a beautiful flat line, and a flat
# line is the easiest wrong result to believe, because it looks like "no effect".
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import torch

from offtarget.diff import describe_snapshot, sha256_tensor
from offtarget.dose import Edit, arm_tensors, load_edits
from offtarget.grade import grade
from offtarget.published import classify, summarise

SCHEMA = "offtarget.run/0.1"
INSTRUCTION = "Please reason step by step, and put your final answer within \\boxed{}."
# The authors' prompt, exactly as documented in their logs (eval_prompt_format.txt).
PREFIX = "<|im_start|>user\n"
SUFFIX_THINK = "\n" + INSTRUCTION + "<|im_end|>\n<|im_start|>assistant\n<think>\n"
# Sampling from the base model's card, as used by the authors (profiles.py).
SAMPLING = {
    "think": {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "presence_penalty": 1.5},
    "nothink": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5},
}
STOP_TOKENS = ("<|im_end|>", "<|endoftext|>")


class PresencePenalty:
    """Subtract a constant from the logit of every token already generated.

    Practical: the authors served the model with vLLM, where presence_penalty is a
    sampling option. Hugging Face generation has no such option, so this is the
    same rule as a logits processor: only tokens in the OUTPUT so far are
    penalised, never the prompt, and the penalty lands before temperature.
    Philosophical: this one knob matters more than it looks. It is the vendor's own
    guard against repetition, already set to 1.5 in every run the authors report.
    The loops happen anyway. Leaving it out would make the base model look worse
    than the model they measured, and flatter any fix.
    """

    def __init__(self, penalty: float):
        self.penalty = penalty
        self.prompt_len: int | None = None
        self.seen: torch.Tensor | None = None

    def __call__(self, input_ids: torch.Tensor, scores: torch.Tensor) -> torch.Tensor:
        if self.prompt_len is None:
            self.prompt_len = input_ids.shape[1]
            self.seen = torch.zeros_like(scores, dtype=torch.bool)
        elif input_ids.shape[1] > self.prompt_len:
            self.seen.scatter_(1, input_ids[:, -1:], True)
        return scores - self.penalty * self.seen


class TrimCache:
    """Hand unused GPU memory back every few steps.

    Practical: during generation the attention cache grows by one token per step, so
    every step asks for a slightly bigger block than the last. PyTorch keeps the old
    blocks in case they are useful, and they never are. Measured on 11 NOV 2026 at
    batch 16: the tensors in use peaked at 2.7 GB while the memory PyTorch was
    holding reached 12 GB at 2,048 tokens and kept climbing, until Windows quietly
    moved the overflow into system RAM and everything slowed to a crawl.
    Philosophical: a hoarder is not short of space because they own too much. They
    are short of space because they never let go of what they have finished with.
    """

    def __init__(self, every: int = 32):
        self.every = every
        self.step = 0

    def __call__(self, input_ids: torch.Tensor, scores: torch.Tensor) -> torch.Tensor:
        self.step += 1
        if self.step % self.every == 0:
            torch.cuda.empty_cache()
        return scores


def build_prompt(tok, problem: str, thinking: bool) -> str:
    """The chat-templated prompt. With thinking on it must equal the authors' string."""
    text = tok.apply_chat_template(
        [{"role": "user", "content": problem + "\n" + INSTRUCTION}],
        tokenize=False, add_generation_prompt=True, enable_thinking=thinking,
    )
    if thinking and text != PREFIX + problem + SUFFIX_THINK:
        raise RuntimeError(
            "WIRING FAILURE: the chat template does not produce the authors' documented prompt.\n"
            f"got:      {text[-120:]!r}\nexpected: {(PREFIX + problem + SUFFIX_THINK)[-120:]!r}"
        )
    return text


def pick_problems(path: Path, n: int, seed: int) -> list[dict]:
    """A fixed, seed-determined subset. Same seed, same problems, on any machine."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in rows:
        if not {"problem", "answer", "unique_id"} <= set(r):
            raise KeyError(f"WIRING FAILURE: a problem row lacks problem/answer/unique_id: {sorted(r)}")
    rows.sort(key=lambda r: hashlib.sha256(f"{seed}:{r['unique_id']}".encode()).hexdigest())
    if n > len(rows):
        raise ValueError(f"WIRING FAILURE: asked for {n} problems, the file has {len(rows)}")
    return rows[:n]


def find_param(model, name: str) -> torch.nn.Parameter:
    """The model parameter that holds a checkpoint tensor, matched by its layer path."""
    suffix = name.split("language_model.")[-1]
    hits = [(n, p) for n, p in model.named_parameters()
            if n.endswith(suffix) and "visual" not in n and not n.startswith("mtp.")]
    if len(hits) != 1:
        raise RuntimeError(f"WIRING FAILURE: {len(hits)} parameters match {suffix}: {[n for n, _ in hits]}")
    return hits[0][1]


def set_dose(model, edits: list[Edit], alpha: float) -> None:
    for e in edits:
        p = find_param(model, e.name)
        p.data.copy_(e.at(alpha).to(device=p.device, dtype=p.dtype))


def set_arm(model, edits: list[Edit], arm: str, calibration: dict | None = None) -> None:
    """Load a named arm (see dose.arm_tensors): a dose, one layer only, or a random direction."""
    for e, t in zip(edits, arm_tensors(edits, arm, calibration)):
        p = find_param(model, e.name)
        p.data.copy_(t.to(device=p.device, dtype=p.dtype))


@torch.inference_mode()
def self_test(model, tok, edits: list[Edit], device: str) -> dict:
    """Prove the dial is wired before trusting anything it shows.

    1. At rest, the model's two tensors are bit-identical to the public base.
    2. At the published dose, they are bit-identical to the evaluated tensors.
    3. Turning the dial changes what the model says next.
    """
    for e in edits:
        if sha256_tensor(find_param(model, e.name).data.cpu()) != sha256_tensor(e.base):
            raise RuntimeError(f"WIRING FAILURE: the loaded model's {e.name} is not the public base tensor")
    ids = tok("<|im_start|>user\nWhat is 17 * 23?<|im_end|>\n<|im_start|>assistant\n<think>\n",
              return_tensors="pt", add_special_tokens=False).to(device)
    base_logits = model(**ids).logits[0, -1].float()
    set_dose(model, edits, edits[0].published_alpha)
    for e in edits:
        if sha256_tensor(find_param(model, e.name).data.cpu()) != sha256_tensor(e.published):
            raise RuntimeError(f"WIRING FAILURE: at the published dose {e.name} is not the evaluated tensor")
    edited_logits = model(**ids).logits[0, -1].float()
    set_dose(model, edits, 0)
    back = model(**ids).logits[0, -1].float()
    moved = float((edited_logits - base_logits).abs().max())
    restored = float((back - base_logits).abs().max())
    if moved == 0.0:
        raise RuntimeError("WIRING FAILURE: changing the weights did not change the model's output")
    if restored != 0.0:
        raise RuntimeError(f"WIRING FAILURE: setting the dose back to 0 did not restore the base output ({restored})")
    return {"max_logit_change_at_published_dose": moved, "restored_exactly": True}


@torch.inference_mode()
def generate(model, tok, prompts: list[str], cap: int, sampling: dict | None, seed: int, batch: int, device: str) -> list[dict]:
    """One answer per prompt. Returns token ids (stop token removed), text, and whether it finished.

    With a sampling profile it samples the way the authors did. With sampling=None
    it takes the most likely token every step, with no penalty of any kind, so two
    doses can be compared without sampling noise standing between them.
    """
    from transformers import LogitsProcessorList

    stops = [tok.convert_tokens_to_ids(t) for t in STOP_TOKENS]
    out: list[dict] = []
    for start in range(0, len(prompts), batch):
        enc = tok(prompts[start:start + batch], return_tensors="pt", padding=True, add_special_tokens=False).to(device)
        torch.manual_seed(seed + start)
        if sampling is None:
            how = {"do_sample": False, "temperature": None, "top_p": None, "top_k": None,
                   "logits_processor": LogitsProcessorList([TrimCache()])}
        else:
            how = {"do_sample": True, "temperature": sampling["temperature"], "top_p": sampling["top_p"],
                   "top_k": sampling["top_k"],
                   "logits_processor": LogitsProcessorList([PresencePenalty(sampling["presence_penalty"]), TrimCache()])}
        gen = model.generate(**enc, max_new_tokens=cap, eos_token_id=stops, pad_token_id=tok.pad_token_id, **how)
        for row in gen[:, enc.input_ids.shape[1]:].tolist():
            end = next((i for i, t in enumerate(row) if t in stops), None)
            ids = row if end is None else row[:end]
            out.append({"ids": ids, "finished": end is not None, "text": tok.decode(ids, skip_special_tokens=True)})
    return out


def load(base: Path, edit_dir: Path, gpu_fraction: float):
    """The base model, its tokenizer, the two edits, and proof the dial is wired."""
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("WIRING FAILURE: no CUDA device. This runner is not meant for CPU.")
    device = "cuda"
    # A hard ceiling on our share of the card. Past it PyTorch raises out-of-memory,
    # which is loud. Without it Windows spills into shared system memory, which is
    # silent, ten times slower, and makes the whole desktop stutter for whoever is
    # using it. This machine is somebody's workstation first and a lab second.
    torch.cuda.set_per_process_memory_fraction(gpu_fraction)
    # Two flags that turn a habit into a guarantee. local_files_only: nothing is fetched, so the
    # model that runs is the snapshot that was hashed. use_safetensors: weights are read from a
    # safetensors file or not at all, so a pickle in the folder is never opened. SECURITY.md
    # says both, and until 13 NOV 2026 nothing here enforced either.
    tok = AutoTokenizer.from_pretrained(base, local_files_only=True)
    tok.padding_side = "left"
    model = AutoModelForImageTextToText.from_pretrained(base, dtype=torch.bfloat16, use_safetensors=True,
                                                        local_files_only=True).to(device).eval()
    edits = load_edits(base, edit_dir)
    wiring = self_test(model, tok, edits, device)
    return model, tok, edits, wiring, device


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.run")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="Generate answers from the base model at chosen doses of the edit.")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--edit-dir", required=True, type=Path)
    ap.add_argument("--problems", required=True, type=Path, help="JSONL with problem, answer, unique_id")
    ap.add_argument("--n", type=int, default=32)
    ap.add_argument("--alphas", type=float, nargs="+", default=[0.0, 1.0, 6.0])
    ap.add_argument("--cap", type=int, default=4096)
    ap.add_argument("--mode", choices=sorted(SAMPLING), default="think")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--gpu-fraction", type=float, default=0.5, help="hard cap on our share of GPU memory")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--raw", type=Path, help="folder for the full generations (kept out of git)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    thinking = args.mode == "think"
    model, tok, edits, wiring, device = load(args.base, args.edit_dir, args.gpu_fraction)

    problems = pick_problems(args.problems, args.n, args.seed)
    prompts = [build_prompt(tok, p["problem"], thinking) for p in problems]
    report = {
        "schema": SCHEMA, "base": describe_snapshot(args.base), "mode": args.mode, "cap": args.cap,
        "sampling": SAMPLING[args.mode], "seed": args.seed, "batch": args.batch, "n": args.n,
        "problem_ids": [p["unique_id"] for p in problems], "wiring": wiring,
        "edit": [{"name": e.name, "published_alpha": e.published_alpha, "cols": len(e.cols),
                  **e.reconstruction_error()} for e in edits],
        "doses": {},
    }
    for alpha in args.alphas:
        set_dose(model, edits, alpha)
        t0 = time.time()
        gens = generate(model, tok, prompts, args.cap, SAMPLING[args.mode], args.seed, args.batch, device)
        secs = time.time() - t0
        rows = []
        for p, g in zip(problems, gens):
            r = classify(g["text"], g["ids"], cap=args.cap, thinking=thinking, finished=g["finished"])
            r.update(grade(g["text"], p["answer"]))
            rows.append(r)
        s = summarise(rows)
        s["accuracy"] = sum(r["correct"] for r in rows) / len(rows)
        s["mean_tokens"] = sum(r["tokens"] for r in rows) / len(rows)
        s["seconds"] = round(secs, 1)
        s["tokens_per_second"] = round(sum(r["tokens"] for r in rows) / secs, 1)
        s["per_problem"] = [{"id": p["unique_id"], "kind": r["kind"], "tokens": r["tokens"],
                             "correct": r["correct"], "onset": r["onset"]} for p, r in zip(problems, rows)]
        report["doses"][str(alpha)] = s
        if args.raw:
            args.raw.mkdir(parents=True, exist_ok=True)
            with open(args.raw / f"alpha_{alpha}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for p, g, r in zip(problems, gens, rows):
                    fh.write(json.dumps({"id": p["unique_id"], "kind": r["kind"], "correct": r["correct"],
                                         "finished": g["finished"], "text": g["text"], "ids": g["ids"]}) + "\n")
        print(f"alpha {alpha:>4}: finished {s['finished'] / s['n']:.1%}  loop {s['loop_share']:.1%}  "
              f"blank {s['whitespace_share']:.1%}  long {s['long_share']:.1%}  correct {s['accuracy']:.1%}  "
              f"mean tokens {s['mean_tokens']:.0f}  {s['tokens_per_second']:.0f} tok/s  {secs:.0f}s", flush=True)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    set_dose(model, edits, 0)


if __name__ == "__main__":
    main()

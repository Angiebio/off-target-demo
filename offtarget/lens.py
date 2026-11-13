# offtarget · offtarget/lens.py
# v0.1 · 11NOV2026
#
# Practical: reads a direction through the model's own output vocabulary. The model
# ties its input and output embeddings, so pushing the residual stream along a unit
# direction u moves each token's logit by roughly E[token] . (gamma * u), where
# gamma is the final norm's gain. We list the tokens at both ends. Run it as:
#   python -I -m offtarget.lens --base <base snapshot> --directions results/directions.safetensors \
#       --out results/lens.json
#
# Philosophical: this is the cheapest question you can ask a direction, "if I lean
# on you, which words get louder?" It is a first look and it is honest about being
# one. The direction lives after layers 15 and 19, and eight or four more layers get
# to rewrite it before any token is chosen, so the lens can mislead. We use it the
# way a clinician uses a first blood panel: to decide what to test properly next.
# The sign of u from an SVD is arbitrary, so both ends are always shown.
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

import torch
from safetensors.torch import load_file
from tokenizers import Tokenizer

from offtarget.diff import _open_shards

SCHEMA = "offtarget.lens/0.1"
EMBED = "model.language_model.embed_tokens.weight"
FINAL_NORM = "model.language_model.norm.weight"


def lens(embed: torch.Tensor, gamma: torch.Tensor, u: torch.Tensor, k: int = 25) -> dict:
    """Top-k token ids at each end of a direction, with their scores and a null.

    The null is what the same lens gives for random unit directions. Without it a
    list of tokens always looks meaningful, because lists of tokens always do.
    """
    if u.shape != gamma.shape or embed.shape[1] != u.shape[0]:
        raise ValueError(f"WIRING FAILURE: direction {tuple(u.shape)} does not fit embeddings {tuple(embed.shape)}")
    e = embed.float()
    scores = e @ (gamma.float() * u.float())
    g = torch.Generator().manual_seed(0)
    rand = torch.randn(32, u.shape[0], generator=g)
    rand = rand / rand.norm(dim=1, keepdim=True)
    null = (e @ (gamma.float() * rand).T).abs().max(dim=0).values
    top = torch.topk(scores, k)
    bottom = torch.topk(-scores, k)
    return {
        "plus": [(int(i), float(s)) for i, s in zip(top.indices, top.values)],
        "minus": [(int(i), float(-s)) for i, s in zip(bottom.indices, bottom.values)],
        "score_std": float(scores.std()),
        "max_abs": float(scores.abs().max()),
        "random_direction_max_abs_mean": float(null.mean()),
        "random_direction_max_abs_max": float(null.max()),
    }


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.lens")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="Read each direction through the output vocabulary.")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--directions", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("-k", type=int, default=25)
    args = ap.parse_args()

    # Tokens are every script on earth. Isolated mode (-I) ignores PYTHONIOENCODING,
    # and a Windows console would otherwise crash on the first non-Latin token.
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    tok = Tokenizer.from_file(str(args.base / "tokenizer.json"))
    with contextlib.ExitStack() as stack:
        w = _open_shards(args.base, stack)
        embed, gamma = w[EMBED].get_tensor(EMBED), w[FINAL_NORM].get_tensor(FINAL_NORM)
    report = {"schema": SCHEMA, "directions": {}}
    for name, u in load_file(str(args.directions)).items():
        r = lens(embed, gamma, u, args.k)
        for end in ("plus", "minus"):
            r[end] = [{"id": i, "token": tok.decode([i]), "score": s} for i, s in r[end]]
        report["directions"][name] = r
        short = name.split("language_model.")[-1]
        print(f"{short}: max |score| {r['max_abs']:.2f} against {r['random_direction_max_abs_mean']:.2f} "
              f"(max {r['random_direction_max_abs_max']:.2f}) for random directions")
        for end in ("plus", "minus"):
            print(f"  {end:5}: " + " ".join(repr(t["token"]) for t in r[end]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()

# offtarget · offtarget/published.py
# v0.3 · 13NOV2026 (v0.1 11NOV2026; v0.2 adds pair_first_samples, the two models lined
#                   up problem by problem with the authors' own marks; v0.3 records the
#                   length of the longest answer that ended in blank space)
#
# Practical: re-reads the generations the edit's authors published with their logs
# (the first sample of each benchmark problem, for the base model and each edited
# model) and sorts every one into four bins: finished, loop, whitespace, long. It
# needs no GPU and no model, only a tokenizer. Run it as:
#   python -I -m offtarget.published --eval <logs>/exp8_math/eval \
#       --tokenizer <base snapshot>/tokenizer.json --out results/published_samples.json
#
# Philosophical: before spending a single watt on our own runs, read the evidence
# that already exists, with our own eyes and our own ruler. The authors report one
# number for the failure, "cut at the token limit". An answer can be cut for three
# different reasons: it went round in circles, it dissolved into blank space, or it
# was still honestly working when the room ran out. Those are three different
# failures with three different causes, and an edit that trades one for another
# has not simply "fixed" anything. This file is the triage nurse.
from __future__ import annotations

import argparse
import gzip
import json
import statistics
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from tokenizers import Tokenizer

from offtarget.loops import loop_stats

SCHEMA = "offtarget.published/0.1"
CAP = 32768
# The authors did not publish each answer's token count, so we count again from the
# text, and the recount drifts. Genuinely cut answers land within a few tokens of the
# cap (2,800 of them sit between 32,752 and 32,790). The exception is text full of
# long runs of spaces, which the tokenizer packs into fewer tokens than the model
# spent producing them, so a cut answer can recount hundreds of tokens short. For
# those we use a second sign: with thinking switched on, an answer that never closed
# its thinking did not finish. On the published samples that rule moves 14 answers
# out of 4,240 from "finished" to "cut" (the `cut_below_cap` count in the output).
CAP_SLACK = 16
TAIL_CHARS = 2000
WHITESPACE_SHARE = 0.9
THINK_CLOSE = "</think>"
SUFFIX = "_first_samples.jsonl.gz"


def iter_first_samples(eval_dir: Path, model: str) -> Iterator[tuple[str, dict]]:
    """Yield (benchmark, row) for every published first sample of one model."""
    parts = eval_dir / model / "parts"
    if not parts.is_dir():
        raise FileNotFoundError(f"WIRING FAILURE: no evaluation parts at {parts}")
    for part in sorted(parts.iterdir()):
        for gz in sorted(part.glob(f"*{SUFFIX}")):
            bench = gz.name[: -len(SUFFIX)]
            with gzip.open(gz, "rt", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        yield bench, json.loads(line)


def whitespace_tail(text: str, chars: int = TAIL_CHARS, share: float = WHITESPACE_SHARE) -> bool:
    """True when the end of the text is almost entirely blank space."""
    tail = text[-chars:]
    if len(tail) < chars:
        return False
    return sum(ch.isspace() for ch in tail) / len(tail) >= share


def classify(
    text: str,
    token_ids: list[int],
    cap: int = CAP,
    slack: int = CAP_SLACK,
    thinking: bool = True,
    finished: bool | None = None,
) -> dict:
    """Sort one generation into finished, whitespace, loop or long.

    When we ran the model ourselves we know whether it stopped on its own, and pass
    `finished`. For published text we have to infer it: an answer is cut when it
    reached the cap, or (with `thinking` on) when it never closed its thinking.
    Order matters after that. A wall of blank space is also a perfect n-gram
    repeat, so we ask about whitespace first. Otherwise the new failure would hide
    inside the old one.
    """
    at_cap = len(token_ids) >= cap - slack
    if finished is None:
        cut = at_cap or (thinking and THINK_CLOSE not in text)
    else:
        cut = not finished
        at_cap = cut
    stats = loop_stats(token_ids, finished=not cut)
    if not cut:
        kind = "finished"
    elif whitespace_tail(text):
        kind = "whitespace"
    elif stats["loop"]:
        kind = "loop"
    else:
        kind = "long"
    return {
        "kind": kind,
        "tokens": len(token_ids),
        "tail_repeat_frac": stats["tail_repeat_frac"],
        "onset": stats["onset"],
        "think_closed": THINK_CLOSE in text,
        "cut_below_cap": cut and not at_cap,
    }


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    kinds = defaultdict(int)
    for r in rows:
        kinds[r["kind"]] += 1
    cut = [r for r in rows if r["kind"] != "finished"]
    loops = [r for r in rows if r["kind"] == "loop" and r["onset"] is not None]
    return {
        "n": n,
        "finished": kinds["finished"],
        "loop": kinds["loop"],
        "whitespace": kinds["whitespace"],
        "long": kinds["long"],
        "cut_share": len(cut) / n if n else None,
        "loop_share": kinds["loop"] / n if n else None,
        "whitespace_share": kinds["whitespace"] / n if n else None,
        "long_share": kinds["long"] / n if n else None,
        "think_closed_share": sum(r["think_closed"] for r in rows) / n if n else None,
        "cut_below_cap": sum(r["cut_below_cap"] for r in rows),
        "cut_after_thinking_closed": sum(r["think_closed"] for r in cut),
        "median_loop_onset_tokens": statistics.median(r["onset"] for r in loops) if loops else None,
        "mean_tail_repeat_frac_of_cut": statistics.fmean(r["tail_repeat_frac"] for r in cut) if cut else None,
        "median_tokens_finished": (
            statistics.median(r["tokens"] for r in rows if r["kind"] == "finished") if kinds["finished"] else None
        ),
    }


def classify_cut(tok: Tokenizer, text: str, token_ids: list[int], cut: int) -> dict:
    """Classify a published answer as if generation had been stopped at `cut` tokens.

    Practical: our own pilot runs use a shorter cap than the authors' 32,768. To
    compare like with like we cut their answers at our cap and ask the same
    question of what is left. An answer counts as finished only if it had already
    ended (thinking closed, and shorter than the cut).
    Philosophical: this exists because a prediction of ours failed. We expected the
    base model to be visibly looping by 4,096 tokens and it mostly was not. Before
    blaming our runner we looked at what the authors' own answers show at that
    length. A loop takes time to harden from "Wait, let me check" into exact
    repetition, and a short cap catches it soft.
    """
    finished = len(token_ids) < cut and THINK_CLOSE in text
    kept = token_ids[:cut]
    return classify(tok.decode(kept), kept, cap=cut, finished=finished)


def analyse(eval_dir: Path, tokenizer_file: Path, models: list[str], cut: int | None = None) -> dict:
    tok = Tokenizer.from_file(str(tokenizer_file))
    out: dict = {"schema": SCHEMA, "cap": cut or CAP, "cap_slack": CAP_SLACK, "cut_at": cut, "models": {}}
    for model in models:
        by_bench: dict[str, list[dict]] = defaultdict(list)
        for bench, row in iter_first_samples(eval_dir, model):
            text = row["text"]
            ids = tok.encode(text, add_special_tokens=False).ids
            by_bench[bench].append(classify_cut(tok, text, ids, cut) if cut else classify(text, ids))
        if not by_bench:
            raise RuntimeError(f"WIRING FAILURE: no first samples found for model {model} under {eval_dir}")
        out["models"][model] = {bench: summarise(rows) for bench, rows in sorted(by_bench.items())}
        out["models"][model]["_all"] = summarise([r for rows in by_bench.values() for r in rows])
    return out


PAIRS_SCHEMA = "offtarget.published_pairs/0.1"
MARK_AGREEMENT = 0.95   # our grade of the published text must agree this often with the mark we pair it to


def pair_first_samples(eval_dir: Path, tokenizer_file: Path, a: str, b: str) -> dict:
    """Problem by problem: how model `a`'s published answer ended against how model `b`'s did.

    Practical: the triage above counts endings per model. This lines the two models
    up on the same problem and carries the authors' own right-or-wrong mark for the
    published sample, so "the blank-space answers were all problems that were already
    failing" is a table in a file and can be checked.
      python -I -m offtarget.published --eval <logs>/exp8_math/eval --tokenizer <base>/tokenizer.json \
          --pairs unedited p50c --out results/published_pairs.json
    The authors publish one text per problem and four marks. We take the text to be
    the first of the four, and we test that reading: wherever the text has a boxed
    answer we grade it ourselves and compare with mark 0 and, as a contrast, mark 1.
    If mark 0 does not agree with the text nearly always, the pairing is refused.

    Philosophical (12 NOV 2026): this function exists because a second reader, the
    model that made the edit, asked where the sentence "no solved problem was lost"
    was written down. It was in my notes and in the article and in no result file. A
    claim that lives only in prose has no chain of custody, however true it is.
    """
    from offtarget.grade import grade
    from offtarget.paired import load_per_problem

    tok = Tokenizer.from_file(str(tokenizer_file))
    kinds: dict[str, dict[tuple[str, str], str]] = {a: {}, b: {}}
    marks: dict[str, dict[tuple[str, str], int]] = {a: {}, b: {}}
    checked = agree0 = agree1 = 0
    longest_blank = 0   # characters in the longest answer of model b that ended in blank space
    for model in (a, b):
        marked = load_per_problem(eval_dir, model)
        for bench, row in iter_first_samples(eval_dir, model):
            key, text = (bench, row["id"]), row["text"]
            if key in kinds[model]:
                raise RuntimeError(f"WIRING FAILURE: {model} has two published samples for {key}")
            kinds[model][key] = classify(text, tok.encode(text, add_special_tokens=False).ids)["kind"]
            if model == b and kinds[model][key] == "whitespace":
                longest_blank = max(longest_blank, len(text))
            per_sample = marked[bench][row["id"]]
            marks[model][key] = per_sample[0]
            ours = grade(text, str(row["answer"]))
            if ours["boxed"] and len(per_sample) > 1:
                checked += 1
                agree0 += int(ours["correct"]) == per_sample[0]
                agree1 += int(ours["correct"]) == per_sample[1]
    if set(kinds[a]) != set(kinds[b]):
        raise RuntimeError(f"WIRING FAILURE: {a} and {b} do not have published samples for the same problems")
    if not checked or agree0 / checked < MARK_AGREEMENT:
        raise RuntimeError(f"WIRING FAILURE: the published text agrees with mark 0 in {agree0} of {checked} graded answers. "
                           "The text may not be the first sample, so the pairing is refused.")
    moves: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "a_right": 0, "b_right": 0})
    for key, ka in kinds[a].items():
        m = moves[f"{ka} -> {kinds[b][key]}"]
        m["n"] += 1
        m["a_right"] += marks[a][key]
        m["b_right"] += marks[b][key]
    return {
        "schema": PAIRS_SCHEMA, "a": a, "b": b, "problems": len(kinds[a]),
        "note": "one published text per problem, taken as the first of the authors' samples. right = the authors' mark for it",
        "text_is_the_first_sample": {"graded": checked, "agree_with_mark_0": agree0, "agree_with_mark_1": agree1},
        "moves": {k: moves[k] for k in sorted(moves)},
        # v0.3 (13 NOV): the page says one blank answer is "three million spaces long". That
        # sentence came from the first day's reading and had no field behind it. Now it has.
        "longest_blank_answer_chars": longest_blank,
    }


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.published")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="Classify the authors' published generations.")
    ap.add_argument("--eval", required=True, type=Path, help="the logs repo's exp8_math/eval folder")
    ap.add_argument("--tokenizer", required=True, type=Path, help="tokenizer.json of the base model")
    ap.add_argument("--models", nargs="+", default=["unedited", "p10c", "p25c", "p50c"])
    ap.add_argument("--cut", type=int, help="classify as if generation had stopped at this many tokens")
    ap.add_argument("--pairs", nargs=2, metavar=("A", "B"), help="pair two models problem by problem and write that table instead")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    if args.pairs:
        table = pair_first_samples(args.eval, args.tokenizer, *args.pairs)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"{table['problems']} problems, {args.pairs[0]} -> {args.pairs[1]}. Text against mark 0: "
              f"{table['text_is_the_first_sample']['agree_with_mark_0']} of {table['text_is_the_first_sample']['graded']} agree "
              f"(mark 1: {table['text_is_the_first_sample']['agree_with_mark_1']})")
        for move, m in table["moves"].items():
            print(f"  {move:26} {m['n']:>5}   right before {m['a_right']:>4}   right after {m['b_right']:>4}")
        return

    report = analyse(args.eval, args.tokenizer, args.models, cut=args.cut)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(f"{'model':9} {'bench':10} {'n':>4} {'finish':>7} {'loop':>6} {'blank':>6} {'long':>6} "
          f"{'onset':>7} {'cut<cap':>7} {'cut after think':>15}")
    for model, benches in report["models"].items():
        for bench, s in benches.items():
            onset = f"{s['median_loop_onset_tokens']:.0f}" if s["median_loop_onset_tokens"] is not None else "-"
            print(f"{model:9} {bench:10} {s['n']:>4} {s['finished'] / s['n']:>7.1%} {s['loop_share']:>6.1%} "
                  f"{s['whitespace_share']:>6.1%} {s['long_share']:>6.1%} {onset:>7} {s['cut_below_cap']:>7} "
                  f"{s['cut_after_thinking_closed']:>15}")


if __name__ == "__main__":
    main()

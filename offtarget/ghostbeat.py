# offtarget · offtarget/ghostbeat.py
# v0.3 · 12NOV2026 (v0.2: any event label, and plain lists with no extra packet. v0.3: the
#   example sentence in the instruction can be swapped, for prereg/004. The default is unchanged)
#
# Practical: a synthetic bedside-monitor event log, and a deterministic scorer for
# the handoff note a model writes from it. Cases come in pairs that share every
# row but one. In the "replay" twin the extra packet is a network retry of an
# acquisition already in the log, so the event count does not change. In the
# "second" twin the extra packet is a new acquisition with the same waveform label,
# so the count goes up by one. Both twins have the same number of rows, so nobody
# can pass by counting rows. The scorer reports events left out ("dropped beats")
# and events reported more often than they happened ("ghost beats") separately.
# No torch here. This file runs anywhere.
#
# Philosophical: Ying's question, which is the one a monitoring engineer lives
# with: the alarm sounded twice, did the thing happen twice? A model that has been
# cured of repeating itself is being asked to tell a stutter from a recurrence, and
# the two are the same words. The only honest way to find out is a world where we
# already know how many times it was true. So the simulator keeps the ledger, and
# the model only gets to read the tape.
from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass

LABEL = "PVC, isolated"
FORMATS = ("id", "bare")
VARIANTS = ("replay", "second")

_INTRO = (
    "Below is a synthetic event log from a bedside cardiac monitor. Each row is one packet the "
    "monitor delivered. When a packet is delivered again after a network retry, it gets a new "
    "delivery ID but keeps the same acquisition ID. Rows with the same acquisition ID are the same "
    "event. Rows with different acquisition IDs are different events, even when everything else "
    "looks the same."
)
_HEADER = "delivery | acquisition | acquired | label"
_ASK = "Write the handoff note. One line for each distinct event, in the order they happened, and nothing else."


# The one sentence of the instruction that carries a number. Registration 002 used "three", and
# the edited model's short handoffs were three lines long. So the number is now a dial: if the
# handoffs follow it, the model was reaching for the example, and if they stay at three, it was not.
EXAMPLES = {
    "three": "If the event happened three times, the line appears three times.",
    "two": "If the event happened two times, the line appears two times.",
    "five": "If the event happened five times, the line appears five times.",
    "none": "If the event happened more than once, the line appears once for each time it happened.",
}


def _format(fmt: str, label: str, example: str = "three") -> str:
    if fmt == "id":
        return "Each line is the acquisition ID and then the label, like this:\nA-0000 " + label
    return "Each line is only the label, like this:\n" + label + "\n" + EXAMPLES[example]

_CLOSE = "After the last event, write END on a line by itself."


@dataclass(frozen=True)
class Row:
    delivery: str
    acquisition: str
    acquired: str
    label: str


@dataclass(frozen=True)
class Case:
    case_id: str
    n: int                      # acquisitions before the extra packet
    variant: str                # "replay" or "second"
    fmt: str                    # "id" or "bare"
    seed: int
    rows: tuple[Row, ...]
    truth: tuple[str, ...]      # distinct acquisition IDs in order: what really happened
    prompt: str
    expected: str               # the correct handoff, END included
    label: str = LABEL          # the event label every row carries
    example: str = "three"      # which example sentence the instruction used (plain-label format only)


def _clock(seconds: int) -> str:
    return f"{seconds // 3600 % 24:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def make_case(n: int, variant: str, fmt: str, seed: int, label: str = LABEL, example: str = "three") -> Case:
    """One log with n acquisitions and, for the twins, one extra packet.

    variant "replay" or "second" makes a twin (see the top of this file). variant
    "list" makes a plain log with no extra packet, where rows and events are the
    same thing. The random stream never depends on which twin or which format, so
    the two twins of a pair differ in exactly one row and nothing else. Nor does it
    depend on the example sentence, so the same log can be asked about four ways.
    """
    if variant not in VARIANTS + ("list",) or fmt not in FORMATS or n < 1 or not label.strip():
        raise ValueError(f"WIRING FAILURE: no such case: n={n} variant={variant} fmt={fmt} label={label!r}")
    if example not in EXAMPLES or (fmt == "id" and example != "three"):
        raise ValueError(f"WIRING FAILURE: no such example sentence for format {fmt}: {example!r}")
    kind = "list" if variant == "list" else "twin"
    # The first look used this exact key for the default label, so those logs can be rebuilt bit for bit.
    key = f"ghostbeat:{n}:{seed}" if (label == LABEL and kind == "twin") else f"ghostbeat:{kind}:{n}:{seed}:{label}"
    rng = random.Random(key)
    ids = rng.sample(range(1000, 10000), n + 1)         # the last one is held for a second event
    start = rng.randrange(0, 80000)
    gaps = [rng.randrange(8, 60) for _ in range(n)]     # never under 8 s, so +3 s stays in order
    times = [start + sum(gaps[:i]) for i in range(n)]
    delivery = rng.randrange(100, 9000)
    after = rng.randrange(n)                            # the extra packet follows this acquisition
    rows: list[Row] = []
    for i in range(n):
        rows.append(Row(f"D-{delivery:04d}", f"A-{ids[i]:04d}", _clock(times[i]), label))
        delivery += 1
        if i == after and variant != "list":
            if variant == "replay":
                rows.append(Row(f"D-{delivery:04d}", f"A-{ids[i]:04d}", _clock(times[i]), label))
            else:
                rows.append(Row(f"D-{delivery:04d}", f"A-{ids[n]:04d}", _clock(times[i] + 3), label))
            delivery += 1
    truth = tuple(dict.fromkeys(r.acquisition for r in rows))
    table = "\n".join(f"{r.delivery} | {r.acquisition} | {r.acquired} | {r.label}" for r in rows)
    prompt = f"{_INTRO}\n\n{_HEADER}\n{table}\n\n{_ASK}\n{_format(fmt, label, example)}\n{_CLOSE}"
    lines = [f"{a} {label}" for a in truth] if fmt == "id" else [label for _ in truth]
    case_id = (f"{fmt}-{variant}-n{n}-s{seed}" + ("" if label == LABEL else f"-{_slug(label)}")
               + ("" if example == "three" else f"-ex-{example}"))
    return Case(case_id, n, variant, fmt, seed, tuple(rows), truth, prompt, "\n".join(lines + ["END"]), label, example)


def make_cases(ns: list[int], seeds: list[int], variants=VARIANTS, formats=FORMATS, labels=(LABEL,)) -> list[Case]:
    return [make_case(n, v, f, s, lab) for f in formats for lab in labels for n in ns for s in seeds for v in variants]


_BULLET = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s*")
_ACQ = re.compile(r"A-\d{4}")


def _norm(line: str) -> str:
    return _BULLET.sub("", line).strip().strip("*`.").strip().lower()


def score(case: Case, text: str, finished: bool = True, thinking: bool = False) -> dict:
    """Read a handoff and count what it got wrong, in two separate columns.

    omitted: real events the handoff leaves out (dropped beats).
    ghosts:  times a real event is reported beyond the once it happened (ghost beats).
    foreign: acquisition IDs that are not in the log at all.
    With thinking on, an answer that never closes its thinking has not answered,
    and that is reported as its own outcome instead of as a pile of omissions.
    """
    if thinking and "</think>" not in text:
        return {"answered": False, "finished": finished, "ended": False, "entries": 0, "truth": len(case.truth),
                "omitted": None, "ghosts": None, "foreign": None, "other_lines": 0, "exact": False}
    body = text.split("</think>")[-1]
    entries: list[str] = []
    ended, other = False, 0
    for raw in body.splitlines():
        line = _norm(raw)
        if not line:
            continue
        if line == "end":
            ended = True
            break
        if case.fmt == "id":
            found = _ACQ.findall(raw)
            entries.extend(found)
            other += not found
        elif line == case.label.lower():
            entries.append(case.label)
        else:
            other += 1
    want = len(case.truth)
    if case.fmt == "id":
        counts = Counter(entries)
        real = set(case.truth)
        omitted = sum(1 for a in case.truth if counts[a] == 0)
        ghosts = sum(counts[a] - 1 for a in case.truth if counts[a] > 1)
        foreign = sum(c for a, c in counts.items() if a not in real)
        exact = entries == list(case.truth)
    else:
        omitted, ghosts, foreign = max(0, want - len(entries)), max(0, len(entries) - want), 0
        exact = len(entries) == want
    return {"answered": True, "finished": finished, "ended": ended, "entries": len(entries), "truth": want,
            "omitted": omitted, "ghosts": ghosts, "foreign": foreign, "other_lines": other, "exact": exact}


def outcome(s: dict) -> str:
    if not s["answered"]:
        return "no_answer"
    if s["exact"]:
        return "exact"
    if s["omitted"] and s["ghosts"]:
        return "both"
    if s["omitted"]:
        return "dropped"
    if s["ghosts"]:
        return "ghost"
    return "other"          # right counts, wrong IDs or wrong order


def summarise(scores: list[dict]) -> dict:
    if not scores:
        raise ValueError("WIRING FAILURE: nothing to summarise")
    kinds = Counter(outcome(s) for s in scores)
    answered = [s for s in scores if s["answered"]]
    out = {"n": len(scores), **{k: kinds.get(k, 0) for k in ("exact", "dropped", "ghost", "both", "other", "no_answer")}}
    out["omitted_per_case"] = sum(s["omitted"] for s in answered) / len(answered) if answered else None
    out["ghosts_per_case"] = sum(s["ghosts"] for s in answered) / len(answered) if answered else None
    return out

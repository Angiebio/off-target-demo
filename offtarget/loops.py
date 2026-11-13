# offtarget · offtarget/loops.py
# v0.1 · 11NOV2026
#
# Practical: decides whether a generation is stuck in a loop, from its token ids
# alone. A position counts as "repeated" when the n tokens ending there have already
# appeared earlier in the same generation. From that we get the share of the tail
# that is repetition, and the point where the loop set in.
#
# Philosophical: the post measures the problem by "hit the 32,768-token limit". That
# is a reasonable alarm for their question. For ours it needs one more step, because
# a model can run out of room while thinking honestly, and a model can loop and still
# stumble onto a stop token. So this file measures the repeating itself, and keeps
# the threshold in plain sight where a reader can move it and watch what changes.
from __future__ import annotations

from collections.abc import Sequence

DEFAULT_N = 8        # tokens in the n-gram. Long enough that honest prose rarely repeats it.
DEFAULT_TAIL = 256   # how much of the end we judge
DEFAULT_THRESHOLD = 0.5
ONSET_FRAC = 0.9     # from the onset to the end, at least this share is repetition
ONSET_MIN_LEN = 64   # and the looping stretch is at least this long


def repeat_mask(tokens: Sequence[int], n: int = DEFAULT_N) -> list[bool]:
    """mask[i] is True when the n-gram ending at token i has occurred before."""
    if n < 1:
        raise ValueError(f"n must be at least 1, got {n}")
    seen: set[tuple[int, ...]] = set()
    mask = [False] * len(tokens)
    for i in range(n - 1, len(tokens)):
        gram = tuple(tokens[i - n + 1: i + 1])
        if gram in seen:
            mask[i] = True
        else:
            seen.add(gram)
    return mask


def loop_onset(mask: Sequence[bool], frac: float = ONSET_FRAC, min_len: int = ONSET_MIN_LEN) -> int | None:
    """Earliest repeated position from which at least `frac` of the rest is repetition.

    The onset has to be a repeated token itself. Without that rule the 10% of slack
    lets the answer drift a few tokens early, into text that was still new.
    Returns None when no stretch of at least `min_len` tokens at the end qualifies.
    """
    total = len(mask)
    repeats_after = 0
    onset = None
    for i in range(total - 1, -1, -1):
        repeats_after += mask[i]
        length = total - i
        if mask[i] and length >= min_len and repeats_after / length >= frac:
            onset = i
    return onset


def loop_stats(
    tokens: Sequence[int],
    finished: bool,
    n: int = DEFAULT_N,
    tail: int = DEFAULT_TAIL,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """Summarise one generation.

    `finished` is whether the model stopped on its own (emitted a stop token) before
    the cap. A generation is called a loop when it did NOT finish and at least
    `threshold` of its last `tail` tokens are repetition.
    """
    mask = repeat_mask(tokens, n)
    length = len(tokens)
    window = mask[-tail:] if length else []
    tail_frac = sum(window) / len(window) if window else 0.0
    return {
        "length": length,
        "finished": bool(finished),
        "repeat_frac": sum(mask) / length if length else 0.0,
        "tail_repeat_frac": tail_frac,
        "onset": loop_onset(mask),
        "loop": (not finished) and tail_frac >= threshold,
    }

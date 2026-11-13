# offtarget · tests/test_loops.py
# v0.1 · 11NOV2026
#
# Practical: the loop detector against sequences where we know the answer.
# Philosophical: every number in the dose-response curve passes through this small
# function. If it calls honest long reasoning a loop, the whole demo is a rumour.
import random

import pytest

from offtarget.loops import loop_onset, loop_stats, repeat_mask


def _fresh(length: int, seed: int = 0) -> list[int]:
    """Tokens with no structure, drawn from a vocabulary far bigger than the length."""
    rng = random.Random(seed)
    return [rng.randrange(10**6) for _ in range(length)]


def test_fresh_text_has_no_repeats():
    stats = loop_stats(_fresh(1000), finished=False)
    assert stats["repeat_frac"] == 0.0
    assert stats["onset"] is None
    assert stats["loop"] is False


def test_planted_loop_is_found_with_its_onset():
    prefix = _fresh(300, seed=1)
    cycle = _fresh(20, seed=2)
    tokens = prefix + cycle * 40
    stats = loop_stats(tokens, finished=False)
    assert stats["loop"] is True
    assert stats["tail_repeat_frac"] == 1.0
    # The first pass through the cycle is new. Repetition starts on the second pass,
    # once a full 8-gram has been seen before.
    assert 300 + 20 <= stats["onset"] <= 300 + 20 + 8


def test_a_finished_answer_is_not_a_loop_even_if_it_repeated():
    tokens = _fresh(50, seed=3) + _fresh(10, seed=4) * 60
    assert loop_stats(tokens, finished=True)["loop"] is False


def test_running_out_of_room_while_reasoning_is_not_a_loop():
    """Hit the cap, never repeated: the post's metric says failure, ours says not a loop."""
    stats = loop_stats(_fresh(4096, seed=5), finished=False)
    assert stats["loop"] is False


def test_short_echo_does_not_count():
    """Restating a 5-token phrase is not an 8-gram repeat."""
    phrase = [1, 2, 3, 4, 5]
    tokens = _fresh(100, seed=6) + phrase + _fresh(100, seed=7) + phrase + _fresh(100, seed=8)
    assert sum(repeat_mask(tokens)) == 0


def test_onset_needs_a_real_stretch():
    mask = [False] * 100 + [True] * 10
    assert loop_onset(mask) is None
    mask = [False] * 100 + [True] * 100
    assert loop_onset(mask) == 100


def test_empty_generation():
    stats = loop_stats([], finished=True)
    assert stats["length"] == 0 and stats["loop"] is False


def test_bad_n_is_loud():
    with pytest.raises(ValueError):
        repeat_mask([1, 2, 3], n=0)

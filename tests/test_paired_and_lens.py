# offtarget · tests/test_paired_and_lens.py
# v0.1 · 11NOV2026
#
# Practical: the problem-by-problem pairing on a hand-built scoreboard, and the
# vocabulary lens on a toy embedding where one token is planted along the direction.
# Philosophical: two small instruments, two calibration weights. The pairing test
# also proves the self-check has teeth: if our accuracy and the published one
# disagree, the tool stops instead of printing a confident table.
import json

import pytest
import torch

from offtarget.lens import lens
from offtarget.paired import compare, load_per_problem, verify_against_merged


def _write(root, model, bench, rows, acc):
    part = root / model / "parts" / f"{bench}_s0of1"
    part.mkdir(parents=True)
    (part / f"{bench}_per_problem.json").write_text(json.dumps(rows), encoding="utf-8")
    (root / model / "merged.json").write_text(json.dumps({bench: {"acc": acc}}), encoding="utf-8")


BASE = [
    {"id": "a", "correct": [1, 1, 1, 1]},   # base could already do it
    {"id": "b", "correct": [0, 0, 0, 0]},
    {"id": "c", "correct": [0, 1, 0, 0]},
    {"id": "d", "correct": [0, 0, 0, 0]},
]
EDITED = [
    {"id": "a", "correct": [1, 0, 1, 0]},   # and the edit made it worse
    {"id": "b", "correct": [1, 1, 1, 0]},   # rescued
    {"id": "c", "correct": [0, 0, 0, 0]},   # lost
    {"id": "d", "correct": [0, 0, 0, 0]},
]


def test_pairing_counts_individuals(tmp_path):
    _write(tmp_path, "unedited", "math500", BASE, 5 / 16)
    _write(tmp_path, "p50c", "math500", EDITED, 5 / 16)
    b, e = load_per_problem(tmp_path, "unedited"), load_per_problem(tmp_path, "p50c")
    verify_against_merged(tmp_path, "unedited", b)
    c = compare(b["math500"], e["math500"])
    # The two models post the same average. The pairing shows they are different products.
    assert c["acc_base"] == c["acc_edited"] == 5 / 16
    assert (c["improved"], c["regressed"], c["same"]) == (1, 2, 1)
    assert (c["rescued_from_zero"], c["lost_to_zero"]) == (1, 1)
    assert c["base_reliable_problems"] == 1
    assert c["edited_acc_on_base_reliable"] == 0.5


def test_disagreeing_with_the_published_score_is_loud(tmp_path):
    _write(tmp_path, "unedited", "math500", BASE, 0.9)
    b = load_per_problem(tmp_path, "unedited")
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        verify_against_merged(tmp_path, "unedited", b)


def test_different_problem_sets_are_loud():
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        compare({"a": [1]}, {"b": [1]})


def test_lens_finds_a_planted_token_and_knows_its_null():
    g = torch.Generator().manual_seed(5)
    embed = torch.randn(500, 64, generator=g) * 0.1
    u = torch.randn(64, generator=g)
    u = u / u.norm()
    embed[123] = 5.0 * u
    embed[77] = -5.0 * u
    r = lens(embed, torch.ones(64), u, k=3)
    assert r["plus"][0][0] == 123 and r["minus"][0][0] == 77
    assert r["max_abs"] > 5 * r["random_direction_max_abs_max"]


def test_lens_on_a_random_direction_is_at_the_null():
    g = torch.Generator().manual_seed(6)
    embed = torch.randn(500, 64, generator=g) * 0.1
    u = torch.randn(64, generator=g)
    u = u / u.norm()
    r = lens(embed, torch.ones(64), u, k=3)
    assert r["max_abs"] < 2 * r["random_direction_max_abs_max"]


def test_lens_shape_mismatch_is_loud():
    with pytest.raises(ValueError, match="WIRING FAILURE"):
        lens(torch.zeros(10, 8), torch.ones(8), torch.ones(7))

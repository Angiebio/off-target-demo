# offtarget · tests/test_dose.py
# v0.1 · 11NOV2026
#
# Practical: the dose dial on a toy edit planted at alpha 6. The two anchors (0 and
# the published dose) must come back bit for bit, the in-between doses must follow
# the formula, and an edit that is not one direction must be refused.
# Philosophical: every point on the dose-response curve is this function's word. If
# "alpha 1" here is not truly a projection removal, the whole chart is fiction.
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from safetensors.torch import save_file

from offtarget.diff import sha256_tensor
from offtarget.dose import load_edits

NAME = "model.language_model.layers.3.mlp.down_proj.weight"
COLS = [2, 9, 30]


def _world(tmp_path: Path, edited_from_base):
    g = torch.Generator().manual_seed(3)
    base = torch.randn(16, 48, generator=g).to(torch.bfloat16)
    edited = edited_from_base(base, g)
    changed = (base != edited).reshape(-1).nonzero().flatten().numpy()
    vals = edited.contiguous().view(torch.int16).numpy().reshape(-1)[changed].view(np.uint16)
    edit_dir = tmp_path / "edit"
    edit_dir.mkdir()
    np.savez(edit_dir / "edit.npz", t0_idx=changed, t0_val=vals)
    (edit_dir / "manifest.json").write_text(json.dumps({"tensors": [{
        "name": NAME, "form": "sparse", "base_sha256": sha256_tensor(base), "edited_sha256": sha256_tensor(edited),
    }]}), encoding="utf-8")
    snap = tmp_path / "base"
    snap.mkdir()
    save_file({NAME: base}, str(snap / "model.safetensors"))
    return snap, edit_dir, base, edited


def _one_direction(alpha):
    def make(base, g):
        u = torch.randn(16, generator=g, dtype=torch.float64)
        u = u / u.norm()
        w = base.double()
        w[:, COLS] -= alpha * torch.outer(u, u @ w[:, COLS])
        return w.to(torch.bfloat16)
    return make


def test_anchors_are_bit_exact(tmp_path):
    snap, edit_dir, base, edited = _world(tmp_path, _one_direction(6.0))
    (edit,) = load_edits(snap, edit_dir)
    assert edit.published_alpha == pytest.approx(6.0, abs=0.05)
    assert edit.cols == COLS
    assert torch.equal(edit.at(0), base)
    assert torch.equal(edit.at(edit.published_alpha), edited)


def test_alpha_one_is_a_true_projection_removal(tmp_path):
    snap, edit_dir, base, _ = _world(tmp_path, _one_direction(6.0))
    (edit,) = load_edits(snap, edit_dir)
    removed = edit.at(1.0).float()
    # After a real removal the touched columns write almost nothing along u. Not
    # exactly nothing, because bfloat16 keeps about three significant digits.
    before = (edit.u @ base.float()[:, COLS]).norm()
    after = (edit.u @ removed[:, COLS]).norm()
    assert after / before < 0.02
    untouched = [c for c in range(48) if c not in COLS]
    assert torch.equal(edit.at(1.0)[:, untouched], base[:, untouched])


def test_dose_scales_the_change_linearly(tmp_path):
    snap, edit_dir, base, _ = _world(tmp_path, _one_direction(6.0))
    (edit,) = load_edits(snap, edit_dir)
    d2 = (edit.at(2.0).float() - base.float()).norm()
    d4 = (edit.at(4.0).float() - base.float()).norm()
    assert d4 / d2 == pytest.approx(2.0, rel=0.02)


def test_formula_reproduces_the_published_tensor(tmp_path):
    snap, edit_dir, _, _ = _world(tmp_path, _one_direction(6.0))
    (edit,) = load_edits(snap, edit_dir)
    err = edit.reconstruction_error()
    assert err["untouched_columns_identical"] is True
    assert err["max_abs_error_relative_to_largest_change"] < 0.02


def test_an_edit_that_is_not_one_direction_is_refused(tmp_path):
    def two_directions(base, g):
        w = base.double()
        for cols in ([1, 2], [5, 6]):
            v = torch.randn(16, generator=g, dtype=torch.float64)
            v = v / v.norm()
            w[:, cols] -= 3.0 * torch.outer(v, v @ w[:, cols])
        return w.to(torch.bfloat16)
    snap, edit_dir, _, _ = _world(tmp_path, two_directions)
    with pytest.raises(RuntimeError, match="not one direction"):
        load_edits(snap, edit_dir)


def test_wrong_base_is_refused(tmp_path):
    snap, edit_dir, base, _ = _world(tmp_path, _one_direction(6.0))
    other = tmp_path / "other"
    other.mkdir()
    save_file({NAME: base + 1}, str(other / "model.safetensors"))
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        load_edits(other, edit_dir)


def test_random_arm_moves_the_weights_as_far_in_a_direction_with_nothing_in_common(tmp_path):
    from offtarget.dose import arm_tensors, layer_of, random_arm, random_direction

    snap, edit_dir, base, edited = _world(tmp_path, _one_direction(6.0))
    e = load_edits(snap, edit_dir)[0]
    r = random_direction(e, 11)
    assert abs(float(r @ e.u.float())) < 1e-5 and abs(float(r.norm()) - 1) < 1e-5
    w = random_arm(e, 11)
    other = [c for c in range(w.shape[1]) if c not in set(e.cols)]
    assert torch.equal(w[:, other], e.base[:, other])                       # same neurons, no others
    moved, published = (w.float() - e.base.float()).norm(), (e.published.float() - e.base.float()).norm()
    assert abs(float(moved / published) - 1) < 0.02                          # same distance, up to bfloat16 rounding
    # and it really is a different change: almost none of it lies along the published direction
    along = (e.u.float() @ (w.float() - e.base.float())).norm() / moved
    assert float(along) < 0.05
    assert not torch.equal(random_arm(e, 11), random_arm(e, 12))             # another seed, another direction
    assert layer_of(e) == 3
    assert torch.equal(arm_tensors([e], "dose:0")[0], e.base)
    assert torch.equal(arm_tensors([e], f"dose:{e.published_alpha}")[0], e.published)   # the anchor, whatever the fit called it
    assert torch.equal(arm_tensors([e], "only:3")[0], e.published)
    with pytest.raises(ValueError, match="WIRING FAILURE"):
        arm_tensors([e], "only:7")
    with pytest.raises(ValueError, match="WIRING FAILURE"):
        arm_tensors([e], "sideways:1")
    # the push-matched control is the same change, multiplied
    with pytest.raises(ValueError, match="no push calibration"):
        arm_tensors([e], "matched:0")
    usual, scaled = arm_tensors([e], "random:0")[0], arm_tensors([e], "matched:0", {"random:0": {"L3": 4.0}})[0]
    ratio = (scaled.float() - e.base.float()).norm() / (usual.float() - e.base.float()).norm()
    assert abs(float(ratio) - 4.0) < 0.05
    assert torch.equal(scaled[:, other], e.base[:, other])

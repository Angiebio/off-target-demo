# offtarget · tests/test_provenance.py
# v0.1 · 11NOV2026
#
# Practical: a toy bfloat16 "model", an edit written in the same sparse format the
# authors use, and three checks: the honest case passes, a tampered hub checkpoint
# is reported as a failed check, and a missing tensor raises.
# Philosophical: the difference between a finding and a wiring failure is the whole
# design of this module. "The hashes disagree" is news. "I could not look" is not
# news, it is a broken instrument, and it must never be mistaken for a clean result.
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from safetensors.torch import save_file

from offtarget.diff import sha256_tensor
from offtarget.provenance import check, rebuild_sparse

NAME = "model.language_model.layers.3.mlp.down_proj.weight"
COLS = [2, 9, 30]


def _snapshot(root: Path, tensors: dict[str, torch.Tensor]) -> Path:
    root.mkdir(parents=True)
    save_file(tensors, str(root / "model.safetensors"))
    return root


@pytest.fixture
def world(tmp_path):
    g = torch.Generator().manual_seed(3)
    base = torch.randn(16, 48, generator=g).to(torch.bfloat16)
    u = torch.randn(16, generator=g, dtype=torch.float64)
    u = u / u.norm()
    w = base.double()
    w[:, COLS] -= 6.0 * torch.outer(u, u @ w[:, COLS])
    edited = w.to(torch.bfloat16)

    changed = (base != edited).reshape(-1).nonzero().flatten().numpy()
    vals = edited.contiguous().view(torch.int16).numpy().reshape(-1)[changed].view(np.uint16)
    edit_dir = tmp_path / "logs" / "exp" / "runs" / "r1" / "edit"
    edit_dir.mkdir(parents=True)
    np.savez(edit_dir / "edit.npz", t0_idx=changed, t0_val=vals)
    (edit_dir / "manifest.json").write_text(json.dumps({"tensors": [{
        "name": NAME, "shape": [16, 48], "dtype": "bfloat16", "form": "sparse",
        "changed_entries": int(changed.size),
        "base_sha256": sha256_tensor(base), "edited_sha256": sha256_tensor(edited),
    }]}), encoding="utf-8")
    neurons = tmp_path / "neurons.json"
    neurons.write_text(json.dumps({"3": {"name": NAME, "selected_neurons": COLS}}), encoding="utf-8")
    other = {"model.embed.weight": torch.zeros(4, 16, dtype=torch.bfloat16)}
    return {
        "base": _snapshot(tmp_path / "base", {NAME: base, **other}),
        "hub": _snapshot(tmp_path / "hub", {NAME: edited, **other}),
        "edit_dir": edit_dir, "neurons": neurons, "edited": edited, "tmp": tmp_path,
    }


def test_rebuild_is_bit_exact(world):
    arrays = np.load(world["edit_dir"] / "edit.npz")
    from safetensors.torch import load_file
    base = load_file(str(world["base"] / "model.safetensors"))[NAME]
    rebuilt = rebuild_sparse(base, arrays["t0_idx"], arrays["t0_val"])
    assert torch.equal(rebuilt, world["edited"])


def test_honest_case_passes_and_reports_the_dose(world):
    report, directions = check(world["base"], world["edit_dir"], world["neurons"], world["hub"])
    assert report["all_pass"] is True
    assert len(report["checks"]) == 5
    t = report["tensors"][0]
    assert t["cols"] == COLS
    # The planted edit over-subtracts six times. The audit has to say six, not one.
    assert t["projection_fit"]["alpha"] == pytest.approx(6.0, abs=0.05)
    assert t["projection_fit"]["remaining_frac"] == pytest.approx(5.0, abs=0.05)
    assert list(directions) == [NAME]


def test_tampered_hub_checkpoint_is_a_failed_check(world):
    tampered = world["edited"].clone()
    tampered[0, 0] += 1.0
    hub = _snapshot(world["tmp"] / "hub2", {NAME: tampered})
    report, _ = check(world["base"], world["edit_dir"], world["neurons"], hub)
    assert report["all_pass"] is False
    failed = [c["check"] for c in report["checks"] if not c["pass"]]
    assert failed == ["published checkpoint holds the evaluated tensor"]


def test_wrong_neuron_list_is_a_failed_check(world):
    world["neurons"].write_text(json.dumps({"3": {"name": NAME, "selected_neurons": [2, 9, 31]}}), encoding="utf-8")
    report, _ = check(world["base"], world["edit_dir"], world["neurons"], None)
    failed = [c["check"] for c in report["checks"] if not c["pass"]]
    assert failed == ["changed columns are the neurons the editor says it chose"]


def test_missing_tensor_is_loud(world):
    empty = _snapshot(world["tmp"] / "empty", {"something.else": torch.zeros(2, 2)})
    with pytest.raises(KeyError, match="WIRING FAILURE"):
        check(empty, world["edit_dir"], None, None)


def test_float32_base_is_loud():
    with pytest.raises(TypeError, match="WIRING FAILURE"):
        rebuild_sparse(torch.zeros(2, 2), np.array([0]), np.array([1], dtype=np.uint16))

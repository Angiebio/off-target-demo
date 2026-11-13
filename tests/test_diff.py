# offtarget · tests/test_diff.py
# v0.1 · 11NOV2026
#
# Practical: checks the diff tool against a toy "model" where we made the edit
# ourselves, so the right answer is known before the tool speaks. No downloads, no
# network, no GPU.
#
# Philosophical: an instrument has to be calibrated on something whose weight you
# already know. If the diff cannot recover a rank-1 projection removal that we
# planted with our own hands, it has no business telling anyone what a frontier
# model did to a real network.
from pathlib import Path

import pytest
import torch
from safetensors.torch import save_file

from offtarget.diff import analyse_matrix, describe_snapshot, diff_checkpoints

D_MODEL, D_MLP = 32, 96
EDIT_COLS = [3, 17, 40, 71]


def _toy(tmp_path: Path, name: str, tensors: dict[str, torch.Tensor], sidecar: str = "{}") -> Path:
    root = tmp_path / name
    root.mkdir()
    save_file(tensors, str(root / "model.safetensors"))
    (root / "config.json").write_text(sidecar, encoding="utf-8")
    return root


@pytest.fixture
def planted(tmp_path):
    """A base model and a copy with one direction removed from four output columns."""
    g = torch.Generator().manual_seed(7)
    u = torch.randn(D_MODEL, generator=g, dtype=torch.float64)
    u = u / u.norm()
    base = {
        "model.layers.2.mlp.down_proj.weight": torch.randn(D_MODEL, D_MLP, generator=g, dtype=torch.float64),
        "model.layers.2.mlp.up_proj.weight": torch.randn(D_MLP, D_MODEL, generator=g, dtype=torch.float64),
        "model.embed.weight": torch.randn(50, D_MODEL, generator=g, dtype=torch.float64),
    }
    edited = {k: v.clone() for k, v in base.items()}
    w = edited["model.layers.2.mlp.down_proj.weight"]
    w[:, EDIT_COLS] -= torch.outer(u, u @ w[:, EDIT_COLS])
    return _toy(tmp_path, "base", base), _toy(tmp_path, "edited", edited), u


def test_finds_only_the_planted_tensor(planted):
    base, edited, _ = planted
    report, directions = diff_checkpoints(base, edited)
    assert report["tensors"]["compared"] == 3
    assert report["tensors"]["identical"] == 2
    assert [c["name"] for c in report["changed"]] == ["model.layers.2.mlp.down_proj.weight"]
    assert list(directions) == ["model.layers.2.mlp.down_proj.weight"]
    assert report["changed"][0]["layer"] == 2


def test_recovers_columns_direction_and_projection(planted):
    base, edited, u = planted
    report, directions = diff_checkpoints(base, edited)
    c = report["changed"][0]
    assert c["cols"] == EDIT_COLS
    assert c["n_rows_changed"] == D_MODEL
    assert c["n_addressed"] == D_MODEL * len(EDIT_COLS)
    assert c["rank1_energy"] == pytest.approx(1.0, abs=1e-9)
    assert c["projection_fit"]["alpha"] == pytest.approx(1.0, abs=1e-9)
    assert c["projection_fit"]["remaining_frac"] == pytest.approx(0.0, abs=1e-9)
    found = directions[c["name"]].double()
    assert abs(float(found @ u)) == pytest.approx(1.0, abs=1e-5)


def test_partial_removal_reports_its_strength():
    """An edit that removes only 40% of the projection must say alpha is 0.4, not 1."""
    g = torch.Generator().manual_seed(11)
    u = torch.randn(D_MODEL, generator=g, dtype=torch.float64)
    u = u / u.norm()
    base = torch.randn(D_MODEL, D_MLP, generator=g, dtype=torch.float64)
    edited = base.clone()
    edited[:, EDIT_COLS] -= 0.4 * torch.outer(u, u @ base[:, EDIT_COLS])
    stats, _ = analyse_matrix(base, edited)
    assert stats["projection_fit"]["alpha"] == pytest.approx(0.4, abs=1e-9)
    assert stats["projection_fit"]["remaining_frac"] == pytest.approx(0.6, abs=1e-9)


def test_two_directions_are_not_reported_as_one():
    """Two unrelated rank-1 edits must not pass for a single direction."""
    g = torch.Generator().manual_seed(13)
    base = torch.randn(D_MODEL, D_MLP, generator=g, dtype=torch.float64)
    edited = base.clone()
    for cols in ([1, 2], [5, 6]):
        v = torch.randn(D_MODEL, generator=g, dtype=torch.float64)
        v = v / v.norm()
        edited[:, cols] -= torch.outer(v, v @ base[:, cols])
    stats, _ = analyse_matrix(base, edited)
    assert stats["rank1_energy"] < 0.95
    assert stats["numerical_rank_1pct"] == 2


def test_missing_and_reshaped_tensors_are_named(tmp_path):
    a = {"x.weight": torch.zeros(4, 4), "gone.weight": torch.zeros(2), "y.weight": torch.zeros(3, 3)}
    b = {"x.weight": torch.zeros(4, 4), "new.weight": torch.zeros(2), "y.weight": torch.zeros(3, 5)}
    report, _ = diff_checkpoints(_toy(tmp_path, "a", a), _toy(tmp_path, "b", b))
    assert report["tensors"]["only_in_base"] == ["gone.weight"]
    assert report["tensors"]["only_in_edited"] == ["new.weight"]
    assert [m["name"] for m in report["tensors"]["shape_or_dtype_mismatch"]] == ["y.weight"]


def test_sidecar_change_is_caught(tmp_path):
    """A changed config with untouched weights is still a change."""
    t = {"x.weight": torch.zeros(4, 4)}
    a = _toy(tmp_path, "a", t, sidecar='{"temperature": 0.6}')
    b = _toy(tmp_path, "b", t, sidecar='{"temperature": 1.0}')
    report, _ = diff_checkpoints(a, b)
    assert report["tensors"]["changed"] == 0
    assert report["sidecar_files"]["different_unexpected"] == ["config.json"]


def test_no_weights_is_a_loud_failure(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="WIRING FAILURE"):
        diff_checkpoints(empty, empty)


def test_cache_path_becomes_repo_and_revision(tmp_path):
    snap = tmp_path / "hub" / "models--Org--Name-0.8B" / "snapshots" / "abc123"
    snap.mkdir(parents=True)
    assert describe_snapshot(snap) == {"repo": "Org/Name-0.8B", "revision": "abc123"}

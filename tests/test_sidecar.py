# offtarget · tests/test_sidecar.py
# v0.1 · 12NOV2026
#
# Practical: the file-by-file comparison of two snapshots, on two folders built by hand
# with one planted difference, one missing file and one weight file that must be left out.
# Philosophical: "identical" is the easiest word to write and the easiest to get wrong.
# The test that matters is the one where a single byte differs and the tool has to say so.
import pytest

from offtarget.sidecar import compare


def _snap(root, name, files):
    d = root / name
    d.mkdir()
    for fname, content in files.items():
        (d / fname).write_bytes(content)
    return d


def test_same_different_missing_and_weights_left_out(tmp_path):
    base = _snap(tmp_path, "base", {"config.json": b"{}", "tokenizer.json": b"abc", "README.md": b"one", "model.safetensors": b"w"})
    edited = _snap(tmp_path, "edited", {"config.json": b"{}", "tokenizer.json": b"abd", "extra.txt": b"x", "model.safetensors": b"v"})
    r = compare(base, edited)
    assert r["same"] == ["config.json"]
    assert r["different"] == ["README.md", "extra.txt", "tokenizer.json"]
    assert "model.safetensors" not in r["files"]            # weights are compared tensor by tensor elsewhere
    assert r["files"]["README.md"]["edited"] is None         # missing on one side is a difference, not a pass
    assert r["files"]["extra.txt"]["base"] is None


def test_a_missing_snapshot_is_loud(tmp_path):
    base = _snap(tmp_path, "base", {"config.json": b"{}"})
    with pytest.raises(FileNotFoundError, match="WIRING FAILURE"):
        compare(base, tmp_path / "nowhere")


def test_nothing_to_compare_is_loud(tmp_path):
    base = _snap(tmp_path, "base", {"model.safetensors": b"w"})
    edited = _snap(tmp_path, "edited", {"model.safetensors": b"v"})
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        compare(base, edited)

# offtarget · offtarget/provenance.py
# v0.1 · 11NOV2026
#
# Practical: three artifacts claim to be the same edit. (1) The exact diff the
# authors published with their logs (edit.npz plus manifest.json, with a sha256 for
# each tensor before and after). (2) The editor model's own manifest of which
# neurons it chose. (3) The checkpoint anyone can download from Hugging Face. This
# file rebuilds the edited tensors from (1) with our own code, and checks all three
# against each other. Run it as:
#   python -I -m offtarget.provenance --base <base snapshot> --edit-dir <logs>/runs/p50c/edit \
#       --neurons <logs>/runs/p50c/work_notes/frozen_weights_manifest.json \
#       [--edited <edited snapshot>] --out results/provenance.json
#
# Philosophical: in a regulated shop the first question about any test report is
# "was the unit you tested the unit you shipped?" It sounds insulting and it is the
# opposite. It is the question that lets everyone stop arguing about the wrong
# object. Here the tested unit is the checkpoint the authors evaluated, and the
# shipped unit is the one on the hub with thousands of downloads. If their hashes
# agree, every later finding lands on the right model. If they do not, nothing
# else in this audit means anything until that is explained.
from __future__ import annotations

import argparse
import contextlib
import json
from pathlib import Path

import numpy as np
import torch

from offtarget.diff import _open_shards, analyse_matrix, describe_snapshot, sha256_tensor

SCHEMA = "offtarget.provenance/0.1"


def rebuild_sparse(base: torch.Tensor, idx: np.ndarray, val: np.ndarray) -> torch.Tensor:
    """Apply a sparse edit (flat indices and new bfloat16 bit patterns) to a base tensor."""
    if base.dtype != torch.bfloat16:
        raise TypeError(f"WIRING FAILURE: sparse edits are stored as bfloat16 bits, base tensor is {base.dtype}")
    if idx.shape != val.shape:
        raise ValueError(f"WIRING FAILURE: {idx.shape[0]} indices but {val.shape[0]} values")
    bits = base.contiguous().view(torch.int16).numpy().copy().reshape(-1)
    bits[idx.astype(np.int64)] = val.astype(np.uint16).view(np.int16)
    return torch.from_numpy(bits.reshape(tuple(base.shape))).view(torch.bfloat16)


def check(
    base_snapshot: Path,
    edit_dir: Path,
    neurons_file: Path | None,
    edited_snapshot: Path | None,
) -> tuple[dict, dict[str, torch.Tensor]]:
    """Run every provenance check. Returns the report and each tensor's direction.

    A hash that does not match is a FINDING and is reported as a failed check. A
    tensor that is missing, or an edit format we cannot read, is a WIRING FAILURE
    and raises, because then we have not checked anything at all.
    """
    manifest = json.loads((edit_dir / "manifest.json").read_text(encoding="utf-8"))
    arrays = np.load(edit_dir / "edit.npz", allow_pickle=False)
    neurons = json.loads(neurons_file.read_text(encoding="utf-8")) if neurons_file else {}
    chosen_by_name = {v["name"]: v["selected_neurons"] for v in neurons.values()}

    checks: list[dict] = []
    tensors: list[dict] = []
    directions: dict[str, torch.Tensor] = {}

    def record(name: str, what: str, ok: bool, detail: str) -> None:
        checks.append({"tensor": name, "check": what, "pass": bool(ok), "detail": detail})

    with contextlib.ExitStack() as stack:
        wb = _open_shards(Path(base_snapshot), stack)
        we = _open_shards(Path(edited_snapshot), stack) if edited_snapshot else None
        for i, t in enumerate(manifest["tensors"]):
            name = t["name"]
            if t["form"] != "sparse":
                raise NotImplementedError(f"WIRING FAILURE: edit form {t['form']!r} for {name} is not handled yet")
            if name not in wb:
                raise KeyError(f"WIRING FAILURE: {name} is not in the base checkpoint")
            tb = wb[name].get_tensor(name)

            base_hash = sha256_tensor(tb)
            record(name, "base tensor is the one the edit was made on", base_hash == t["base_sha256"],
                   f"ours {base_hash[:16]}, manifest {t['base_sha256'][:16]}")

            rebuilt = rebuild_sparse(tb, arrays[f"t{i}_idx"], arrays[f"t{i}_val"])
            rebuilt_hash = sha256_tensor(rebuilt)
            record(name, "edit rebuilt from the logs matches the evaluated tensor", rebuilt_hash == t["edited_sha256"],
                   f"ours {rebuilt_hash[:16]}, manifest {t['edited_sha256'][:16]}")

            if we is not None:
                if name not in we:
                    raise KeyError(f"WIRING FAILURE: {name} is not in the published edited checkpoint")
                hub_hash = sha256_tensor(we[name].get_tensor(name))
                record(name, "published checkpoint holds the evaluated tensor", hub_hash == t["edited_sha256"],
                       f"hub {hub_hash[:16]}, manifest {t['edited_sha256'][:16]}")

            stats, u = analyse_matrix(tb, rebuilt)
            directions[name] = u
            record(name, "entries that differ after rounding match the manifest",
                   stats["n_changed"] == t["changed_entries"],
                   f"ours {stats['n_changed']:,}, manifest {t['changed_entries']:,}")
            if name in chosen_by_name:
                record(name, "changed columns are the neurons the editor says it chose",
                       stats["cols"] == sorted(chosen_by_name[name]),
                       f"{stats['n_cols_changed']} columns changed, {len(chosen_by_name[name])} neurons listed")
            tensors.append({"name": name, "shape": list(tb.shape), **stats})

    names = list(directions)
    cosines = [
        {"a": a, "b": b, "abs_cos": float(torch.dot(directions[a], directions[b]).abs())}
        for i, a in enumerate(names) for b in names[i + 1:]
        if directions[a].shape == directions[b].shape
    ]
    return {
        "schema": SCHEMA,
        "base": describe_snapshot(Path(base_snapshot)),
        "edited": describe_snapshot(Path(edited_snapshot)) if edited_snapshot else None,
        "edit_source": "/".join(edit_dir.parts[-4:]),
        "checks": checks,
        "all_pass": all(c["pass"] for c in checks),
        "tensors": tensors,
        "direction_cosines": cosines,
    }, directions


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.provenance")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="Check the logged edit, the editor's manifest and the hub checkpoint agree.")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--edit-dir", required=True, type=Path)
    ap.add_argument("--neurons", type=Path)
    ap.add_argument("--edited", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--directions", type=Path)
    args = ap.parse_args()

    report, directions = check(args.base, args.edit_dir, args.neurons, args.edited)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.directions:
        from safetensors.torch import save_file
        save_file(directions, str(args.directions))

    for c in report["checks"]:
        print(f"{'PASS' if c['pass'] else 'FAIL'}  {c['tensor'].split('language_model.')[-1]}: {c['check']} ({c['detail']})")
    for t in report["tensors"]:
        fit, sel = t["projection_fit"], t["column_selection"]
        print(f"{t['name'].split('language_model.')[-1]}: {t['n_cols_changed']} cols x {t['n_rows_changed']} rows, "
              f"{t['n_changed']:,} values differ, relative change {t['rel_change']:.4%}")
        print(f"    rank-1 energy {t['rank1_energy']:.6f}, alpha {fit['alpha']:.4f}, "
              f"write along u after/before {fit['remaining_frac']:.3f}")
        print(f"    columns hold {sel['share_of_layer_write_mass']:.1%} of the layer's write along u; "
              f"overlap with the top-{t['n_cols_changed']} static writers {sel['overlap_with_topk_writers']:.1%}")
    for c in report["direction_cosines"]:
        print(f"|cos| between the two layers' directions: {c['abs_cos']:.4f}")
    print("ALL CHECKS PASS" if report["all_pass"] else "AT LEAST ONE CHECK FAILED")


if __name__ == "__main__":
    main()

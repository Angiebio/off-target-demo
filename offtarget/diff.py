# offtarget · offtarget/diff.py
# v0.1 · 11NOV2026
#
# Practical: subtract one checkpoint from another, tensor by tensor, and describe
# what moved. Which tensors, which rows and columns, how big the change is next to
# the weights it changed, what rank it has, and the direction it points along. It
# also hashes every file so the result names exactly which two artifacts it compared.
# Run it as:
#   python -I -m offtarget.diff --base <snapshot dir> --edited <snapshot dir> --out results/diff.json
#
# Philosophical: before anyone argues about whether an edit to a mind was a good
# idea, somebody has to read the patch. A blog post says "we changed 131,072
# numbers". This file is the person at the back of the change control meeting who
# opens both versions side by side and counts. Nothing here runs the model. It is
# pure bookkeeping, and bookkeeping is where trust starts, because every later
# claim ("the loops went away", "nothing else broke") is a claim about THIS diff
# and no other.
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import save_file

SCHEMA = "offtarget.diff/0.1"
LAYER_RE = re.compile(r"layers\.(\d+)\.")
# Files we never expect to match between a model and its edited copy, and say so
# out loud instead of hiding them: the model card is rewritten by whoever uploads.
EXPECTED_TO_DIFFER = {"README.md"}


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    """Hash a file in chunks. A checkpoint is too big to read in one gulp."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def sha256_tensor(t: torch.Tensor) -> str:
    """Hash a tensor's stored bytes, exactly as they sit in the checkpoint.

    Practical: this is the convention the edit's authors use in their manifest
    (sha256 over the raw bfloat16 values), so our hash and theirs can be compared.
    Philosophical: a lot number for a matrix. Two people who never met can each
    compute it and know they are holding the same part.
    """
    return hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()


def describe_snapshot(snapshot: Path) -> dict:
    """Name a snapshot by repo and revision when it sits in a Hugging Face cache.

    Practical: a cache path looks like models--Org--Name/snapshots/<commit>. We turn
    that into "Org/Name" and the commit, and never write the local path to disk.
    Philosophical: a result that says "C:/Users/someone/..." can be checked by one
    person. A result that says "Org/Name at commit abc" can be checked by anyone.
    """
    parts = snapshot.resolve().parts
    for i, part in enumerate(parts):
        if part.startswith("models--") and i + 2 < len(parts) and parts[i + 1] == "snapshots":
            return {"repo": part[len("models--"):].replace("--", "/"), "revision": parts[i + 2]}
    return {"repo": snapshot.name, "revision": None}


def _open_shards(snapshot: Path, stack: contextlib.ExitStack) -> dict[str, object]:
    """Map every tensor name in a snapshot to the open shard that holds it."""
    shards = sorted(snapshot.glob("*.safetensors"))
    if not shards:
        raise FileNotFoundError(f"WIRING FAILURE: no .safetensors files in {snapshot}")
    where: dict[str, object] = {}
    for shard in shards:
        handle = stack.enter_context(safe_open(str(shard), framework="pt", device="cpu"))
        for name in handle.keys():
            if name in where:
                raise RuntimeError(f"WIRING FAILURE: tensor {name} appears in two shards of {snapshot}")
            where[name] = handle
    return where


def _weight_files(snapshot: Path) -> list[dict]:
    out = []
    for shard in sorted(snapshot.glob("*.safetensors")):
        with safe_open(str(shard), framework="pt", device="cpu") as handle:
            meta = handle.metadata() or {}
        out.append({"name": shard.name, "bytes": shard.stat().st_size, "sha256": sha256_file(shard), "metadata": meta})
    return out


def _sidecars(base: Path, edited: Path) -> dict:
    """Compare everything that is NOT weights: config, tokenizer, chat template.

    Philosophical: a model's behaviour lives in more than its tensors. Swap the chat
    template or a sampling default and you have changed the product without touching
    a single weight. A change record that only looks at the matrices has looked at
    the engine and skipped the fuel.
    """
    def listing(root: Path) -> dict[str, str]:
        # `.cache/` is the download tool's own bookkeeping, written on this machine.
        # It is not part of what the authors published, so it is not compared.
        return {
            p.relative_to(root).as_posix(): sha256_file(p)
            for p in sorted(root.rglob("*"))
            if p.is_file() and p.suffix != ".safetensors" and ".cache" not in p.relative_to(root).parts
        }

    b, e = listing(base), listing(edited)
    common = sorted(set(b) & set(e))
    different = [n for n in common if b[n] != e[n]]
    return {
        "identical": [n for n in common if b[n] == e[n]],
        "different": different,
        "different_unexpected": [n for n in different if n not in EXPECTED_TO_DIFFER],
        "only_in_base": sorted(set(b) - set(e)),
        "only_in_edited": sorted(set(e) - set(b)),
    }


def analyse_matrix(tb: torch.Tensor, te: torch.Tensor) -> tuple[dict, torch.Tensor]:
    """Describe the change to one 2-D weight and return its main direction.

    Practical: PyTorch stores a Linear weight as [out, in]. For an MLP's output
    projection, each COLUMN is one neuron's contribution to the residual stream, a
    vector of length d_model. So "the direction" of an edit to output columns is a
    left singular vector of the delta, also of length d_model. We take the SVD of
    only the changed columns, since everything else is exactly zero.

    Then three questions a reviewer would ask:
      1. Is it one direction? (share of the delta's energy in the top component)
      2. Is it a clean projection removal, w <- w - alpha * u (u . w)? (fit alpha)
      3. Why these columns? (are they the ones that wrote most along u?)
    """
    changed = tb != te
    cols = changed.any(dim=0).nonzero().flatten()
    rows = changed.any(dim=1).nonzero().flatten()
    base = tb.double()
    delta = te.double() - base
    sub = delta[:, cols]

    U, S, _ = torch.linalg.svd(sub, full_matrices=False)
    energy = (S**2) / (S**2).sum()
    u = U[:, 0]

    # Fit delta[:, J] = -alpha * u u^T W[:, J]. alpha = 1 is a full projection removal.
    proj = torch.outer(u, u @ base[:, cols])
    alpha = float(-(sub * proj).sum() / (proj * proj).sum())
    residual = float(torch.linalg.norm(sub + alpha * proj) / torch.linalg.norm(sub))
    before = float(torch.linalg.norm(u @ base[:, cols]))
    after = float(torch.linalg.norm(u @ te.double()[:, cols]))

    # How much of what this matrix can write along u did the chosen columns hold?
    write = (u @ base) ** 2
    k = int(cols.numel())
    topk = set(torch.topk(write, k).indices.tolist())
    chosen = set(cols.tolist())

    stats = {
        "n_changed": int(changed.sum()),
        "n_addressed": int(cols.numel() * rows.numel()),
        "n_cols_changed": k,
        "n_rows_changed": int(rows.numel()),
        "cols": cols.tolist(),
        "delta_fro": float(torch.linalg.norm(delta)),
        "base_fro": float(torch.linalg.norm(base)),
        "rel_change": float(torch.linalg.norm(delta) / torch.linalg.norm(base)),
        "max_abs_delta": float(delta.abs().max()),
        "singular_values_top5": [float(s) for s in S[:5]],
        "rank1_energy": float(energy[0]),
        "numerical_rank_1pct": int((S > 0.01 * S[0]).sum()),
        "projection_fit": {
            "alpha": alpha,
            "residual_frac": residual,
            "write_along_u_before": before,
            "write_along_u_after": after,
            "remaining_frac": after / before if before else None,
        },
        "column_selection": {
            "overlap_with_topk_writers": len(topk & chosen) / k,
            "share_of_layer_write_mass": float(write[cols].sum() / write.sum()),
        },
    }
    return stats, u.float()


def diff_checkpoints(base: Path, edited: Path) -> tuple[dict, dict[str, torch.Tensor]]:
    """Compare two snapshots. Returns the report and the direction of each changed matrix."""
    base, edited = Path(base), Path(edited)
    directions: dict[str, torch.Tensor] = {}
    changed_report: list[dict] = []
    mismatched: list[dict] = []
    total_params = 0
    params_by_group: dict[str, int] = {}
    identical = 0

    with contextlib.ExitStack() as stack:
        wb, we = _open_shards(base, stack), _open_shards(edited, stack)
        common = sorted(set(wb) & set(we))
        for name in common:
            tb, te = wb[name].get_tensor(name), we[name].get_tensor(name)
            total_params += tb.numel()
            group = ".".join(name.split(".")[:2])
            params_by_group[group] = params_by_group.get(group, 0) + tb.numel()
            if tb.shape != te.shape or tb.dtype != te.dtype:
                mismatched.append({
                    "name": name,
                    "base": [list(tb.shape), str(tb.dtype)],
                    "edited": [list(te.shape), str(te.dtype)],
                })
                continue
            if torch.equal(tb, te):
                identical += 1
                continue
            layer = LAYER_RE.search(name)
            entry = {
                "name": name,
                "shape": list(tb.shape),
                "dtype": str(tb.dtype),
                "layer": int(layer.group(1)) if layer else None,
                "base_sha256": sha256_tensor(tb),
                "edited_sha256": sha256_tensor(te),
            }
            if tb.ndim == 2:
                stats, u = analyse_matrix(tb, te)
                entry.update(stats)
                directions[name] = u
            else:
                delta = te.double() - tb.double()
                entry.update({
                    "n_changed": int((tb != te).sum()),
                    "delta_fro": float(torch.linalg.norm(delta)),
                    "base_fro": float(torch.linalg.norm(tb.double())),
                })
            changed_report.append(entry)

        only_base, only_edited = sorted(set(wb) - set(we)), sorted(set(we) - set(wb))

    names = list(directions)
    cosines = [
        {"a": a, "b": b, "abs_cos": float(torch.dot(directions[a], directions[b]).abs())}
        for i, a in enumerate(names)
        for b in names[i + 1:]
        if directions[a].shape == directions[b].shape
    ]
    n_changed = sum(c["n_changed"] for c in changed_report)
    n_addressed = sum(c.get("n_addressed", c["n_changed"]) for c in changed_report)
    report = {
        "schema": SCHEMA,
        "base": {**describe_snapshot(base), "weight_files": _weight_files(base)},
        "edited": {**describe_snapshot(edited), "weight_files": _weight_files(edited)},
        "tensors": {
            "compared": len(common),
            "identical": identical,
            "changed": len(changed_report),
            "only_in_base": only_base,
            "only_in_edited": only_edited,
            "shape_or_dtype_mismatch": mismatched,
        },
        "params": {
            "total": total_params,
            "by_group": dict(sorted(params_by_group.items(), key=lambda kv: -kv[1])),
            "values_that_differ": n_changed,
            "addressed": n_addressed,
            "addressed_pct_of_total": 100.0 * n_addressed / total_params if total_params else None,
        },
        "changed": changed_report,
        "direction_cosines": cosines,
        "sidecar_files": _sidecars(base, edited),
    }
    return report, directions


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.diff")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="Diff two safetensors checkpoints, tensor by tensor.")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--edited", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path, help="where to write the JSON report")
    ap.add_argument("--directions", type=Path, help="where to write the directions (.safetensors)")
    args = ap.parse_args()

    report, directions = diff_checkpoints(args.base, args.edited)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.directions and directions:
        save_file(directions, str(args.directions))

    t, p = report["tensors"], report["params"]
    print(f"compared {t['compared']} tensors: {t['identical']} identical, {t['changed']} changed, "
          f"{len(t['only_in_base'])} only in base, {len(t['only_in_edited'])} only in edited, "
          f"{len(t['shape_or_dtype_mismatch'])} shape or dtype mismatches")
    print(f"{p['addressed']:,} weights addressed ({p['values_that_differ']:,} stored values differ) "
          f"of {p['total']:,} = {p['addressed_pct_of_total']:.4f}%")
    for c in report["changed"]:
        line = f"  {c['name']}  shape {c['shape']}  {c['n_changed']:,} values differ"
        if "rank1_energy" in c:
            line += (f"  cols {c['n_cols_changed']}  rows {c['n_rows_changed']}"
                     f"  rank-1 energy {c['rank1_energy']:.6f}  alpha {c['projection_fit']['alpha']:.4f}")
        print(line)
    for c in report["direction_cosines"]:
        print(f"  |cos| between directions: {c['abs_cos']:.6f}")
    s = report["sidecar_files"]
    print(f"sidecar files: {len(s['identical'])} identical, different: {s['different']}, "
          f"only in base: {s['only_in_base']}, only in edited: {s['only_in_edited']}")


if __name__ == "__main__":
    main()

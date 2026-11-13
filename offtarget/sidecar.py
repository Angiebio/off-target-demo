# offtarget · offtarget/sidecar.py
# v0.1 · 12NOV2026
#
# Practical: a checkpoint is more than its weights. The tokenizer, the configuration
# and the chat template decide what the weights are asked, and a change to any of them
# changes behaviour without touching a tensor. This compares every file that is not a
# weight file between two snapshots, by sha256, and writes what is the same and what
# is not.
#   python -I -m offtarget.sidecar --base <base snapshot> --edited <edited snapshot> --out results/sidecar.json
#
# Philosophical: the article said "the tokenizer, the configuration and the chat
# template are identical to the public base model" for a night before any file in
# results/ said so. It was true. I had checked it by eye on the first day and written
# the sentence from memory. A second reader asked where it was recorded, and the honest
# answer was nowhere. A true sentence without a record is still a debt, so this pays it.
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "offtarget.sidecar/0.1"
WEIGHTS = (".safetensors", ".bin", ".pt", ".gguf")   # compared tensor by tensor elsewhere (diff.py), never here


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def compare(base: Path, edited: Path) -> dict:
    """Every non-weight file in either snapshot, with its hash on each side."""
    for d in (base, edited):
        if not d.is_dir():
            raise FileNotFoundError(f"WIRING FAILURE: no snapshot folder at {d}")
    names = sorted({p.name for d in (base, edited) for p in d.iterdir() if p.is_file() and not p.name.endswith(WEIGHTS)})
    if not names:
        raise RuntimeError(f"WIRING FAILURE: no files besides weights in {base} or {edited}. Nothing was compared.")
    files = {}
    for name in names:
        b, e = base / name, edited / name
        hb = sha256_file(b) if b.is_file() else None
        he = sha256_file(e) if e.is_file() else None
        files[name] = {"base": hb, "edited": he, "same": hb is not None and hb == he}
    return {
        "schema": SCHEMA,
        "files": files,
        "same": [n for n, f in files.items() if f["same"]],
        "different": [n for n, f in files.items() if not f["same"]],
    }


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.sidecar")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="Compare the non-weight files of two snapshots by hash.")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--edited", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    report = compare(args.base, args.edited)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    for name, f in report["files"].items():
        print(f"  {'same     ' if f['same'] else 'DIFFERENT'}  {name}")
    print(f"{len(report['same'])} the same, {len(report['different'])} different")


if __name__ == "__main__":
    main()

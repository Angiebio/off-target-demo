# offtarget · offtarget/dose.py
# v0.1 · 11NOV2026
#
# Practical: turns the published edit into a dial. The edit has the form
#   W' = W - alpha * u (u . W)   on a chosen set of columns,
# with alpha = 6 as shipped. Here we recover u and the columns from the published
# tensors and rebuild the weight at any alpha: 0 is the base model, 1 is a true
# projection removal (what "subtracted that direction" sounds like), 6 is what was
# evaluated, and anything else is a dose nobody has published results for.
#
# Philosophical: a drug label does not say "we added the molecule". It says how
# much. The single most useful thing an auditor can do with a one-number edit is
# turn the number, because a benefit and a harm that both rise with dose stop being
# anecdotes and become a curve somebody chose a point on. This module is the dial.
# It runs no model. The model-running lives in run.py, so that this arithmetic can
# be tested to the last bit on a laptop.
from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from offtarget.diff import _open_shards, analyse_matrix, sha256_tensor
from offtarget.provenance import rebuild_sparse


@dataclass
class Edit:
    """One edited tensor, with everything needed to rebuild it at any dose."""
    name: str
    base: torch.Tensor          # bfloat16, as in the public base checkpoint
    published: torch.Tensor     # bfloat16, as evaluated by the authors
    u: torch.Tensor             # float32 unit direction in the residual stream
    cols: list[int]             # the neurons (output columns) the edit touches
    published_alpha: float      # the dose the published tensor fits

    def at(self, alpha: float) -> torch.Tensor:
        """The weight at dose alpha, in bfloat16.

        0 returns the base tensor and the published dose returns the published
        tensor, both bit for bit, so the two anchor points of every curve are the
        real artifacts and not our reconstruction of them. Other doses follow the
        editor's own recipe: compute in float32, then round to bfloat16.
        """
        if alpha == 0:
            return self.base.clone()
        if alpha == self.published_alpha:
            return self.published.clone()
        w = self.base.float()
        w[:, self.cols] -= alpha * torch.outer(self.u, self.u @ w[:, self.cols])
        return w.to(torch.bfloat16)

    def reconstruction_error(self) -> dict:
        """How well our formula at the published dose reproduces the published bits.

        This is the check that the dial is attached to the right machine. If our
        u and columns were wrong, the rebuilt tensor would not match theirs.
        """
        w = self.base.float()
        w[:, self.cols] -= self.published_alpha * torch.outer(self.u, self.u @ w[:, self.cols])
        ours = w.to(torch.bfloat16)
        touched = self.published[:, self.cols]
        same = (ours[:, self.cols] == touched).float().mean()
        err = (ours.float() - self.published.float()).abs().max()
        scale = (self.published.float() - self.base.float()).abs().max()
        return {
            "bit_identical_share_of_touched": float(same),
            "max_abs_error": float(err),
            "max_abs_error_relative_to_largest_change": float(err / scale),
            "untouched_columns_identical": bool(torch.equal(
                ours[:, [c for c in range(ours.shape[1]) if c not in set(self.cols)]],
                self.base[:, [c for c in range(ours.shape[1]) if c not in set(self.cols)]],
            )),
        }


def load_edits(base_snapshot: Path, edit_dir: Path) -> list[Edit]:
    """Read the published edit from the authors' logs and fit its direction and dose.

    Every tensor is checked against the hashes in the authors' manifest first. A
    dial built on the wrong tensors would turn smoothly and mean nothing.
    """
    manifest = json.loads((edit_dir / "manifest.json").read_text(encoding="utf-8"))
    arrays = np.load(edit_dir / "edit.npz", allow_pickle=False)
    edits: list[Edit] = []
    with contextlib.ExitStack() as stack:
        wb = _open_shards(Path(base_snapshot), stack)
        for i, t in enumerate(manifest["tensors"]):
            name = t["name"]
            if name not in wb:
                raise KeyError(f"WIRING FAILURE: {name} is not in the base checkpoint")
            base = wb[name].get_tensor(name)
            if sha256_tensor(base) != t["base_sha256"]:
                raise RuntimeError(f"WIRING FAILURE: base tensor {name} is not the one the edit was made on")
            published = rebuild_sparse(base, arrays[f"t{i}_idx"], arrays[f"t{i}_val"])
            if sha256_tensor(published) != t["edited_sha256"]:
                raise RuntimeError(f"WIRING FAILURE: rebuilt {name} does not match the evaluated tensor")
            stats, u = analyse_matrix(base, published)
            alpha = stats["projection_fit"]["alpha"]
            if stats["rank1_energy"] < 0.999:
                raise RuntimeError(
                    f"WIRING FAILURE: the change to {name} is not one direction "
                    f"(rank-1 energy {stats['rank1_energy']:.4f}), so a single dose dial does not describe it"
                )
            edits.append(Edit(name=name, base=base, published=published, u=u, cols=stats["cols"],
                              published_alpha=round(alpha, 2)))
    return edits


# ---- arms: the published dial, one layer at a time, and a random direction ---------------
# v0.2 · 11NOV2026
#
# Practical: an "arm" is one setting of the two edited tensors, named by a string so a
# run's output can say exactly what was loaded:
#   dose:<alpha>   both layers at dose alpha along the published direction
#   only:<layer>   the published edit on that layer, the base weights on the other
#   random:<k>     the same recipe on the same neurons with a random direction, scaled
#                  so the weights move exactly as far as the published edit moved them
#   matched:<k>    that same random direction, scaled up until it pushes on the model's
#                  activations as hard as the published edit does (needs a calibration)
# Philosophical: Kai's control. If a random shove of the same size in the same place
# does the same thing, the direction was never special and the "edit" is damage that
# happens to help. A treatment arm means nothing without the sham next to it.
def layer_of(edit: Edit) -> int:
    return int(edit.name.split("layers.")[1].split(".")[0])


def random_direction(edit: Edit, seed: int) -> torch.Tensor:
    """A unit direction with nothing in common with the edit's own."""
    g = torch.Generator().manual_seed(seed)
    r = torch.randn(edit.u.shape[0], generator=g, dtype=torch.float32)
    u = edit.u.float()
    r = r - (r @ u) * u / (u @ u)
    return r / r.norm()


def random_arm(edit: Edit, seed: int, scale: float = 1.0) -> torch.Tensor:
    """The edit's recipe with a random direction, moving the weights the same distance.

    With scale 1 this is the control as it is usually specified, and as the editor
    model ran it: the same distance in weight space. Measured on real activations,
    that control pushes on the model about a fifth as hard as the edit does, because
    these neurons were chosen for writing the published direction together and they
    write a random one incoherently. So a second control multiplies the same change
    by `scale` until the push matches. A sham that weighs the same as the pill is not
    much of a sham if it dissolves before it reaches the bloodstream.
    """
    r = random_direction(edit, seed)
    w = edit.base.float()
    step = torch.outer(r, r @ w[:, edit.cols])
    distance = (edit.published.float() - edit.base.float()).norm()
    if float(step.norm()) == 0.0:
        raise RuntimeError("WIRING FAILURE: the random direction has no component in the edited columns")
    w[:, edit.cols] -= scale * (distance / step.norm()) * step
    return w.to(torch.bfloat16)


def _seed(k: int, edit: Edit) -> int:
    return 7919 * (k + 1) + layer_of(edit)


def arm_tensors(edits: list[Edit], arm: str, calibration: dict | None = None) -> list[torch.Tensor]:
    kind, _, value = arm.partition(":")
    if kind == "dose":
        return [e.at(float(value)) for e in edits]
    if kind == "only":
        if int(value) not in [layer_of(e) for e in edits]:
            raise ValueError(f"WIRING FAILURE: no edited layer {value}")
        return [e.at(e.published_alpha if layer_of(e) == int(value) else 0) for e in edits]
    if kind == "random":
        return [random_arm(e, _seed(int(value), e)) for e in edits]
    if kind == "matched":
        if not calibration or f"random:{value}" not in calibration:
            raise ValueError(f"WIRING FAILURE: no push calibration for random:{value}")
        scales = calibration[f"random:{value}"]
        return [random_arm(e, _seed(int(value), e), float(scales[f"L{layer_of(e)}"])) for e in edits]
    raise ValueError(f"WIRING FAILURE: no such arm: {arm}")

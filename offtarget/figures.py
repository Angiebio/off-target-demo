# offtarget · offtarget/figures.py
# v0.1 · 11NOV2026
#
# Practical: draws the one picture that carries finding 2. For every neuron in the
# two edited MLPs it plots how much that neuron wrote along the direction before
# the edit (across) against after (up). Untouched neurons sit on the diagonal. A
# deletion would put the edited ones on the horizontal axis. They are not there.
#   python -I -m offtarget.figures --base <base snapshot> --edit-dir <logs>/runs/p50c/edit \
#       --out results/fig_before_after.png
#
# Philosophical: "we subtracted a direction" and "we reversed it at five times the
# strength" are one line of algebra apart and a world apart to a reviewer. Words
# argue. A picture where 64 dots refuse to sit where the summary says they sit
# does not. Colour is used for one job only, to pick out the neurons that were
# edited, and everything else stays grey so the eye lands where the finding is.
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from offtarget.dose import load_edits  # noqa: E402

# Reference palette of the dataviz skill, light surface. Emphasis form: one hue + grey.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
ACCENT = "#2a78d6"


def draw(edits, out: Path) -> None:
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    fig, axes = plt.subplots(1, len(edits), figsize=(11, 5.6), sharex=True, sharey=True, facecolor=SURFACE)
    for ax, e in zip(axes, edits):
        before = (e.u @ e.base.float()).numpy()
        after = (e.u @ e.published.float()).numpy()
        chosen = set(e.cols)
        rest = [j for j in range(len(before)) if j not in chosen]
        lim = float(abs(before).max()) * 1.08

        ax.set_facecolor(SURFACE)
        ax.axhline(0, color=AXIS, lw=1, zorder=1)
        ax.axvline(0, color=AXIS, lw=1, zorder=1)
        ax.axline((0, 0), slope=1, color=MUTED, lw=1, zorder=2)
        ax.axline((0, 0), slope=-5, color=INK_2, lw=1, zorder=2)
        ax.scatter(before[rest], after[rest], s=9, color=MUTED, alpha=0.45, linewidths=0, zorder=3,
                   label=f"{len(rest):,} neurons left alone")
        ax.scatter(before[e.cols], after[e.cols], s=46, color=ACCENT, edgecolors=SURFACE, linewidths=1.3, zorder=4,
                   label=f"{len(e.cols)} edited neurons")

        layer = e.name.split("layers.")[1].split(".")[0]
        ax.set_title(f"Layer {layer} MLP", loc="left", fontsize=12, color=INK, pad=10)
        ax.set_xlim(-lim, lim)
        ax.grid(True, color=GRID, lw=0.6, zorder=0)
        ax.tick_params(colors=MUTED, labelsize=9, length=0)
        for side in ("top", "right", "left", "bottom"):
            ax.spines[side].set_visible(False)
        ax.set_xlabel("written along the direction before the edit", fontsize=10, color=INK_2)

    top = max(abs(a) for ax in axes for a in ax.get_ylim())
    axes[0].set_ylim(-top, top)
    axes[0].set_ylabel("written along the direction after the edit", fontsize=10, color=INK_2)

    # Direct labels on the three reference lines, once, in the left panel. Each sits
    # in a quadrant its own line leaves empty, so no label lands on a dot.
    ax = axes[0]
    x_lo, x_hi = ax.get_xlim()
    ax.text(x_hi * 0.97, x_hi * 0.97 + 0.035, "left alone: on this line", fontsize=9, color=INK_2, ha="right", va="bottom")
    ax.text(x_hi * 0.97, -0.03, "a deletion would land on zero", fontsize=9, color=INK_2, ha="right", va="top")
    ax.text(x_lo * 0.52, -5 * x_lo * 0.62, "what shipped: reversed, five times over", fontsize=9, color=INK_2,
            ha="left", va="center")

    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(handles[::-1], labels[::-1], loc="lower left", bbox_to_anchor=(0.062, 0.895), ncols=2, frameon=False,
               fontsize=10, labelcolor=INK_2, handletextpad=0.3, columnspacing=1.6)
    fig.suptitle("The edit did not delete the direction. It reversed it, at five times the strength.",
                 x=0.07, y=0.985, ha="left", fontsize=14.5, color=INK, fontweight="semibold")
    fig.text(0.07, 0.012,
             "Each dot is one of 3,584 neurons. Position is the dot product of its output weights with the layer's edit direction, "
             "from the published base and edited tensors.\nSource: Qwen/Qwen3.5-0.8B and the edit logged in "
             "RikiyaT/lm_understand-logs (exp8_math/runs/p50c). Fitted form: W' = W - 6 u (u . W) on 64 columns per layer.",
             fontsize=8, color=MUTED, ha="left", va="bottom")
    fig.subplots_adjust(left=0.07, right=0.985, top=0.83, bottom=0.17, wspace=0.06)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    from offtarget.isolation import require_isolated

    require_isolated("offtarget.figures")     # this tool reads files written by someone else
    ap = argparse.ArgumentParser(description="Before and after, per neuron, along the edit direction.")
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--edit-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    draw(load_edits(args.base, args.edit_dir), args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

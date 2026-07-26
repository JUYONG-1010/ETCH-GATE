"""Dashboard for the preregistered OES incremental-value pilot."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

INK = "#17212B"
MUTED = "#66717E"
TEAL = "#007F7B"
CORAL = "#D9534F"
PALE = "#F4F7F8"


def plot_oes_pilot_dashboard(
    wafer_metrics: pd.DataFrame,
    summary: dict[str, object],
    output_path: Path,
) -> None:
    """Show the pre-registered OES decision without obscuring a negative result."""

    full = wafer_metrics[wafer_metrics["stage"] == "full_map"].copy()
    lot = full.groupby(["lot_number", "family"], as_index=False)["mae"].mean()
    wide = lot.pivot(index="lot_number", columns="family", values="mae")
    order = ["process_only_pls", "process_oes_pls"]
    labels = ["Process only", "Process + OES"]
    colors = [TEAL, CORAL]
    overall = [
        float(summary["process_only_lot_macro_mae"]),
        float(summary["process_oes_lot_macro_mae"]),
    ]
    paired = full.pivot(
        index=["experiment_key", "lot_number"], columns="family", values="mae"
    ).reset_index()
    delta = wide["process_oes_pls"] - wide["process_only_pls"]

    figure = plt.figure(figsize=(16, 9), facecolor=PALE)
    grid = figure.add_gridspec(2, 3, height_ratios=[0.8, 1.2], hspace=0.38, wspace=0.35)
    figure.suptitle(
        "OES pilot: raw feature fusion does not clear the unseen-lot gate",
        x=0.055,
        y=0.965,
        ha="left",
        fontsize=20,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.055,
        0.925,
        "Pre-registered Lots 2, 4, 6, 9 | 39 wafers | direct 89-point P-17 "
        "stepheight | lower MAE is better",
        fontsize=9.5,
        color=MUTED,
    )

    overall_axis = figure.add_subplot(grid[0, 0])
    bars = overall_axis.bar(labels, overall, color=colors, width=0.58)
    overall_axis.set_title(
        "Lot-macro full-map error", loc="left", fontsize=11, fontweight="bold", color=INK
    )
    overall_axis.set_ylabel("MAE (um)", fontsize=9)
    overall_axis.set_ylim(0, max(overall) * 1.28)
    overall_axis.spines[["top", "right"]].set_visible(False)
    overall_axis.grid(axis="y", color="#D8DFE3", linewidth=0.7)
    overall_axis.set_axisbelow(True)
    overall_axis.tick_params(labelsize=8, colors=MUTED)
    for bar, value in zip(bars, overall, strict=True):
        overall_axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.008,
            f"{value:.4f}",
            ha="center",
            fontsize=9,
            fontweight="bold",
            color=INK,
        )

    gate_axis = figure.add_subplot(grid[0, 1])
    relative = 100 * float(summary["lot_macro_relative_mae_reduction"])
    actual_lots = int(summary["lots_improved"])
    gate_axis.axis("off")
    gate_axis.text(
        0, 0.9, "Pre-registered retention gate", fontsize=11, fontweight="bold", color=INK
    )
    gate_axis.text(0, 0.62, "Required", fontsize=9, color=MUTED)
    gate_axis.text(0.48, 0.62, "Observed", fontsize=9, color=MUTED)
    gate_axis.text(0, 0.42, "MAE reduction", fontsize=9, color=INK)
    gate_axis.text(
        0.48, 0.42, f"{relative:+.2f}%  (need +5.00%)", fontsize=11, fontweight="bold", color=CORAL
    )
    gate_axis.text(0, 0.19, "Lots improved", fontsize=9, color=INK)
    gate_axis.text(
        0.48, 0.19, f"{actual_lots}/4  (need 3/4)", fontsize=11, fontweight="bold", color=CORAL
    )

    lot_axis = figure.add_subplot(grid[0, 2])
    lot_axis.bar(
        [f"L{value}" for value in delta.index],
        delta.to_numpy(),
        color=[TEAL if value < 0 else CORAL for value in delta],
    )
    lot_axis.axhline(0, color=INK, linewidth=0.9)
    lot_axis.set_title(
        "OES minus process-only error", loc="left", fontsize=11, fontweight="bold", color=INK
    )
    lot_axis.set_ylabel("Delta MAE (um)", fontsize=9)
    lot_axis.spines[["top", "right"]].set_visible(False)
    lot_axis.grid(axis="y", color="#D8DFE3", linewidth=0.7)
    lot_axis.set_axisbelow(True)
    lot_axis.tick_params(labelsize=8, colors=MUTED)

    matrix_axis = figure.add_subplot(grid[1, :2])
    matrix = wide[order].T
    image = matrix_axis.imshow(matrix, cmap="YlGnBu", aspect="auto")
    matrix_axis.set_title(
        "Mean full-map MAE by held-out lot", loc="left", fontsize=12, fontweight="bold", color=INK
    )
    matrix_axis.set_xticks(
        np.arange(len(matrix.columns)), [f"Lot {int(value)}" for value in matrix.columns]
    )
    matrix_axis.set_yticks(np.arange(2), labels)
    matrix_axis.tick_params(labelsize=9, colors=MUTED)
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = matrix.iloc[row, column]
            matrix_axis.text(
                column,
                row,
                f"{value:.3f}",
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
                color="white" if value > 0.35 else INK,
            )
    colorbar = figure.colorbar(image, ax=matrix_axis, fraction=0.035, pad=0.02)
    colorbar.set_label("MAE (um)", fontsize=8)
    colorbar.ax.tick_params(labelsize=7, colors=MUTED)

    pair_axis = figure.add_subplot(grid[1, 2])
    pair_axis.scatter(
        paired["process_only_pls"],
        paired["process_oes_pls"],
        c=paired["lot_number"],
        cmap="tab10",
        s=42,
        alpha=0.9,
    )
    limit = float(paired[["process_only_pls", "process_oes_pls"]].to_numpy().max()) * 1.05
    pair_axis.plot([0, limit], [0, limit], "--", color=INK, linewidth=0.9)
    pair_axis.set_xlim(0, limit)
    pair_axis.set_ylim(0, limit)
    pair_axis.set_xlabel("Process-only wafer MAE (um)", fontsize=8)
    pair_axis.set_ylabel("Process + OES wafer MAE (um)", fontsize=8)
    pair_axis.set_title(
        "Every held-out wafer", loc="left", fontsize=12, fontweight="bold", color=INK
    )
    pair_axis.text(
        0.04,
        0.95,
        "Below diagonal: OES improves\nAbove diagonal: OES worsens",
        transform=pair_axis.transAxes,
        va="top",
        fontsize=8,
        color=MUTED,
    )
    pair_axis.spines[["top", "right"]].set_visible(False)
    pair_axis.grid(color="#D8DFE3", linewidth=0.7)
    pair_axis.tick_params(labelsize=8, colors=MUTED)

    figure.text(
        0.055,
        0.04,
        "Decision: do not download the remaining OES days under this raw fusion design. "
        "Evaluate compact, training-fold-only OES representations before any expansion.",
        fontsize=9,
        color=INK,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)

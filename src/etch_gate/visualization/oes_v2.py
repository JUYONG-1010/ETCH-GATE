"""Wafer-map dashboard for the physics-constrained OES V2 pilot."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from etch_gate.visualization.model_benchmark import plot_wafer_map

INK = "#17212B"
MUTED = "#66717E"
TEAL = "#007F7B"
CORAL = "#D9534F"


def plot_oes_v2_dashboard(
    points: pd.DataFrame,
    wafers: pd.DataFrame,
    summary: dict[str, object],
    output_path: Path,
) -> None:
    """Show full-map decision statistics and a deterministic held-out wafer map."""

    full = wafers[wafers["stage"] == "full_map"].copy()
    paired = full.pivot(
        index=["experiment_key", "lot_number"], columns="family", values="mae"
    ).reset_index()
    paired["improvement"] = paired["process_only_pls"] - paired["physics_constrained_oes_v2"]
    improved = paired[paired["improvement"] > 0].copy()
    pool = improved if not improved.empty else paired
    distance = (pool["improvement"] - pool["improvement"].median()).abs()
    example_key = pool.loc[distance.sort_values(kind="mergesort").index[0], "experiment_key"]
    example = points[
        (points["experiment_key"] == example_key) & (points["stage"] == "full_map")
    ].copy()
    process = example[example["family"] == "process_only_pls"]
    constrained = example[example["family"] == "physics_constrained_oes_v2"]
    observed = process.assign(display=process["observed"])
    value_min = min(observed["display"].min(), example["predicted"].min())
    value_max = max(observed["display"].max(), example["predicted"].max())
    error_limit = max(example["error"].abs().max(), 1e-6)
    lot = full.groupby(["lot_number", "family"])["mae"].mean().unstack("family")

    figure = plt.figure(figsize=(20, 11), facecolor="#F6F8F9")
    grid = figure.add_gridspec(2, 24, height_ratios=[0.72, 1.28], hspace=0.36, wspace=0.8)
    figure.suptitle(
        "Physics-constrained OES V2 does not improve unseen wafer maps",
        x=0.045,
        y=0.97,
        ha="left",
        fontsize=21,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.045,
        0.935,
        "OES predicts global mean shift only; process PLS predicts spatial residual | "
        "four held-out lots | lower MAE is better",
        fontsize=9.5,
        color=MUTED,
    )

    overall_axis = figure.add_subplot(grid[0, :6])
    values = [
        float(summary["process_only_lot_macro_mae"]),
        float(summary["physics_constrained_lot_macro_mae"]),
    ]
    bars = overall_axis.bar(["Process only", "OES V2"], values, color=[TEAL, CORAL], width=0.58)
    overall_axis.set_title("Lot-macro full-map MAE", loc="left", fontweight="bold", color=INK)
    overall_axis.set_ylabel("MAE (um)")
    overall_axis.set_ylim(0, max(values) * 1.3)
    overall_axis.spines[["top", "right"]].set_visible(False)
    overall_axis.grid(axis="y", color="#D8DFE3")
    overall_axis.set_axisbelow(True)
    for bar, value in zip(bars, values, strict=True):
        overall_axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.01,
            f"{value:.4f}",
            ha="center",
            fontweight="bold",
        )

    gate_axis = figure.add_subplot(grid[0, 7:13])
    gate_axis.axis("off")
    gate_axis.text(0, 0.86, "Pre-registered gate", fontsize=12, fontweight="bold", color=INK)
    gate_axis.text(
        0,
        0.56,
        f"Observed reduction: {100 * float(summary['lot_macro_relative_mae_reduction']):+.2f}%",
        fontsize=11,
        color=CORAL,
        fontweight="bold",
    )
    gate_axis.text(0, 0.34, "Required: +5.00%", fontsize=9, color=MUTED)
    gate_axis.text(
        0,
        0.13,
        f"Lots improved: {summary['lots_improved']}/4 (need 3/4)",
        fontsize=10,
        color=CORAL,
        fontweight="bold",
    )

    lot_axis = figure.add_subplot(grid[0, 14:])
    x = np.arange(len(lot.index))
    width = 0.35
    lot_axis.bar(x - width / 2, lot["process_only_pls"], width, label="Process only", color=TEAL)
    lot_axis.bar(
        x + width / 2, lot["physics_constrained_oes_v2"], width, label="OES V2", color=CORAL
    )
    lot_axis.set_xticks(x, [f"Lot {int(value)}" for value in lot.index])
    lot_axis.set_title("Held-out lot error", loc="left", fontweight="bold", color=INK)
    lot_axis.set_ylabel("Mean map MAE (um)")
    lot_axis.spines[["top", "right"]].set_visible(False)
    lot_axis.grid(axis="y", color="#D8DFE3")
    lot_axis.set_axisbelow(True)
    lot_axis.legend(frameon=False, fontsize=8)

    maps = [
        (observed, "display", "Measured map", "viridis", False),
        (process, "predicted", "Process-only prediction", "viridis", False),
        (constrained, "predicted", "Physics-constrained OES V2", "viridis", False),
        (process, "error", "Process-only error", "RdBu_r", True),
        (constrained, "error", "OES V2 error", "RdBu_r", True),
    ]
    map_grid = grid[1, :].subgridspec(1, 5, wspace=0.38)
    for index, (table, value, title, cmap, centered) in enumerate(maps):
        axis = figure.add_subplot(map_grid[0, index])
        plot_wafer_map(
            axis,
            table,
            value,
            title,
            cmap=cmap,
            vmin=-error_limit if centered else value_min,
            vmax=error_limit if centered else value_max,
            centered=centered,
        )
    figure.text(
        0.045,
        0.05,
        "Map rule: median improvement among OES-improved held-out wafers. "
        f"Selected wafer: {example_key}.",
        fontsize=9,
        color=MUTED,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)

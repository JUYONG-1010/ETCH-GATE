"""Wafer-map-centric visualization of VM target decomposition."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.tri import Triangulation

INK = "#17212b"
TEAL = "#008b87"
AMBER = "#eba514"
CORAL = "#dc554f"
GRID = "#d8e0e4"


def _wafer_map(
    axis: plt.Axes,
    frame: pd.DataFrame,
    value: str,
    *,
    title: str,
    minimum: float,
    maximum: float,
    cmap: str,
):
    triangulation = Triangulation(frame["X"], frame["Y"])
    contour = axis.tricontourf(
        triangulation,
        frame[value],
        levels=np.linspace(minimum, maximum, 18),
        cmap=cmap,
        extend="both",
    )
    axis.set_aspect("equal")
    axis.set_xticks([])
    axis.set_yticks([])
    axis.set_title(title, fontsize=9.5, fontweight="bold", color=INK)
    for spine in axis.spines.values():
        spine.set_visible(False)
    return contour


def plot_spatial_decomposition(
    points: pd.DataFrame,
    wafer_metrics: pd.DataFrame,
    stage_summary: pd.DataFrame,
    gate: dict[str, object],
    output: Path,
) -> None:
    """Show stage-level value and matched-scale wafer maps."""

    figure = plt.figure(figsize=(15, 9))
    grid = figure.add_gridspec(2, 5, height_ratios=[0.9, 1.1], hspace=0.34, wspace=0.20)
    axis = figure.add_subplot(grid[0, :3])
    order = [
        "template",
        "mean_shift",
        "full_map",
        "oracle_true_mean_zero_residual",
        "oracle_true_mean_pca_reconstruction",
    ]
    labels = ["Template", "+ predicted\nmean", "+ predicted\nresidual", "Oracle mean", "Oracle PCA"]
    ordered = stage_summary.set_index("stage").loc[order]
    colors = ["#aeb8be", AMBER, TEAL, "#9f89bd", "#6c5a8e"]
    axis.bar(labels, ordered["lot_macro_mae"], color=colors)
    for index, value in enumerate(ordered["lot_macro_mae"]):
        axis.text(index, value + 0.004, f"{value:.3f}", ha="center", fontsize=9)
    axis.set_ylabel("Lot-macro full-map MAE (um)")
    axis.set_title("Deployable stages and oracle upper bounds", loc="left", fontweight="bold")
    axis.grid(axis="y", color=GRID)
    axis.spines[["top", "right"]].set_visible(False)

    axis = figure.add_subplot(grid[0, 3:])
    stages = ["template", "mean_shift", "full_map"]
    residual = stage_summary.set_index("stage").loc[stages]
    x = np.arange(len(stages))
    axis.bar(x - 0.18, residual["mean_shift_mae"], width=0.36, color=AMBER, label="mean shift")
    axis.bar(x + 0.18, residual["residual_mae"], width=0.36, color=TEAL, label="residual profile")
    axis.set_xticks(x, ["Template", "+ mean", "+ residual"])
    axis.set_ylabel("Wafer-macro absolute error (um)")
    axis.set_title(
        f"Residual-stage gate: {gate['status']}",
        loc="left",
        fontweight="bold",
    )
    axis.legend(frameon=False)
    axis.grid(axis="y", color=GRID)
    axis.spines[["top", "right"]].set_visible(False)

    full_metrics = wafer_metrics[wafer_metrics["stage"] == "full_map"].sort_values(
        ["full_map_mae", "experiment_key"]
    )
    key = str(full_metrics.iloc[len(full_metrics) // 2]["experiment_key"])
    selected = points[points["experiment_key"] == key]
    observed = selected[selected["stage"] == "template"].copy()
    value_min = float(observed["observed"].min())
    value_max = float(observed["observed"].max())
    map_stages = [
        ("observed", "Measured"),
        ("template", "Template"),
        ("mean_shift", "+ predicted mean"),
        ("full_map", "+ predicted residual"),
    ]
    for column, (stage, title) in enumerate(map_stages):
        axis = figure.add_subplot(grid[1, column])
        frame = observed if stage == "observed" else selected[selected["stage"] == stage]
        value = "observed" if stage == "observed" else "predicted"
        contour = _wafer_map(
            axis,
            frame,
            value,
            title=title,
            minimum=value_min,
            maximum=value_max,
            cmap="viridis",
        )
        if column == 3:
            figure.colorbar(contour, ax=axis, shrink=0.72, label="Stepheight (um)")
    axis = figure.add_subplot(grid[1, 4])
    full = selected[selected["stage"] == "full_map"].copy()
    full["error"] = full["predicted"] - full["observed"]
    error_limit = float(np.max(np.abs(full["error"])))
    contour = _wafer_map(
        axis,
        full,
        "error",
        title="Final error",
        minimum=-error_limit,
        maximum=error_limit,
        cmap="RdBu_r",
    )
    figure.colorbar(contour, ax=axis, shrink=0.72, label="Error (um)")

    figure.suptitle(
        "Where does virtual-metrology improvement come from?",
        x=0.06,
        ha="left",
        fontsize=18,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.06,
        0.94,
        f"Matched-scale median-error wafer: {key}. Oracle stages are not deployable.",
        fontsize=10,
        color="#5c6973",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(figure)

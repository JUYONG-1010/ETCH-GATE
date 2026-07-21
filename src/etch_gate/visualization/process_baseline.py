"""Publication-style figures for process-feature virtual metrology."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from scipy.interpolate import griddata

from etch_gate.data.process import (
    LONG_PHASE_GAS,
    SHORT_PHASE_GAS,
    SOURCE_RF,
    ProcessTrace,
    detect_process_regions,
)

INK = "#17212B"
MUTED = "#66717E"
TEAL = "#007F7B"
CORAL = "#E45C3A"
GOLD = "#E8A317"
PALE = "#EFF3F5"


def _wafer_field(
    axis: plt.Axes,
    table: pd.DataFrame,
    value: str,
    title: str,
    *,
    cmap: str,
    vmin: float | None = None,
    vmax: float | None = None,
    centered: bool = False,
) -> None:
    x = table["X"].to_numpy(dtype=float)
    y = table["Y"].to_numpy(dtype=float)
    z = table[value].to_numpy(dtype=float)
    grid_x, grid_y = np.mgrid[x.min() : x.max() : 220j, y.min() : y.max() : 220j]
    grid_z = griddata((x, y), z, (grid_x, grid_y), method="cubic")
    radius = min(x.max() - x.min(), y.max() - y.min()) / 2
    center_x, center_y = (x.min() + x.max()) / 2, (y.min() + y.max()) / 2
    grid_z[(grid_x - center_x) ** 2 + (grid_y - center_y) ** 2 > radius**2] = np.nan
    norm = None
    if centered:
        limit = max(abs(np.nanmin(grid_z)), abs(np.nanmax(grid_z)))
        norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
    image = axis.imshow(
        grid_z.T,
        origin="lower",
        extent=(x.min(), x.max(), y.min(), y.max()),
        cmap=cmap,
        vmin=None if norm else vmin,
        vmax=None if norm else vmax,
        norm=norm,
    )
    scatter_limits = {} if norm else {"vmin": vmin, "vmax": vmax}
    axis.scatter(x, y, c=z, cmap=cmap, norm=norm, s=8, **scatter_limits)
    axis.add_patch(
        plt.Circle((center_x, center_y), radius, fill=False, color=INK, linewidth=1.0)
    )
    axis.set_title(title, loc="left", fontsize=10, fontweight="bold", color=INK)
    axis.set_aspect("equal")
    axis.axis("off")
    colorbar = axis.figure.colorbar(image, ax=axis, fraction=0.045, pad=0.02)
    colorbar.ax.tick_params(labelsize=7, colors=MUTED)


def plot_process_cycle_atlas(trace: ProcessTrace, output_path: Path) -> None:
    """Show the active RF window and detected anonymous long/short phases."""

    regions = detect_process_regions(trace)
    active = regions.active
    time = trace.times - regions.active_start_seconds
    figure, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True)
    figure.patch.set_facecolor("#F7F9FA")
    figure.suptitle(
        "From raw chamber trace to cycle-aware process features",
        x=0.06,
        y=0.97,
        ha="left",
        fontsize=20,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.06,
        0.925,
        (
            f"{trace.experiment_key}  |  {regions.cycle_count} detected cycles  |  "
            "channel identities remain anonymized"
        ),
        color=MUTED,
        fontsize=10,
    )

    signals = [
        (SOURCE_RF, "Source RF load power", TEAL),
        (LONG_PHASE_GAS, "Long-pulse gas channel (Gas5)", CORAL),
        (SHORT_PHASE_GAS, "Short-pulse gas channel (Gas4)", GOLD),
    ]
    for axis, (signal, label, color) in zip(axes, signals, strict=True):
        axis.plot(time[active], trace.values.loc[active, signal], color=color, linewidth=1.3)
        axis.set_ylabel(label, fontsize=9, color=INK)
        axis.grid(axis="y", color="#D8DFE3", linewidth=0.7)
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.tick_params(colors=MUTED, labelsize=8)
        axis.set_facecolor("#F7F9FA")

    for cycle in range(regions.cycle_count):
        indices = np.flatnonzero(regions.cycle_index == cycle)
        if len(indices) and cycle % 10 == 0:
            axes[-1].axvline(time[indices[0]], color="#9AA5AE", linewidth=0.7, alpha=0.6)
    axes[-1].set_xlabel("Seconds from detected process start", color=INK)
    figure.text(
        0.74,
        0.925,
        "No rows are resampled; slopes use recorded timestamps.",
        color=TEAL,
        fontsize=9,
        fontweight="bold",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)


def plot_process_model_dashboard(
    point_results: pd.DataFrame,
    wafer_metrics: pd.DataFrame,
    output_path: Path,
) -> None:
    """Summarize lot robustness and one representative dense-map prediction."""

    family_summary = (
        wafer_metrics.groupby(["family", "stage"])["mae"].mean().unstack()
    )
    best_family = family_summary["full_map"].idxmin()
    selected = wafer_metrics[wafer_metrics["family"] == best_family]
    means = selected.groupby("stage")["mae"].mean()
    reduction = 100 * (1 - means["full_map"] / means["template"])
    full = selected[selected["stage"] == "full_map"].sort_values("mae")
    representative_key = full.iloc[len(full) // 2]["experiment_key"]

    points = point_results[
        (point_results["family"] == best_family)
        & (point_results["experiment_key"] == representative_key)
    ]
    template = points[points["stage"] == "template"].copy()
    mean_shift = points[points["stage"] == "mean_shift"].copy()
    full_map = points[points["stage"] == "full_map"].copy()
    value_min = min(points["observed"].min(), points["predicted"].min())
    value_max = max(points["observed"].max(), points["predicted"].max())

    figure = plt.figure(figsize=(18, 10), facecolor="#F7F9FA")
    grid = figure.add_gridspec(2, 10, height_ratios=[0.9, 1.1], hspace=0.32, wspace=0.42)
    figure.suptitle(
        "Can chamber signals improve a spatial-template baseline?",
        x=0.055,
        y=0.975,
        ha="left",
        fontsize=21,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.055,
        0.935,
        (
            f"Nested leave-one-lot-out validation  |  88 wafers, 10 lots  |  "
            f"best family: {best_family.upper()}"
        ),
        fontsize=10,
        color=MUTED,
    )
    figure.text(
        0.77,
        0.948,
        f"{reduction:.1f}% lower MAE",
        fontsize=16,
        fontweight="bold",
        color=TEAL,
    )
    figure.text(
        0.77,
        0.925,
        "full process model vs template",
        fontsize=9,
        color=MUTED,
    )

    metric_axis = figure.add_subplot(grid[0, :5])
    stages = ["template", "mean_shift", "full_map"]
    labels = ["Template only", "+ predicted wafer mean", "+ predicted residual shape"]
    colors = ["#AAB4BC", GOLD, TEAL]
    values = [means[stage] for stage in stages]
    bars = metric_axis.barh(labels, values, color=colors, height=0.55)
    metric_axis.invert_yaxis()
    metric_axis.set_xlabel("Mean absolute error (µm, lower is better)", color=INK)
    metric_axis.spines[["top", "right", "left"]].set_visible(False)
    metric_axis.grid(axis="x", color="#D8DFE3", linewidth=0.7)
    metric_axis.set_axisbelow(True)
    metric_axis.tick_params(colors=MUTED)
    metric_axis.set_facecolor("#F7F9FA")
    for bar, value in zip(bars, values, strict=True):
        metric_axis.text(
            value + max(values) * 0.025,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.3f}",
            va="center",
            fontsize=10,
            fontweight="bold",
            color=INK,
        )

    lot_axis = figure.add_subplot(grid[0, 5:])
    lot_values = (
        selected.groupby(["lot_number", "stage"])["mae"].mean().unstack()
    )
    x = np.arange(len(lot_values))
    lot_axis.plot(x, lot_values["template"], "o-", color="#AAB4BC", label="Template")
    lot_axis.plot(x, lot_values["mean_shift"], "o-", color=GOLD, label="+ mean")
    lot_axis.plot(x, lot_values["full_map"], "o-", color=TEAL, label="+ residual")
    lot_axis.set_xticks(x, [f"L{int(lot)}" for lot in lot_values.index])
    lot_axis.set_ylabel("Lot mean MAE (µm)", color=INK)
    lot_axis.set_title("Held-out lot consistency", loc="left", color=INK, fontweight="bold")
    lot_axis.spines[["top", "right"]].set_visible(False)
    lot_axis.grid(axis="y", color="#D8DFE3", linewidth=0.7)
    lot_axis.legend(frameon=False, ncol=3, fontsize=8)
    lot_axis.tick_params(colors=MUTED, labelsize=8)
    lot_axis.set_facecolor("#F7F9FA")

    observed_table = full_map.assign(predicted=full_map["observed"])
    map_tables = [
        (observed_table, "predicted", "Measured map", "viridis", False),
        (template, "predicted", "Template only", "viridis", False),
        (mean_shift, "predicted", "+ process mean", "viridis", False),
        (full_map, "predicted", "Final prediction", "viridis", False),
        (full_map, "error", "Final error", "RdBu_r", True),
    ]
    for column, (table, value, title, cmap, centered) in enumerate(map_tables):
        axis = figure.add_subplot(grid[1, 2 * column : 2 * column + 2])
        _wafer_field(
            axis,
            table,
            value,
            title,
            cmap=cmap,
            vmin=value_min,
            vmax=value_max,
            centered=centered,
        )
    figure.text(
        0.055,
        0.045,
        (
            f"Representative held-out wafer: {representative_key}. "
            "Every displayed prediction was produced without using its lot for fitting."
        ),
        fontsize=9,
        color=MUTED,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)

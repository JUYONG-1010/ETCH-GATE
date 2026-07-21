"""Readable failure-analysis figures for held-out lots."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

INK = "#17212B"
MUTED = "#66717E"
TEAL = "#007F7B"
CORAL = "#E45C3A"
GOLD = "#E8A317"
GRID = "#D8DFE3"
BACKGROUND = "#F7F9FA"


def _short_feature_name(name: str) -> str:
    signal, statistic = name.split("__", maxsplit=1)
    signal = signal.removeprefix("Stat3_Etch_MV_")
    return f"{signal} | {statistic}"


def plot_lot_failure_atlas(
    wafer_summary: pd.DataFrame,
    z_scores: pd.DataFrame,
    output_path: Path,
    *,
    lot_number: int,
) -> None:
    """Plot sequence reversal, stage errors, and unusual process features."""

    figure = plt.figure(figsize=(16, 10), facecolor=BACKGROUND)
    grid = figure.add_gridspec(2, 2, height_ratios=[0.9, 1.15], hspace=0.34, wspace=0.24)
    figure.suptitle(
        f"Why did the process model fail on Lot {lot_number}?",
        x=0.055,
        y=0.97,
        ha="left",
        fontsize=21,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.055,
        0.928,
        (
            "The dominant error is a wafer-sequence mean-shift reversal, "
            "not a failure to reconstruct the fixed spatial template."
        ),
        fontsize=10,
        color=MUTED,
    )

    order = wafer_summary["wafer_order"].to_numpy()
    shift_axis = figure.add_subplot(grid[0, 0])
    shift_axis.axhline(0, color=GRID, linewidth=1)
    shift_axis.plot(
        order,
        wafer_summary["true_mean_shift"],
        "o-",
        color=INK,
        linewidth=2,
        label="Measured mean shift",
    )
    shift_axis.plot(
        order,
        wafer_summary["predicted_mean_shift"],
        "o-",
        color=CORAL,
        linewidth=2,
        label="PLS prediction",
    )
    shift_axis.axvspan(7.5, 10.5, color=CORAL, alpha=0.08)
    shift_axis.text(
        8.05,
        shift_axis.get_ylim()[0] * 0.82,
        "prediction direction diverges",
        color=CORAL,
        fontsize=9,
        fontweight="bold",
    )
    shift_axis.set_title("A. Wafer-order drift", loc="left", color=INK, fontweight="bold")
    shift_axis.set_xlabel("Wafer order within Lot 8", color=INK)
    shift_axis.set_ylabel("Mean shift from template (um)", color=INK)
    shift_axis.set_xticks(order)
    shift_axis.legend(frameon=False, fontsize=9)

    error_axis = figure.add_subplot(grid[0, 1])
    error_axis.plot(
        order,
        wafer_summary["template_mae"],
        "o-",
        color="#AAB4BC",
        label="Template",
    )
    error_axis.plot(
        order,
        wafer_summary["mean_shift_mae"],
        "o-",
        color=GOLD,
        label="+ predicted mean",
    )
    error_axis.plot(
        order,
        wafer_summary["full_map_mae"],
        "o-",
        color=TEAL,
        label="+ residual shape",
    )
    error_axis.axvspan(7.5, 10.5, color=CORAL, alpha=0.08)
    error_axis.set_title(
        "B. Error by prediction stage", loc="left", color=INK, fontweight="bold"
    )
    error_axis.set_xlabel("Wafer order within Lot 8", color=INK)
    error_axis.set_ylabel("89-point MAE (um)", color=INK)
    error_axis.set_xticks(order)
    error_axis.legend(frameon=False, fontsize=9)

    heat_axis = figure.add_subplot(grid[1, :])
    matrix = z_scores.T.to_numpy()
    limit = max(3.0, float(np.nanmax(np.abs(matrix))))
    image = heat_axis.imshow(
        matrix,
        aspect="auto",
        cmap="RdBu_r",
        norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit),
    )
    heat_axis.set_xticks(
        np.arange(len(z_scores)),
        [str(value) for value in order],
    )
    heat_axis.set_yticks(
        np.arange(len(z_scores.columns)),
        [_short_feature_name(name) for name in z_scores.columns],
        fontsize=8,
    )
    heat_axis.set_xlabel("Wafer order within Lot 8", color=INK)
    heat_axis.set_title(
        "C. Largest process-feature departures from other-lot training data",
        loc="left",
        color=INK,
        fontweight="bold",
    )
    colorbar = figure.colorbar(image, ax=heat_axis, fraction=0.018, pad=0.015)
    colorbar.set_label("Training-standardized value (z-score)", color=INK)
    for axis in (shift_axis, error_axis):
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", color=GRID, linewidth=0.7)
        axis.tick_params(colors=MUTED)
        axis.set_facecolor(BACKGROUND)
    heat_axis.tick_params(colors=MUTED)

    figure.text(
        0.055,
        0.025,
        (
            "Evidence boundary: the public metadata documents conditioning-induced "
            "drift and a repeated 3C-SiO2 experiment, but does not identify a specific "
            "physical fault for wafers 8-10."
        ),
        fontsize=9,
        color=MUTED,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=BACKGROUND)
    plt.close(figure)

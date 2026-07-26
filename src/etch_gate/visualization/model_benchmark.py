"""Visual audit of Ridge, PLS, and GPR process models."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from scipy.interpolate import griddata

INK = "#17212B"
MUTED = "#66717E"
TEAL = "#007F7B"
CORAL = "#E45C3A"
GOLD = "#E8A317"
PALE = "#F3F6F7"


def _wafer_map(
    axis: plt.Axes,
    table: pd.DataFrame,
    value: str,
    title: str,
    *,
    cmap: str,
    vmin: float,
    vmax: float,
    centered: bool = False,
) -> None:
    x = table["X"].to_numpy(dtype=float)
    y = table["Y"].to_numpy(dtype=float)
    z = table[value].to_numpy(dtype=float)
    gx, gy = np.mgrid[x.min() : x.max() : 180j, y.min() : y.max() : 180j]
    gz = griddata((x, y), z, (gx, gy), method="cubic")
    radius = min(x.max() - x.min(), y.max() - y.min()) / 2
    cx, cy = (x.min() + x.max()) / 2, (y.min() + y.max()) / 2
    gz[(gx - cx) ** 2 + (gy - cy) ** 2 > radius**2] = np.nan
    norm = TwoSlopeNorm(vmin=vmin, vcenter=0.0, vmax=vmax) if centered else None
    image = axis.imshow(
        gz.T,
        origin="lower",
        extent=(x.min(), x.max(), y.min(), y.max()),
        cmap=cmap,
        vmin=None if centered else vmin,
        vmax=None if centered else vmax,
        norm=norm,
    )
    axis.scatter(x, y, c=z, cmap=cmap, norm=norm, vmin=None if centered else vmin,
                 vmax=None if centered else vmax, s=5)
    axis.add_patch(plt.Circle((cx, cy), radius, fill=False, color=INK, linewidth=0.9))
    axis.set_title(title, fontsize=10, fontweight="bold", color=INK, pad=7)
    axis.set_aspect("equal")
    axis.axis("off")
    colorbar = axis.figure.colorbar(image, ax=axis, fraction=0.045, pad=0.02)
    colorbar.ax.tick_params(labelsize=6, colors=MUTED)


def plot_model_benchmark_dashboard(
    point_predictions: pd.DataFrame,
    wafer_metrics: pd.DataFrame,
    model_summary: pd.DataFrame,
    audit: dict[str, object],
    output_path: Path,
) -> None:
    """Show accuracy, lot robustness, uncertainty, and the Lot 8 failure map."""

    full = wafer_metrics[wafer_metrics["stage"] == "full_map"].copy()
    order = ["ridge", "pls", "gpr"]
    summary = model_summary.set_index("family").loc[order]
    lot_wide = full.groupby(["lot_number", "family"])["mae"].mean().unstack()[order]
    paired = full.pivot(
        index=["experiment_key", "lot_number"],
        columns="family",
        values="mae",
    ).reset_index()
    gpr = full[full["family"] == "gpr"]

    lot8_pls = full[(full["family"] == "pls") & (full["lot_number"] == 8)]
    example_key = lot8_pls.nlargest(1, "mae")["experiment_key"].iloc[0]
    example = point_predictions[
        (point_predictions["experiment_key"] == example_key)
        & (point_predictions["stage"] == "full_map")
        & (point_predictions["family"].isin(["pls", "gpr"]))
    ]
    pls_points = example[example["family"] == "pls"].copy()
    gpr_points = example[example["family"] == "gpr"].copy()
    observed = pls_points.assign(display=pls_points["observed"])
    prediction_min = min(observed["observed"].min(), example["predicted"].min())
    prediction_max = max(observed["observed"].max(), example["predicted"].max())
    error_limit = max(example["error"].abs().max(), 1e-6)

    figure = plt.figure(figsize=(20, 12), facecolor="#F7F9FA")
    grid = figure.add_gridspec(
        2,
        24,
        height_ratios=[0.82, 1.18],
        hspace=0.28,
        wspace=0.8,
    )
    figure.suptitle(
        "Simple latent regression beats nonlinear GPR on unseen lots",
        x=0.045,
        y=0.975,
        ha="left",
        fontsize=22,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.045,
        0.94,
        (
            "Nested leave-one-lot-out | 88 wafers | direct 89-point P-17 "
            "stepheight | lower MAE is better"
        ),
        fontsize=10,
        color=MUTED,
    )
    figure.text(
        0.79,
        0.958,
        f"PLS  {summary.loc['pls', 'wafer_macro_mae']:.4f} um",
        fontsize=15,
        color=TEAL,
        fontweight="bold",
    )
    figure.text(
        0.79,
        0.936,
        f"GPR is {100 * float(audit['gpr_relative_mae_change_vs_pls']):.1f}% worse",
        fontsize=9,
        color=CORAL,
    )

    metric_axis = figure.add_subplot(grid[0, :5])
    colors = ["#8B98A3", TEAL, CORAL]
    bars = metric_axis.bar(order, summary["wafer_macro_mae"], color=colors, width=0.62)
    metric_axis.set_title("Overall full-map error", loc="left", fontweight="bold", color=INK)
    metric_axis.set_ylabel("Wafer-macro MAE (um)", color=INK)
    metric_axis.spines[["top", "right"]].set_visible(False)
    metric_axis.grid(axis="y", color="#D8DFE3", linewidth=0.7)
    metric_axis.set_axisbelow(True)
    metric_axis.tick_params(colors=MUTED)
    for bar, value in zip(bars, summary["wafer_macro_mae"], strict=True):
        metric_axis.text(bar.get_x() + bar.get_width() / 2, value + 0.003, f"{value:.4f}",
                         ha="center", fontsize=9, fontweight="bold", color=INK)

    lot_axis = figure.add_subplot(grid[0, 5:12])
    lot_axis.imshow(lot_wide.T, cmap="YlGnBu", aspect="auto")
    lot_axis.set_title("Error carried lot by lot", loc="left", fontweight="bold", color=INK)
    lot_axis.set_xticks(np.arange(len(lot_wide)), [f"L{int(lot)}" for lot in lot_wide.index])
    lot_axis.set_yticks(np.arange(len(order)), [name.upper() for name in order])
    lot_axis.tick_params(labelsize=8, colors=MUTED)
    for row in range(len(order)):
        for column in range(len(lot_wide)):
            value = lot_wide.iloc[column, row]
            lot_axis.text(column, row, f"{value:.3f}", ha="center", va="center",
                          fontsize=7, color="white" if value > 0.18 else INK)

    paired_axis = figure.add_subplot(grid[0, 12:17])
    normal = paired[paired["lot_number"] != 8]
    drift = paired[paired["lot_number"] == 8]
    paired_axis.scatter(normal["pls"], normal["gpr"], s=22, color="#7C8A95", alpha=0.75)
    paired_axis.scatter(drift["pls"], drift["gpr"], s=38, color=CORAL, label="Lot 8")
    limit = max(paired[["pls", "gpr"]].max()) * 1.06
    paired_axis.plot([0, limit], [0, limit], linestyle="--", color=INK, linewidth=0.9)
    paired_axis.set_xlim(0, limit)
    paired_axis.set_ylim(0, limit)
    paired_axis.set_xlabel("PLS wafer MAE", fontsize=8)
    paired_axis.set_ylabel("GPR wafer MAE", fontsize=8)
    paired_axis.set_title("Each wafer", loc="left", fontweight="bold", color=INK)
    paired_axis.spines[["top", "right"]].set_visible(False)
    paired_axis.grid(color="#D8DFE3", linewidth=0.6)
    paired_axis.legend(frameon=False, fontsize=7)
    paired_axis.tick_params(labelsize=7, colors=MUTED)

    uncertainty_axis = figure.add_subplot(grid[0, 17:])
    uncertainty_axis.scatter(
        gpr["mean_predicted_std"],
        gpr["mae"],
        c=gpr["lot_number"],
        cmap="tab10",
        s=30,
        alpha=0.8,
    )
    uncertainty_axis.set_title(
        "Raw GPR uncertainty fails",
        loc="left",
        fontweight="bold",
        color=INK,
    )
    uncertainty_axis.set_xlabel("Mean predicted standard deviation (um)", fontsize=8)
    uncertainty_axis.set_ylabel("Observed wafer MAE (um)", fontsize=8)
    uncertainty_axis.text(
        0.04,
        0.95,
        f"Spearman rho = {float(audit['gpr_uncertainty_wafer_mae_spearman_rho']):.3f}\n"
        f"Top-20% capture = {100 * float(audit['gpr_top_20_percent_error_capture']):.1f}%",
        transform=uncertainty_axis.transAxes,
        va="top",
        fontsize=8,
        color=CORAL,
        fontweight="bold",
    )
    uncertainty_axis.spines[["top", "right"]].set_visible(False)
    uncertainty_axis.grid(color="#D8DFE3", linewidth=0.6)
    uncertainty_axis.tick_params(labelsize=7, colors=MUTED)

    map_tables = [
        (observed, "display", "Measured Lot 8 map", "viridis", False),
        (pls_points, "predicted", "PLS prediction", "viridis", False),
        (gpr_points, "predicted", "GPR prediction", "viridis", False),
        (pls_points, "error", "PLS error", "RdBu_r", True),
        (gpr_points, "error", "GPR error", "RdBu_r", True),
    ]
    map_grid = grid[1, :].subgridspec(1, 5, wspace=0.35)
    for index, (table, value, title, cmap, centered) in enumerate(map_tables):
        axis = figure.add_subplot(map_grid[0, index])
        _wafer_map(
            axis,
            table,
            value,
            title,
            cmap=cmap,
            vmin=-error_limit if centered else prediction_min,
            vmax=error_limit if centered else prediction_max,
            centered=centered,
        )
    figure.text(
        0.045,
        0.055,
        (
            f"Failure case: {example_key}. GPR kernel optimization and PCA selection used "
            "training lots only; raw GPR variance is not a calibrated interval."
        ),
        fontsize=9,
        color=MUTED,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)

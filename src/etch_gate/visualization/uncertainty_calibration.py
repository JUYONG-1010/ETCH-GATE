"""Coverage-width visualization for dense-map conformal intervals."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Circle


def plot_coverage_width_dashboard(
    summary: pd.DataFrame,
    lot_coverage: pd.DataFrame,
    points: pd.DataFrame,
    output_path: Path,
) -> None:
    """Show marginal and simultaneous calibration with a wafer-level miss map."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(16, 11), facecolor="#F4F6F3")
    grid = fig.add_gridspec(2, 2, hspace=0.33, wspace=0.26)
    axes = [fig.add_subplot(grid[row, column]) for row in range(2) for column in range(2)]
    for axis in axes:
        axis.set_facecolor("white")
        axis.spines[["top", "right"]].set_visible(False)
    ax_coverage, ax_width, ax_lots, ax_map = axes

    nominal = summary["nominal_coverage"].to_numpy()
    ax_coverage.plot(
        nominal,
        nominal,
        color="#9AA3AE",
        linestyle="--",
        label="Ideal",
    )
    ax_coverage.plot(
        nominal,
        summary["point_empirical_coverage"],
        color="#237A8B",
        marker="o",
        linewidth=3,
        label="Point-wise",
    )
    ax_coverage.plot(
        nominal,
        summary["simultaneous_map_coverage"],
        color="#E46C4C",
        marker="s",
        linewidth=3,
        label="Simultaneous map",
    )
    ax_coverage.set_xlim(0.75, 1.0)
    ax_coverage.set_ylim(0, 1.02)
    ax_coverage.set_xlabel("Nominal coverage")
    ax_coverage.set_ylabel("Empirical coverage")
    ax_coverage.set_title("A  Nominal coverage is not guaranteed by appearance", loc="left")
    ax_coverage.grid(color="#E7EBE8")
    ax_coverage.legend(frameon=False)

    ax_width.plot(
        nominal,
        summary["mean_point_interval_width"],
        color="#237A8B",
        marker="o",
        linewidth=3,
        label="Point-wise full width",
    )
    ax_width.plot(
        nominal,
        summary["mean_simultaneous_interval_width"],
        color="#E46C4C",
        marker="s",
        linewidth=3,
        label="Simultaneous full width",
    )
    ax_width.axhline(
        2 * summary["mean_template_baseline_mae"].mean(),
        color="#9AA3AE",
        linestyle="--",
        label="2 x template baseline MAE",
    )
    ax_width.set_xlabel("Nominal coverage")
    ax_width.set_ylabel("Mean interval width (um)")
    ax_width.set_title("B  Coverage-width tradeoff", loc="left")
    ax_width.grid(color="#E7EBE8")
    ax_width.legend(frameon=False, fontsize=9)

    offsets = {0.8: -0.015, 0.9: 0.0, 0.95: 0.015}
    for coverage in sorted(lot_coverage["nominal_coverage"].unique()):
        group = lot_coverage[lot_coverage["nominal_coverage"] == coverage]
        x = group["test_lot"].to_numpy() + offsets.get(float(coverage), 0)
        ax_lots.scatter(
            x,
            group["point_empirical_coverage"],
            s=80,
            label=f"{coverage:.0%} point",
        )
        ax_lots.scatter(
            x,
            group["simultaneous_map_coverage"],
            s=80,
            marker="x",
            linewidths=2,
            label=f"{coverage:.0%} map",
        )
    ax_lots.set_xticks(sorted(lot_coverage["test_lot"].unique()))
    ax_lots.set_ylim(-0.03, 1.03)
    ax_lots.set_xlabel("Strictly later test lot")
    ax_lots.set_ylabel("Empirical coverage")
    ax_lots.set_title("C  Lot-to-lot coverage instability", loc="left")
    ax_lots.grid(color="#E7EBE8")
    ax_lots.legend(frameon=False, ncol=2, fontsize=8)

    selected_nominal = 0.9 if 0.9 in set(points["nominal_coverage"]) else nominal[0]
    candidates = points[points["nominal_coverage"] == selected_nominal]
    wafer_scores = candidates.groupby("experiment_key")["absolute_error"].mean()
    key = str(wafer_scores.idxmax())
    wafer = candidates[candidates["experiment_key"] == key]
    colors = np.where(wafer["point_covered"], "#2A9D8F", "#E46C4C")
    sizes = 80 + 500 * wafer["absolute_error"] / wafer["absolute_error"].max()
    ax_map.scatter(
        wafer["X"],
        wafer["Y"],
        c=colors,
        s=sizes,
        edgecolors="white",
        linewidths=0.8,
    )
    radius = float(np.hypot(wafer["X"], wafer["Y"]).max())
    ax_map.add_patch(
        Circle((0, 0), radius * 1.04, fill=False, color="#172A3A", linewidth=1.4)
    )
    ax_map.set_aspect("equal")
    ax_map.set_xlabel("X (mm)")
    ax_map.set_ylabel("Y (mm)")
    ax_map.set_title(
        f"D  {selected_nominal:.0%} point interval | green covered, red missed",
        loc="left",
    )

    resolution = summary["mean_coverage_resolution"].max()
    attainable = summary.loc[
        summary["nominal_coverage"] == summary["nominal_coverage"].max(),
        "attainable_lot_fraction",
    ].iloc[0]
    fig.text(
        0.055,
        0.965,
        "ETCH-GATE | GROUP-AWARE CONFORMAL AUDIT",
        fontsize=20,
        weight="bold",
        color="#172A3A",
    )
    fig.text(
        0.055,
        0.934,
        f"Calibration resolution up to {resolution:.1%}; "
        f"highest nominal level attainable in {attainable:.0%} of lots",
        fontsize=11,
        color="#52616B",
    )
    fig.text(
        0.055,
        0.025,
        "Fit lots < calibration lot < test lot. Test targets never set interval width.",
        fontsize=9,
        color="#66747D",
    )
    fig.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

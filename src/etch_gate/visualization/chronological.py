"""LOLO-versus-forward VM dashboard with wafer-map evidence."""

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


def _map(
    axis: plt.Axes,
    frame: pd.DataFrame,
    column: str,
    title: str,
    minimum: float,
    maximum: float,
    cmap: str,
):
    contour = axis.tricontourf(
        Triangulation(frame["X"], frame["Y"]),
        frame[column],
        levels=np.linspace(minimum, maximum, 18),
        cmap=cmap,
        extend="both",
    )
    axis.set_aspect("equal")
    axis.set_xticks([])
    axis.set_yticks([])
    axis.set_title(title, fontsize=10, fontweight="bold", color=INK)
    for spine in axis.spines.values():
        spine.set_visible(False)
    return contour


def plot_lolo_vs_forward_dashboard(
    comparison: pd.DataFrame,
    points: pd.DataFrame,
    wafers: pd.DataFrame,
    output: Path,
) -> None:
    """Show deployment degradation and a deterministic forward-test wafer."""

    figure = plt.figure(figsize=(15, 8.5))
    grid = figure.add_gridspec(2, 4, hspace=0.40, wspace=0.30)
    axis = figure.add_subplot(grid[0, :2])
    lot_rows = comparison[comparison["scope"] == "lot"]
    for family, color in (("pls", TEAL), ("ridge", AMBER), ("gpr", CORAL)):
        family_rows = lot_rows[lot_rows["family"] == family]
        if family_rows.empty:
            continue
        axis.plot(
            family_rows["lot_number"],
            family_rows["chronological_mae"],
            marker="o",
            color=color,
            label=f"{family.upper()} forward",
        )
        axis.plot(
            family_rows["lot_number"],
            family_rows["lolo_mae"],
            linestyle="--",
            alpha=0.55,
            color=color,
            label=f"{family.upper()} LOLO",
        )
    axis.set(
        title="Same held-out lots, different information availability",
        xlabel="Test lot",
        ylabel="Full-map MAE (um)",
        xticks=sorted(lot_rows["lot_number"].unique()),
    )
    axis.grid(color=GRID)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False, ncol=2, fontsize=8)

    axis = figure.add_subplot(grid[0, 2:])
    macro = comparison[comparison["scope"] == "macro"].copy()
    x = np.arange(len(macro))
    axis.bar(x - 0.18, macro["lolo_mae"], width=0.36, color="#aeb8be", label="LOLO")
    axis.bar(
        x + 0.18,
        macro["chronological_mae"],
        width=0.36,
        color=CORAL,
        label="Forward",
    )
    axis.set_xticks(x, macro["family"].str.upper())
    axis.set_ylabel("Eligible-lot macro MAE (um)")
    axis.set_title("Temporal deployment penalty", loc="left", fontweight="bold")
    axis.grid(axis="y", color=GRID)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False)

    pls_full = wafers[
        (wafers["family"] == "pls") & (wafers["stage"] == "full_map")
    ].sort_values(["mae", "experiment_key"])
    key = str(pls_full.iloc[len(pls_full) // 2]["experiment_key"])
    selected = points[
        (points["experiment_key"] == key) & (points["family"] == "pls")
    ]
    full = selected[selected["stage"] == "full_map"].copy()
    template = selected[selected["stage"] == "template"].copy()
    full["error"] = full["predicted"] - full["observed"]
    value_min = float(full["observed"].min())
    value_max = float(full["observed"].max())
    error_limit = float(np.abs(full["error"]).max())
    maps = [
        (full, "observed", "Measured", value_min, value_max, "viridis"),
        (template, "predicted", "Past-lot template", value_min, value_max, "viridis"),
        (full, "predicted", "Forward PLS", value_min, value_max, "viridis"),
        (full, "error", "Forward error", -error_limit, error_limit, "RdBu_r"),
    ]
    for column, (frame, value, title, minimum, maximum, cmap) in enumerate(maps):
        axis = figure.add_subplot(grid[1, column])
        contour = _map(axis, frame, value, title, minimum, maximum, cmap)
        if column in {2, 3}:
            label = "Stepheight (um)" if column == 2 else "Error (um)"
            figure.colorbar(contour, ax=axis, shrink=0.72, label=label)

    figure.suptitle(
        "LOLO generalization is not chronological deployment",
        x=0.06,
        ha="left",
        fontsize=18,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.06,
        0.94,
        f"Forward folds train only on earlier lots. Median forward-PLS wafer: {key}.",
        fontsize=10,
        color="#5c6973",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(figure)

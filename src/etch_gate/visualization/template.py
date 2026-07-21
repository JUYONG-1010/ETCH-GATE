"""Publication figures for lot-aware target and template analysis."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from scipy.interpolate import griddata

BACKGROUND = "#F5F7F8"
INK = "#15232B"
MUTED = "#60717A"
GRID = "#D6DEE2"
TEAL = "#007F78"
CYAN = "#29A8B7"
CORAL = "#E0604F"
GOLD = "#D8A42B"
BLUE = "#3977B8"
TARGET_LABELS = {
    "stepheight": "Stepheight",
    "oxide_etch": "Oxide etch",
    "si_etch": "Silicon etch",
}


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": BACKGROUND,
            "axes.facecolor": BACKGROUND,
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": INK,
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "bold",
        }
    )


def _finish(figure: Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=BACKGROUND)
    plt.close(figure)


def _wafer_map(
    axis: plt.Axes,
    frame: pd.DataFrame,
    value_column: str,
    title: str,
    *,
    color_map: str,
    minimum: float,
    maximum: float,
    center_text: str | None = None,
) -> matplotlib.cm.ScalarMappable:
    x = frame["X"].to_numpy(dtype=float) / 1000
    y = frame["Y"].to_numpy(dtype=float) / 1000
    values = frame[value_column].to_numpy(dtype=float)
    grid_axis = np.linspace(-100, 100, 241)
    grid_x, grid_y = np.meshgrid(grid_axis, grid_axis)
    grid_values = griddata((x, y), values, (grid_x, grid_y), method="cubic")
    nearest_values = griddata((x, y), values, (grid_x, grid_y), method="nearest")
    grid_values = np.where(np.isfinite(grid_values), grid_values, nearest_values)
    grid_values = np.ma.masked_where(grid_x**2 + grid_y**2 > 100**2, grid_values)
    levels = np.linspace(minimum, maximum, 64)
    image = axis.contourf(
        grid_x,
        grid_y,
        grid_values,
        levels=levels,
        cmap=color_map,
        vmin=minimum,
        vmax=maximum,
        extend="both",
    )
    axis.scatter(
        x,
        y,
        s=8,
        color=INK,
        edgecolors=BACKGROUND,
        linewidths=0.35,
        alpha=0.72,
        zorder=3,
    )
    axis.add_patch(Circle((0, 0), 100, fill=False, edgecolor=INK, linewidth=1.6))
    axis.axhline(0, color=INK, linewidth=0.6, alpha=0.35)
    axis.axvline(0, color=INK, linewidth=0.6, alpha=0.35)
    axis.set(
        title=title,
        xlim=(-104, 104),
        ylim=(-104, 104),
        aspect="equal",
        xticks=(-100, -50, 0, 50, 100),
        yticks=(-100, -50, 0, 50, 100),
        xlabel="X (mm)",
        ylabel="Y (mm)",
    )
    axis.tick_params(labelsize=8)
    if center_text:
        axis.text(
            0,
            -88,
            center_text,
            ha="center",
            va="center",
            color=INK,
            bbox={
                "boxstyle": "round,pad=0.28",
                "facecolor": BACKGROUND,
                "edgecolor": "none",
                "alpha": 0.88,
            },
        )
    return image


def plot_decomposition_atlas(
    row_table: pd.DataFrame,
    wafer_table: pd.DataFrame,
    lot_table: pd.DataFrame,
    metrics: list[dict[str, object]],
    output_path: Path,
    *,
    representative_wafer: str,
    primary_target: str,
) -> None:
    """Plot observed, template, shifted-template, residual, and lot diagnostics."""

    _apply_style()
    wafer = row_table[
        (row_table["experiment_key"] == representative_wafer)
        & (row_table["target"] == primary_target)
    ].copy()
    if len(wafer) != 89:
        raise ValueError(
            f"representative wafer {representative_wafer} has {len(wafer)} rows"
        )

    sequential_values = np.concatenate(
        [
            wafer["observed"].to_numpy(),
            wafer["template_prediction"].to_numpy(),
            wafer["template_plus_true_mean_shift"].to_numpy(),
        ]
    )
    sequential_minimum, sequential_maximum = np.quantile(
        sequential_values, [0.005, 0.995]
    )
    residual_bound = float(np.max(np.abs(wafer["residual"])))
    primary_metrics = next(
        item for item in metrics if item["target"] == primary_target
    )

    figure = plt.figure(figsize=(18, 11.5))
    grid = figure.add_gridspec(
        2,
        12,
        height_ratios=(1.15, 0.85),
        hspace=0.32,
        wspace=0.55,
    )
    map_axes = [figure.add_subplot(grid[0, start : start + 3]) for start in (0, 3, 6, 9)]
    observed_image = _wafer_map(
        map_axes[0],
        wafer,
        "observed",
        "A  Measured map",
        color_map="viridis",
        minimum=float(sequential_minimum),
        maximum=float(sequential_maximum),
        center_text=f"mean {wafer['observed'].mean():.2f} µm",
    )
    _wafer_map(
        map_axes[1],
        wafer,
        "template_prediction",
        "B  Other-lot template",
        color_map="viridis",
        minimum=float(sequential_minimum),
        maximum=float(sequential_maximum),
        center_text=f"R² {primary_metrics['template_r2']:.3f}",
    )
    _wafer_map(
        map_axes[2],
        wafer,
        "template_plus_true_mean_shift",
        "C  Template + true mean shift",
        color_map="viridis",
        minimum=float(sequential_minimum),
        maximum=float(sequential_maximum),
        center_text=f"shift {wafer['mean_shift'].iat[0]:+.2f} µm",
    )
    residual_image = _wafer_map(
        map_axes[3],
        wafer,
        "residual",
        "D  Residual left to predict",
        color_map="RdBu_r",
        minimum=-residual_bound,
        maximum=residual_bound,
        center_text=f"RMSE {np.sqrt(np.mean(np.square(wafer['residual']))):.3f} µm",
    )
    figure.colorbar(
        observed_image,
        ax=map_axes[:3],
        location="bottom",
        shrink=0.82,
        pad=0.12,
        label=f"{TARGET_LABELS[primary_target]} (µm) · shared scale",
    )
    figure.colorbar(
        residual_image,
        ax=map_axes[3],
        location="bottom",
        shrink=0.86,
        pad=0.12,
        ticks=np.linspace(-residual_bound, residual_bound, 5),
        label="Residual (µm) · zero-centered",
    )

    shift_axis = figure.add_subplot(grid[1, 0:5])
    primary_wafers = wafer_table[wafer_table["target"] == primary_target]
    lots = sorted(primary_wafers["lot_number"].unique())
    rng = np.random.default_rng(17)
    for index, lot in enumerate(lots):
        values = primary_wafers.loc[
            primary_wafers["lot_number"] == lot, "mean_shift"
        ].to_numpy()
        jitter = rng.uniform(-0.12, 0.12, size=len(values))
        shift_axis.scatter(
            np.full(len(values), index) + jitter,
            values,
            s=28,
            color=TEAL,
            alpha=0.72,
            edgecolors=BACKGROUND,
            linewidths=0.5,
        )
        shift_axis.plot(
            [index - 0.22, index + 0.22],
            [np.mean(values), np.mean(values)],
            color=INK,
            linewidth=2.2,
        )
    shift_axis.axhline(0, color=CORAL, linewidth=1.2, linestyle="--")
    shift_axis.set(
        title="E  Wafer-level mean shift by held-out lot",
        xlabel="Lot",
        ylabel="Mean shift from other-lot template (µm)",
        xticks=np.arange(len(lots)),
        xticklabels=[str(int(lot)) for lot in lots],
    )
    shift_axis.grid(axis="y", color=GRID, linewidth=0.8)

    residual_axis = figure.add_subplot(grid[1, 5:8])
    primary_lots = lot_table[lot_table["target"] == primary_target].sort_values(
        "lot_number"
    )
    residual_axis.bar(
        np.arange(len(primary_lots)),
        primary_lots["residual_rmse_mean"],
        color=BLUE,
        alpha=0.86,
        width=0.72,
    )
    residual_axis.set(
        title="F  Residual difficulty",
        xlabel="Held-out lot",
        ylabel="Mean wafer residual RMSE (µm)",
        xticks=np.arange(len(primary_lots)),
        xticklabels=primary_lots["lot_number"].astype(int),
    )
    residual_axis.grid(axis="y", color=GRID, linewidth=0.8)

    dominance_axis = figure.add_subplot(grid[1, 8:12])
    metric_table = pd.DataFrame(metrics).set_index("target").loc[
        ["stepheight", "si_etch", "oxide_etch"]
    ]
    y = np.arange(len(metric_table))
    dominance_axis.barh(
        y + 0.17,
        metric_table["template_r2"],
        height=0.32,
        color=GOLD,
        label="Template only",
    )
    dominance_axis.barh(
        y - 0.17,
        metric_table["true_mean_shift_oracle_r2"],
        height=0.32,
        color=CYAN,
        label="+ true wafer mean shift",
    )
    dominance_axis.axvline(0.95, color=CORAL, linestyle="--", linewidth=1.4)
    dominance_axis.set(
        title="G  What the fixed shape already explains",
        xlabel="Leave-one-lot-out R²",
        yticks=y,
        yticklabels=[TARGET_LABELS[target] for target in metric_table.index],
        xlim=(min(-0.1, float(metric_table["template_r2"].min()) - 0.05), 1.02),
    )
    dominance_axis.grid(axis="x", color=GRID, linewidth=0.8)
    dominance_axis.legend(frameon=False, loc="upper left", fontsize=8)

    figure.suptitle(
        (
            f"ETCH-GATE target decomposition | {representative_wafer} held out with "
            f"Lot {int(wafer['lot_number'].iat[0])}"
        ),
        fontsize=18,
        fontweight="bold",
        x=0.06,
        ha="left",
    )
    figure.text(
        0.06,
        0.93,
        (
            "Every template is fitted without the displayed lot. Black dots are real "
            "measurement locations; smooth color between dots is visual interpolation."
        ),
        color=MUTED,
    )
    figure.text(
        0.06,
        0.015,
        (
            "Panel C uses the observed wafer mean shift as an oracle diagnostic, not as "
            "a deployable prediction. Raw-map R² is not a headline when Template R² ≥ 0.95."
        ),
        color=MUTED,
    )
    _finish(figure, output_path)


def plot_measurement_provenance(
    dense: pd.DataFrame,
    output_path: Path,
) -> None:
    """Show where raw post-etch fits failed and IDW-filled values were used."""

    _apply_style()
    flags = dense.assign(
        postoxide_filled=dense["postox_thickness_nan"].isna()
    )
    wafer_counts = (
        flags.groupby(["experiment_key", "lot_number"], as_index=False)[
            "postoxide_filled"
        ]
        .sum()
        .sort_values("postoxide_filled", ascending=False)
    )
    selected_key = str(wafer_counts.iloc[0]["experiment_key"])
    selected = flags[flags["experiment_key"] == selected_key]
    lot_counts = flags.groupby("lot_number")["postoxide_filled"].sum()

    figure = plt.figure(figsize=(13.5, 6.4))
    grid = figure.add_gridspec(1, 2, width_ratios=(1.05, 1.25), wspace=0.28)
    map_axis = figure.add_subplot(grid[0, 0])
    direct = selected[~selected["postoxide_filled"]]
    filled = selected[selected["postoxide_filled"]]
    map_axis.add_patch(
        Circle((0, 0), 100, facecolor="#E8EEF0", edgecolor=INK, linewidth=1.7)
    )
    map_axis.scatter(
        direct["X"] / 1000,
        direct["Y"] / 1000,
        s=38,
        color=TEAL,
        label=f"Raw fit available ({len(direct)})",
    )
    map_axis.scatter(
        filled["X"] / 1000,
        filled["Y"] / 1000,
        s=54,
        color=CORAL,
        marker="x",
        linewidths=1.8,
        label=f"IDW-filled after failed fit ({len(filled)})",
    )
    map_axis.set(
        title=f"Most affected wafer | {selected_key}",
        xlabel="X (mm)",
        ylabel="Y (mm)",
        xlim=(-104, 104),
        ylim=(-104, 104),
        aspect="equal",
    )
    map_axis.axhline(0, color=GRID, linewidth=0.8)
    map_axis.axvline(0, color=GRID, linewidth=0.8)
    handles, labels = map_axis.get_legend_handles_labels()

    bar_axis = figure.add_subplot(grid[0, 1])
    bar_axis.bar(
        lot_counts.index.astype(str),
        lot_counts.values,
        color=[CORAL if value > 0 else GRID for value in lot_counts.values],
        width=0.72,
    )
    for index, value in enumerate(lot_counts.values):
        bar_axis.text(index, value + 1.5, str(int(value)), ha="center", color=INK)
    bar_axis.set(
        title="Original post-etch fit failures by lot",
        xlabel="Lot",
        ylabel="89-point rows filled by IDW",
    )
    bar_axis.grid(axis="y", color=GRID, linewidth=0.8)

    figure.suptitle(
        "Measurement provenance | direct fits and released IDW replacements",
        fontsize=17,
        fontweight="bold",
        x=0.06,
        ha="left",
    )
    figure.text(
        0.06,
        0.02,
        (
            "The release preserves failed raw fits as NaN in postox_thickness_nan and "
            "provides replacements in postox_thickness. Stepheight itself is directly measured."
        ),
        color=MUTED,
    )
    figure.legend(
        handles,
        labels,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.31, 0.055),
        ncol=2,
    )
    _finish(figure, output_path)

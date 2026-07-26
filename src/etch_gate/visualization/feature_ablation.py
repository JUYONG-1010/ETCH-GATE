"""Figures for process-feature ablation and stability."""

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
PALE = "#eef3f4"
GRID = "#d8e0e4"


def _finish(figure: plt.Figure, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def plot_ablation_dashboard(
    summary: pd.DataFrame,
    stability: pd.DataFrame,
    dense: pd.DataFrame,
    output: Path,
) -> None:
    """Summarize cumulative value, family dependence, and a real wafer map."""

    figure = plt.figure(figsize=(14, 9))
    grid = figure.add_gridspec(2, 2, hspace=0.36, wspace=0.28)
    cumulative = summary[~summary["ablation"].str.startswith("family_only")].copy()
    family = summary[summary["ablation"].str.startswith("family_only")].copy()

    axis = figure.add_subplot(grid[0, 0])
    labels = ["Level", "+ drift", "+ phase", "+ cycle"]
    axis.bar(
        labels,
        cumulative["lot_macro_full_map_mae"],
        color=["#aeb8be", AMBER, "#49a7a2", TEAL],
    )
    for index, value in enumerate(cumulative["lot_macro_full_map_mae"]):
        axis.text(index, value + 0.003, f"{value:.3f}", ha="center", fontsize=9)
    axis.set_title("Cumulative feature-group ablation", loc="left", fontweight="bold")
    axis.set_ylabel("Lot-macro full-map MAE (um)")
    axis.grid(axis="y", color=GRID)
    axis.spines[["top", "right"]].set_visible(False)

    axis = figure.add_subplot(grid[0, 1])
    family_labels = (
        family["ablation"].str.replace("family_only__", "", regex=False).str.replace("_", "\n")
    )
    axis.barh(family_labels, family["lot_macro_full_map_mae"], color=CORAL, alpha=0.82)
    axis.invert_yaxis()
    axis.set_title("Single-family dependence check", loc="left", fontweight="bold")
    axis.set_xlabel("Lot-macro full-map MAE (um)")
    axis.grid(axis="x", color=GRID)
    axis.spines[["top", "right"]].set_visible(False)

    axis = figure.add_subplot(grid[1, 0])
    pls = stability[stability["family"] == "pls"]
    top = (
        pls.groupby(["feature", "feature_group"], as_index=False)
        .agg(top_fold_frequency=("top_20", "mean"), median_vip=("importance", "median"))
        .sort_values(["top_fold_frequency", "median_vip"], ascending=False)
        .head(10)
        .sort_values("top_fold_frequency")
    )
    short_labels = [value.split("Stat3_Etch_MV_", 1)[-1] for value in top["feature"]]
    axis.barh(short_labels, top["top_fold_frequency"], color=TEAL)
    axis.set_xlim(0, 1.02)
    axis.set_title("PLS top-20 stability across held-out lots", loc="left", fontweight="bold")
    axis.set_xlabel("Fraction of outer folds")
    axis.grid(axis="x", color=GRID)
    axis.spines[["top", "right"]].set_visible(False)

    axis = figure.add_subplot(grid[1, 1])
    wafer_means = dense.groupby("experiment_key")["stepheight"].mean().sort_values()
    median_key = wafer_means.index[len(wafer_means) // 2]
    wafer = dense[dense["experiment_key"] == median_key]
    triangulation = Triangulation(wafer["X"], wafer["Y"])
    contour = axis.tricontourf(
        triangulation,
        wafer["stepheight"],
        levels=18,
        cmap="viridis",
    )
    axis.set_aspect("equal")
    axis.set_xticks([])
    axis.set_yticks([])
    axis.set_title(
        f"Context: measured median-mean wafer\n{median_key}",
        loc="left",
        fontweight="bold",
    )
    figure.colorbar(contour, ax=axis, shrink=0.78, label="Stepheight (um)")
    for spine in axis.spines.values():
        spine.set_visible(False)

    figure.suptitle(
        "What do the 310 process features actually add?",
        x=0.07,
        ha="left",
        fontsize=18,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.07,
        0.94,
        "Identical nested leave-one-lot-out PLS evaluation; only feature groups change.",
        fontsize=10,
        color="#5c6973",
    )
    _finish(figure, output)


def plot_feature_stability(
    stability: pd.DataFrame,
    output: Path,
) -> None:
    """Show fold recurrence and sign consistency for the most stable features."""

    pls = stability[stability["family"] == "pls"].copy()
    grouped = (
        pls.groupby(["feature", "feature_group"], as_index=False)
        .agg(
            top_frequency=("top_20", "mean"),
            median_vip=("importance", "median"),
            positive_sign_fraction=("coefficient_sign", lambda values: np.mean(values > 0)),
        )
        .sort_values(["top_frequency", "median_vip"], ascending=False)
        .head(18)
        .sort_values("top_frequency")
    )
    labels = [value.split("Stat3_Etch_MV_", 1)[-1] for value in grouped["feature"]]
    figure, axes = plt.subplots(1, 2, figsize=(14, 7), sharey=True)
    axes[0].barh(labels, grouped["top_frequency"], color=TEAL)
    axes[0].set(xlabel="Top-20 selection frequency", xlim=(0, 1.02))
    axes[1].barh(
        labels,
        grouped["positive_sign_fraction"],
        color=np.where(grouped["positive_sign_fraction"] >= 0.5, AMBER, CORAL),
    )
    axes[1].set(xlabel="Positive coefficient fraction", xlim=(0, 1.02))
    for axis in axes:
        axis.grid(axis="x", color=GRID)
        axis.spines[["top", "right"]].set_visible(False)
    figure.suptitle(
        "Fold-wise PLS importance and coefficient-direction stability",
        fontsize=17,
        fontweight="bold",
        color=INK,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    _finish(figure, output)

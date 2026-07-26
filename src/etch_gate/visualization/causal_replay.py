"""Visual diagnostics for chronological selective-metrology replay."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Circle

COLORS = {
    "no_metrology": "#9AA3AE",
    "random": "#D7A928",
    "periodic": "#5C6BC0",
    "ood": "#237A8B",
    "disagreement": "#E46C4C",
    "combined": "#007F5F",
    "validated_combined": "#2A9D8F",
    "oracle": "#172A3A",
}


def _wafer_map(
    axis: plt.Axes,
    dense: pd.DataFrame,
    key: str,
    *,
    title: str,
) -> None:
    wafer = dense[dense["experiment_key"] == key]
    scatter = axis.scatter(
        wafer["X"],
        wafer["Y"],
        c=wafer["stepheight"],
        cmap="viridis",
        s=115,
        edgecolors="white",
        linewidths=0.7,
    )
    radius = float(np.hypot(wafer["X"], wafer["Y"]).max())
    axis.add_patch(
        Circle((0, 0), radius * 1.04, fill=False, color="#172A3A", linewidth=1.4)
    )
    axis.set_aspect("equal")
    axis.set_xlabel("X (mm)")
    axis.set_ylabel("Y (mm)")
    axis.set_title(title, loc="left")
    colorbar = axis.figure.colorbar(scatter, ax=axis, fraction=0.045, pad=0.03)
    colorbar.set_label("Measured step height (um)")


def plot_causal_replay_dashboard(
    timeline: pd.DataFrame,
    summary: pd.DataFrame,
    bootstrap: pd.DataFrame,
    dense: pd.DataFrame,
    output_path: Path,
) -> None:
    """Show deployable-policy value, feedback behavior, and measured map context."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(16, 11), facecolor="#F4F6F3")
    grid = fig.add_gridspec(2, 2, hspace=0.33, wspace=0.26)
    axes = [fig.add_subplot(grid[row, column]) for row in range(2) for column in range(2)]
    for axis in axes:
        axis.set_facecolor("white")
        axis.spines[["top", "right"]].set_visible(False)
    ax_policy, ax_feedback, ax_bootstrap, ax_map = axes

    direct = summary[
        (summary["mode"] == "direct_substitution")
        & (summary["feedback"] == "F0")
    ]
    for policy in ("no_metrology", "random", "periodic", "ood", "combined", "oracle"):
        group = direct[direct["policy"] == policy]
        ax_policy.plot(
            100 * group["budget"],
            group["lot_macro_system_mae"],
            color=COLORS[policy],
            linewidth=3 if policy == "combined" else 1.8,
            marker="o",
            label=policy.replace("_", " ").title(),
        )
    ax_policy.set_xlabel("Direct-metrology budget (%)")
    ax_policy.set_ylabel("Lot-macro total system MAE (um)")
    ax_policy.set_title("A  Online decisions, direct-result substitution", loc="left")
    ax_policy.grid(color="#E7EBE8")
    ax_policy.legend(frameon=False, ncol=2, fontsize=8)

    feedback = summary[
        (summary["mode"] == "causal_feedback")
        & (summary["policy"] == "combined")
        & (summary["budget"].isin([0.1, 0.2, 0.3]))
    ]
    feedback_order = ["F0", "F1", "F2", "F3"]
    width = 0.18
    positions = np.arange(3)
    for index, mode in enumerate(feedback_order):
        values = (
            feedback[feedback["feedback"] == mode]
            .set_index("budget")
            .reindex([0.1, 0.2, 0.3])["lot_macro_system_mae"]
        )
        ax_feedback.bar(
            positions + (index - 1.5) * width,
            values,
            width=width,
            color=["#9AA3AE", "#007F5F", "#237A8B", "#E46C4C"][index],
            label=mode,
        )
    ax_feedback.set_xticks(positions, ["10%", "20%", "30%"])
    ax_feedback.set_ylabel("Lot-macro total system MAE (um)")
    ax_feedback.set_title("B  Does measured feedback help later wafers?", loc="left")
    ax_feedback.grid(axis="y", color="#E7EBE8")
    ax_feedback.legend(frameon=False, ncol=4)

    bootstrap = bootstrap[bootstrap["budget"].isin([0.1, 0.2, 0.3])]
    centers = bootstrap["observed_mean_difference"].to_numpy()
    lower = centers - bootstrap["bootstrap_p025"].to_numpy()
    upper = bootstrap["bootstrap_p975"].to_numpy() - centers
    y = np.arange(len(bootstrap))
    ax_bootstrap.errorbar(
        centers,
        y,
        xerr=np.vstack([lower, upper]),
        fmt="o",
        color="#172A3A",
        ecolor="#237A8B",
        capsize=6,
        linewidth=2,
    )
    ax_bootstrap.axvline(0, color="#B9482E", linestyle="--")
    ax_bootstrap.set_yticks(y, [f"{value:.0%} budget" for value in bootstrap["budget"]])
    ax_bootstrap.set_xlabel("Combined system MAE - Random system MAE (um)")
    ax_bootstrap.set_title("C  Matched lot-cluster bootstrap, 95% interval", loc="left")
    ax_bootstrap.grid(axis="x", color="#E7EBE8")

    context = timeline[
        (timeline["mode"] == "direct_substitution")
        & (timeline["policy"] == "combined")
        & (timeline["budget"] == 0.2)
    ]
    key = str(context.loc[context["vm_error_before_measurement"].idxmax(), "experiment_key"])
    _wafer_map(
        ax_map,
        dense,
        key,
        title="D  Measured map of the largest frozen-VM error",
    )

    fig.text(
        0.055,
        0.965,
        "ETCH-GATE | CAUSAL SELECTIVE METROLOGY",
        fontsize=20,
        weight="bold",
        color="#172A3A",
    )
    fig.text(
        0.055,
        0.934,
        "Every decision uses past lots and the current process trace; future risk ranks are hidden",
        fontsize=11,
        color="#52616B",
    )
    fig.text(
        0.055,
        0.025,
        "Measured wafers use the direct P-17 result (system error = 0). Oracle is not deployable.",
        fontsize=9,
        color="#66747D",
    )
    fig.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def plot_cumulative_error_timeline(
    timeline: pd.DataFrame,
    lot_summary: pd.DataFrame,
    dense: pd.DataFrame,
    output_path: Path,
    *,
    budget: float = 0.2,
) -> None:
    """Show chronological cumulative error and lot-wise policy behavior."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    direct = timeline[
        (timeline["mode"] == "direct_substitution")
        & (timeline["feedback"] == "F0")
        & (timeline["budget"] == budget)
        & (timeline["policy"].isin(["no_metrology", "periodic", "combined", "oracle"]))
    ].copy()
    direct = direct.sort_values(["test_lot", "wafer_order"])
    fig = plt.figure(figsize=(16, 10), facecolor="#F4F6F3")
    grid = fig.add_gridspec(2, 2, height_ratios=(1.05, 1), hspace=0.34, wspace=0.26)
    ax_cumulative = fig.add_subplot(grid[0, :])
    ax_lots = fig.add_subplot(grid[1, 0])
    ax_map = fig.add_subplot(grid[1, 1])
    for axis in (ax_cumulative, ax_lots, ax_map):
        axis.set_facecolor("white")
        axis.spines[["top", "right"]].set_visible(False)

    for policy in ("no_metrology", "periodic", "combined", "oracle"):
        group = direct[direct["policy"] == policy]
        ax_cumulative.plot(
            np.arange(1, len(group) + 1),
            group["system_error"].cumsum(),
            color=COLORS[policy],
            linewidth=3 if policy == "combined" else 2,
            label=policy.replace("_", " ").title(),
        )
    ax_cumulative.set_xlabel("Chronological test-wafer index")
    ax_cumulative.set_ylabel("Cumulative system absolute error (um)")
    ax_cumulative.set_title(
        f"A  Cumulative system error at {budget:.0%} metrology budget",
        loc="left",
    )
    ax_cumulative.grid(color="#E7EBE8")
    ax_cumulative.legend(frameon=False, ncol=4)

    lot_data = lot_summary[
        (lot_summary["mode"] == "direct_substitution")
        & (lot_summary["feedback"] == "F0")
        & (lot_summary["budget"] == budget)
        & (lot_summary["policy"].isin(["random", "combined"]))
    ].pivot(index="test_lot", columns="policy", values="total_system_mae")
    improvement = 100 * (1 - lot_data["combined"] / lot_data["random"])
    ax_lots.bar(
        improvement.index.astype(str),
        improvement,
        color=np.where(improvement >= 0, "#007F5F", "#E46C4C"),
    )
    ax_lots.axhline(0, color="#52616B", linewidth=1)
    ax_lots.set_xlabel("Chronological test lot")
    ax_lots.set_ylabel("System MAE reduction vs Random (%)")
    ax_lots.set_title("B  Improvement is not uniform across lots", loc="left")
    ax_lots.grid(axis="y", color="#E7EBE8")

    lot8 = direct[
        (direct["test_lot"] == 8)
        & (direct["policy"] == "combined")
    ]
    key = str(lot8.loc[lot8["vm_error_before_measurement"].idxmax(), "experiment_key"])
    _wafer_map(
        ax_map,
        dense,
        key,
        title="C  Lot 8 high-error measured wafer map",
    )

    fig.text(
        0.055,
        0.965,
        "ETCH-GATE | CHRONOLOGICAL ERROR ACCOUNTING",
        fontsize=20,
        weight="bold",
        color="#172A3A",
    )
    fig.text(
        0.055,
        0.025,
        "The curve accumulates only errors available to the deployed system after each decision.",
        fontsize=9,
        color="#66747D",
    )
    fig.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

"""Publication-quality Milestone 4 risk-policy visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

COLORS = {
    "random": "#9AA3AE",
    "periodic": "#D7A928",
    "ood": "#237A8B",
    "delta": "#5C6BC0",
    "ewma": "#8F5DA2",
    "disagreement": "#E46C4C",
    "combined": "#007F5F",
    "oracle": "#172A3A",
}


def plot_failure_risk_dashboard(
    wafer_scores: pd.DataFrame,
    risk_curves: pd.DataFrame,
    lot_summary: pd.DataFrame,
    output_path: Path,
    *,
    minimum_reduction: float,
    minimum_lots: int,
) -> None:
    """Show policy value, wafer risk landscape, and the Lot 8 failure sequence."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    macro_curve = (
        risk_curves.groupby(["policy", "requested_budget"], as_index=False)
        .agg(retained_mae=("retained_mae", "mean"))
    )
    macro_aurc = lot_summary.groupby("policy")["aurc"].mean()
    random_aurc = float(macro_aurc["random"])
    reductions = 100 * (1 - macro_aurc / random_aurc)
    combined_lots = lot_summary.pivot(index="lot_number", columns="policy", values="aurc")
    improved_lots = int((combined_lots["combined"] < combined_lots["random"]).sum())
    combined_reduction = float(reductions["combined"])
    passed = combined_reduction >= 100 * minimum_reduction and improved_lots >= minimum_lots

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.titleweight": "bold",
            "axes.edgecolor": "#C9D0D6",
            "axes.labelcolor": "#36454F",
            "xtick.color": "#52616B",
            "ytick.color": "#52616B",
        }
    )
    fig = plt.figure(figsize=(16, 11), facecolor="#F4F6F3")
    grid = fig.add_gridspec(2, 2, height_ratios=(1.05, 1), hspace=0.34, wspace=0.23)
    ax_curve = fig.add_subplot(grid[0, 0])
    ax_bar = fig.add_subplot(grid[0, 1])
    ax_map = fig.add_subplot(grid[1, 0])
    ax_lot8 = fig.add_subplot(grid[1, 1])
    for axis in (ax_curve, ax_bar, ax_map, ax_lot8):
        axis.set_facecolor("#FFFFFF")
        axis.grid(color="#E7EBE8", linewidth=0.8, zorder=0)
        axis.spines[["top", "right"]].set_visible(False)

    shown = ["random", "periodic", "ood", "disagreement", "combined", "oracle"]
    for policy in shown:
        group = macro_curve[macro_curve["policy"] == policy]
        ax_curve.plot(
            100 * group["requested_budget"],
            group["retained_mae"],
            color=COLORS[policy],
            linewidth=3 if policy == "combined" else 1.8,
            marker="o" if policy in {"combined", "random"} else None,
            markersize=4,
            label=policy.replace("_", " ").title(),
            zorder=3,
        )
    ax_curve.set_title("A  What remains after selective metrology", loc="left", fontsize=13)
    ax_curve.set_xlabel("Wafers sent to full 89-point metrology (%)")
    ax_curve.set_ylabel("Mean MAE of unmeasured wafers (um)")
    ax_curve.legend(frameon=False, ncol=2, fontsize=9)

    order = ["periodic", "ood", "delta", "ewma", "disagreement", "combined", "oracle"]
    values = reductions.reindex(order)
    bars = ax_bar.barh(
        np.arange(len(order)),
        values,
        color=[COLORS[name] for name in order],
        edgecolor="white",
        zorder=2,
    )
    ax_bar.axvline(0, color="#52616B", linewidth=1)
    ax_bar.axvline(10, color="#007F5F", linewidth=1.3, linestyle="--")
    ax_bar.set_yticks(np.arange(len(order)), [name.title() for name in order])
    ax_bar.set_xlabel("Lot-macro AURC reduction vs Random (%)")
    ax_bar.set_title("B  Ranking value across all held-out lots", loc="left", fontsize=13)
    ax_bar.invert_yaxis()
    for bar, value in zip(bars, values, strict=True):
        ax_bar.text(
            value + (0.8 if value >= 0 else -0.8),
            bar.get_y() + bar.get_height() / 2,
            f"{value:+.1f}%",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=9,
            color="#263238",
        )

    ordered_scores = wafer_scores.sort_values(["lot_number", "experiment_key"]).copy()
    ordered_scores["wafer_in_lot"] = ordered_scores.groupby("lot_number").cumcount() + 1
    scatter = ax_map.scatter(
        ordered_scores["wafer_in_lot"],
        ordered_scores["lot_number"],
        c=ordered_scores["combined_risk"],
        s=70 + 900 * ordered_scores["true_pls_mae"],
        cmap="viridis",
        vmin=0,
        vmax=1,
        edgecolors="#FFFFFF",
        linewidths=1.1,
        zorder=3,
    )
    ax_map.set_yticks(sorted(ordered_scores["lot_number"].unique()))
    ax_map.set_xlabel("Wafer order inside lot")
    ax_map.set_ylabel("Held-out lot")
    ax_map.set_title(
        "C  Risk landscape: color = predicted risk, size = actual error",
        loc="left",
        fontsize=13,
    )
    colorbar = fig.colorbar(scatter, ax=ax_map, fraction=0.045, pad=0.02)
    colorbar.set_label("Target-free combined risk")

    lot8 = ordered_scores[ordered_scores["lot_number"] == 8]
    x = lot8["wafer_in_lot"].to_numpy()
    errors = lot8["true_pls_mae"].to_numpy()
    risks = lot8["combined_risk"].to_numpy()
    ax_lot8.bar(x, errors, color="#F2B8A7", edgecolor="#E46C4C", label="Actual PLS MAE", zorder=2)
    ax_lot8.set_xlabel("Lot 8 wafer order")
    ax_lot8.set_ylabel("Actual MAE (um)", color="#B9482E")
    twin = ax_lot8.twinx()
    twin.plot(x, risks, color="#007F5F", linewidth=3, marker="o", label="Predicted risk", zorder=4)
    twin.set_ylim(0, 1.05)
    twin.set_ylabel("Target-free risk (0-1)", color="#007F5F")
    twin.spines["top"].set_visible(False)
    ax_lot8.set_title(
        "D  Lot 8: was the late-lot failure visible in advance?",
        loc="left",
        fontsize=13,
    )
    ax_lot8.legend(
        handles=[
            Line2D([0], [0], color="#E46C4C", linewidth=7, label="Actual error"),
            Line2D(
                [0],
                [0],
                color="#007F5F",
                marker="o",
                linewidth=3,
                label="Risk before metrology",
            ),
        ],
        frameon=False,
        loc="upper left",
    )

    status_color = "#007F5F" if passed else "#B9482E"
    status = "PASS" if passed else "FAIL"
    fig.text(
        0.055,
        0.965,
        "ETCH-GATE | DRIFT & FAILURE-AWARE VM",
        fontsize=20,
        weight="bold",
        color="#172A3A",
    )
    fig.text(
        0.055,
        0.934,
        "Can process-end information prioritize direct metrology before the "
        "89-point result exists?",
        fontsize=11,
        color="#52616B",
    )
    fig.text(
        0.945,
        0.95,
        f"{status}  {combined_reduction:+.1f}% AURC | {improved_lots}/10 lots",
        ha="right",
        fontsize=12,
        weight="bold",
        color=status_color,
        bbox={"boxstyle": "round,pad=0.45", "facecolor": "white", "edgecolor": status_color},
    )
    fig.text(
        0.055,
        0.025,
        "Outer leave-one-lot-out. Risk scaling uses outer-training wafers only. "
        "Oracle is an unattainable upper bound.",
        fontsize=9,
        color="#66747D",
    )
    fig.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

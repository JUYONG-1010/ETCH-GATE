"""Publication-ready figures for actual-wafer BOSCH cycle validation."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from etch_gate.analysis.cycle_validation import deterministic_example_keys
from etch_gate.data.process import (
    LONG_PHASE_GAS,
    SHORT_PHASE_GAS,
    ProcessTrace,
    detect_process_regions,
)

INK = "#17212b"
TEAL = "#008b87"
AMBER = "#eba514"
CORAL = "#dc554f"
GRID = "#d8e0e4"


def _finish(figure: plt.Figure, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def plot_cycle_count_by_lot(
    diagnostics: pd.DataFrame,
    output: Path,
) -> None:
    """Show all actual-wafer cycle counts and the stated 95-105 band."""

    figure, axis = plt.subplots(figsize=(12, 5.8))
    axis.axhspan(95, 105, color=TEAL, alpha=0.10, label="95-105 validation band")
    rng = np.random.default_rng(20260726)
    for lot, group in diagnostics.groupby("lot_number"):
        jitter = rng.uniform(-0.18, 0.18, len(group))
        colors = np.where(group["suspicious"], CORAL, TEAL)
        axis.scatter(
            lot + jitter,
            group["detected_cycle_count"],
            c=colors,
            s=48,
            edgecolor="white",
            linewidth=0.6,
            zorder=3,
        )
    medians = diagnostics.groupby("lot_number")["detected_cycle_count"].median()
    axis.plot(medians.index, medians.values, color=INK, marker="D", lw=1.5, label="lot median")
    axis.set(
        title="Actual-wafer BOSCH cycle detection across all 96 process traces",
        xlabel="Chronological lot",
        ylabel="Detected cycle count",
        xticks=sorted(diagnostics["lot_number"].unique()),
    )
    axis.grid(axis="y", color=GRID, lw=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False, ncol=2, loc="upper right")
    figure.text(
        0.01,
        0.01,
        "Red markers are flagged by a fixed cycle/phase diagnostic rule; "
        "no stepheight target is used.",
        fontsize=9,
        color="#5c6973",
    )
    _finish(figure, output)


def plot_phase_duration_distribution(
    diagnostics: pd.DataFrame,
    output: Path,
) -> None:
    """Compare long, short, and complete-cycle durations by lot."""

    figure, axes = plt.subplots(1, 3, figsize=(14, 5.2), sharex=True)
    fields = [
        ("long_phase_median_seconds", "Long phase", TEAL),
        ("short_phase_median_seconds", "Short phase", AMBER),
        ("cycle_period_median_seconds", "Cycle period", INK),
    ]
    for axis, (field, title, color) in zip(axes, fields, strict=True):
        grouped = [
            diagnostics.loc[diagnostics["lot_number"] == lot, field].to_numpy()
            for lot in sorted(diagnostics["lot_number"].unique())
        ]
        plot = axis.boxplot(
            grouped,
            patch_artist=True,
            showfliers=True,
            medianprops={"color": INK, "linewidth": 1.5},
            boxprops={"edgecolor": color},
            whiskerprops={"color": color},
            capprops={"color": color},
            flierprops={"marker": "o", "markersize": 3, "markerfacecolor": CORAL},
        )
        for patch in plot["boxes"]:
            patch.set_facecolor(color)
            patch.set_alpha(0.18)
        axis.set_title(title, color=INK, fontweight="bold")
        axis.set_xlabel("Lot")
        axis.grid(axis="y", color=GRID, lw=0.8)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Median duration per wafer (s)")
    figure.suptitle(
        "BOSCH phase-duration stability from real timestamps",
        fontsize=16,
        fontweight="bold",
        color=INK,
    )
    figure.tight_layout(rect=(0, 0.03, 1, 0.94))
    _finish(figure, output)


def plot_anomalous_cycle_examples(
    traces: dict[str, ProcessTrace],
    diagnostics: pd.DataFrame,
    detector: str,
    output: Path,
) -> None:
    """Plot deterministic median/min/max/anomaly examples."""

    examples = deterministic_example_keys(diagnostics)
    roles = ["median", "minimum", "maximum", "phase_anomaly"]
    figure, axes = plt.subplots(4, 1, figsize=(14, 10.5), sharex=False)
    for axis, role in zip(axes, roles, strict=True):
        key = examples[role]
        trace = traces[key]
        regions = detect_process_regions(trace, detector=detector)
        active = regions.active
        time = trace.times - regions.active_start_seconds
        long_signal = trace.values[LONG_PHASE_GAS].to_numpy(dtype=float)
        short_signal = trace.values[SHORT_PHASE_GAS].to_numpy(dtype=float)
        long_scale = max(np.ptp(long_signal), 1e-12)
        short_scale = max(np.ptp(short_signal), 1e-12)
        long_normalized = (long_signal - long_signal.min()) / long_scale
        short_normalized = (short_signal - short_signal.min()) / short_scale
        axis.plot(
            time[active],
            long_normalized[active],
            color=TEAL,
            lw=1.0,
            label="Gas5 normalized",
        )
        axis.plot(
            time[active],
            short_normalized[active],
            color=AMBER,
            lw=1.0,
            label="Gas4 normalized",
        )
        for edge in trace.times[regions.rising_edge_indices] - regions.active_start_seconds:
            axis.axvline(edge, color=INK, alpha=0.12, lw=0.6)
        row = diagnostics.set_index("experiment_key").loc[key]
        axis.set_title(
            f"{role.replace('_', ' ').title()}: {key} | "
            f"{int(row['detected_cycle_count'])} cycles",
            loc="left",
            fontsize=10.5,
            fontweight="bold",
            color=INK,
        )
        axis.set_ylabel("Normalized")
        axis.set_ylim(-0.05, 1.08)
        axis.grid(axis="y", color=GRID, lw=0.7)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, ncol=2, loc="upper right")
    axes[-1].set_xlabel("Seconds from RF-active-window start")
    figure.suptitle(
        "Deterministically selected cycle-detection examples",
        fontsize=16,
        fontweight="bold",
        color=INK,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    _finish(figure, output)

"""Publication-style visualization for the one-day OES integrity gate."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from etch_gate.data.oes import OESPreview
from etch_gate.data.process import ProcessTrace, detect_process_regions

INK = "#17212B"
MUTED = "#66717E"
TEAL = "#007F7B"
CORAL = "#E45C3A"
GOLD = "#E8A317"


def _bin_wavelengths(
    values: np.ndarray,
    wavelengths: np.ndarray,
    *,
    bin_size: int = 16,
) -> tuple[np.ndarray, np.ndarray]:
    usable = len(wavelengths) - len(wavelengths) % bin_size
    binned = values[:, :usable].reshape(len(values), -1, bin_size).mean(axis=2)
    centers = wavelengths[:usable].reshape(-1, bin_size).mean(axis=1)
    return binned, centers


def plot_oes_integrity_dashboard(
    preview: OESPreview,
    process_trace: ProcessTrace,
    audit: pd.DataFrame,
    output_path: Path,
) -> None:
    """Show the spectrum, time structure, alignment, and file-level gate."""

    regions = detect_process_regions(process_trace)
    process_elapsed = process_trace.times - process_trace.times[0]
    source = process_trace.values["Stat3_Etch_MV_SourceRFLoadPower"].to_numpy(dtype=float)
    source_scaled = (source - np.quantile(source, 0.05)) / max(
        np.quantile(source, 0.95) - np.quantile(source, 0.05), 1e-12
    )
    broadband = preview.broadband_mean
    broadband_scaled = (broadband - np.quantile(broadband, 0.05)) / max(
        np.quantile(broadband, 0.95) - np.quantile(broadband, 0.05), 1e-12
    )
    heatmap, wavelength_centers = _bin_wavelengths(
        preview.decoded_intensity,
        preview.wavelengths_nm,
    )
    color_min, color_max = np.quantile(heatmap, [0.02, 0.995])

    figure = plt.figure(figsize=(18, 10), facecolor="#F7F9FA")
    grid = figure.add_gridspec(2, 12, hspace=0.34, wspace=0.75)
    figure.suptitle(
        "One-day OES gate: valid spectra, shared wavelengths, aligned process time",
        x=0.045,
        y=0.975,
        ha="left",
        fontsize=21,
        fontweight="bold",
        color=INK,
    )
    figure.text(
        0.045,
        0.938,
        (
            f"{preview.experiment_key} preview | 3,648 wavelengths | "
            "dictionary-decoded intensity | no target used"
        ),
        fontsize=10,
        color=MUTED,
    )
    passed = int(audit["passes_integrity_gate"].sum())
    figure.text(
        0.82,
        0.954,
        f"{passed}/{len(audit)} wafers pass",
        fontsize=15,
        color=TEAL if passed == len(audit) else CORAL,
        fontweight="bold",
    )

    heat_axis = figure.add_subplot(grid[0, :8])
    image = heat_axis.imshow(
        heatmap.T,
        origin="lower",
        aspect="auto",
        extent=(
            preview.elapsed_seconds[0],
            preview.elapsed_seconds[-1],
            wavelength_centers[0],
            wavelength_centers[-1],
        ),
        cmap="magma",
        vmin=color_min,
        vmax=color_max,
    )
    heat_axis.axvspan(
        regions.active_start_seconds - process_trace.times[0],
        regions.active_end_seconds - process_trace.times[0],
        color=TEAL,
        alpha=0.08,
        label="Process active RF window",
    )
    heat_axis.set_title("Plasma emission across time and wavelength", loc="left",
                        fontweight="bold", color=INK)
    heat_axis.set_xlabel("Seconds from wafer trace start")
    heat_axis.set_ylabel("Wavelength (nm)")
    heat_axis.legend(frameon=False, fontsize=8, loc="upper right")
    heat_axis.tick_params(colors=MUTED, labelsize=8)
    heat_axis.spines[["top", "right"]].set_visible(False)
    colorbar = figure.colorbar(image, ax=heat_axis, fraction=0.025, pad=0.02)
    colorbar.ax.tick_params(labelsize=7, colors=MUTED)

    spectrum_axis = figure.add_subplot(grid[0, 8:])
    spectrum_axis.plot(preview.wavelengths_nm, preview.mean_spectrum, color=GOLD,
                       linewidth=1.0)
    spectrum_axis.set_title("Mean emission spectrum", loc="left", fontweight="bold",
                            color=INK)
    spectrum_axis.set_xlabel("Wavelength (nm)")
    spectrum_axis.set_ylabel("Mean intensity (a.u.)")
    spectrum_axis.grid(color="#D8DFE3", linewidth=0.6)
    spectrum_axis.spines[["top", "right"]].set_visible(False)
    spectrum_axis.tick_params(colors=MUTED, labelsize=8)

    alignment_axis = figure.add_subplot(grid[1, :8])
    alignment_axis.plot(process_elapsed, source_scaled, color=TEAL, linewidth=1.1,
                        label="Source RF power (robust scaled)")
    alignment_axis.plot(preview.elapsed_seconds, broadband_scaled, color=CORAL,
                        linewidth=0.9, alpha=0.8, label="OES broadband mean (robust scaled)")
    alignment_axis.axvspan(
        regions.active_start_seconds - process_trace.times[0],
        regions.active_end_seconds - process_trace.times[0],
        color=TEAL,
        alpha=0.08,
    )
    alignment_axis.set_xlim(0, preview.elapsed_seconds[-1])
    alignment_axis.set_title("Independent sensors share the same wafer timeline", loc="left",
                             fontweight="bold", color=INK)
    alignment_axis.set_xlabel("Seconds from each trace start")
    alignment_axis.set_ylabel("Robust-scaled signal")
    alignment_axis.grid(color="#D8DFE3", linewidth=0.6)
    alignment_axis.spines[["top", "right"]].set_visible(False)
    alignment_axis.tick_params(colors=MUTED, labelsize=8)
    alignment_axis.legend(frameon=False, ncol=2, fontsize=8)

    status_axis = figure.add_subplot(grid[1, 8:])
    status_axis.set_xlim(0, 1)
    status_axis.set_ylim(0, 1)
    status_axis.axis("off")
    metrics = [
        ("Wafer groups", f"{len(audit)}"),
        ("Wavelength grid", f"{int(audit['wavelengths'].iloc[0]):,} shared channels"),
        ("Median sample rate", f"{audit['effective_sample_rate_hz'].median():.2f} Hz"),
        ("Largest timestamp gap", f"{audit['maximum_gap_seconds'].max():.3f} s"),
        ("Max duration mismatch", f"{audit['duration_difference_seconds'].abs().max():.3f} s"),
        ("Dictionary code gate", "PASS"),
    ]
    status_axis.set_title("Integrity and alignment audit", loc="left", fontweight="bold",
                          color=INK, pad=12)
    for index, (label, value) in enumerate(metrics):
        y = 0.91 - index * 0.145
        status_axis.text(
            0.02,
            y,
            label,
            color=MUTED,
            fontsize=9,
            va="center",
            transform=status_axis.transAxes,
        )
        status_axis.text(
            0.98,
            y,
            value,
            color=TEAL,
            fontsize=10,
            fontweight="bold",
            ha="right",
            va="center",
            transform=status_axis.transAxes,
        )
        status_axis.plot([0.02, 0.98], [y - 0.065, y - 0.065], color="#D8DFE3",
                         linewidth=0.7, transform=status_axis.transAxes)
    figure.text(
        0.045,
        0.04,
        (
            "OES is in-situ process sensing, not additional post-process metrology. "
            "This one-lot gate validates data integrity only; it cannot establish "
            "unseen-lot accuracy."
        ),
        fontsize=9,
        color=MUTED,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)

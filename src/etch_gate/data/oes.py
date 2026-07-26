"""Streaming audit and compact preview utilities for daily OES NetCDF files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from netCDF4 import Dataset

from etch_gate.data.process import ProcessTrace, detect_process_regions

DAY_PATTERN = re.compile(r"Day_(\d{4})_(\d{2})_(\d{2})\.nc")
WAFER_PATTERN = re.compile(r"Wafer_(\d{2})")


@dataclass(frozen=True)
class OESPreview:
    """Memory-bounded subset used only for visual inspection."""

    experiment_key: str
    elapsed_seconds: np.ndarray
    wavelengths_nm: np.ndarray
    decoded_intensity: np.ndarray
    mean_spectrum: np.ndarray
    broadband_mean: np.ndarray


OES_STATISTICS = (
    "active_mean",
    "active_std",
    "early_late_delta",
    "long_phase_mean",
    "short_phase_mean",
    "phase_difference",
    "cycle_mean_slope",
)


def oes_group_to_key(path: Path, group_name: str) -> str:
    """Build the shared experiment key from the daily filename and wafer group."""

    day_match = DAY_PATTERN.fullmatch(path.name)
    wafer_match = WAFER_PATTERN.fullmatch(group_name)
    if day_match is None or wafer_match is None:
        raise ValueError(f"unexpected OES file/group pair: {path.name}/{group_name}")
    year, month, day = day_match.groups()
    return f"{year}-{month}-{day}_{wafer_match.group(1)}"


def _regular_process_duration(times: np.ndarray) -> float:
    """Ignore a final isolated logging point after the regular process trace."""

    differences = np.diff(times)
    if len(differences) == 0 or np.any(differences <= 0):
        raise ValueError("process timestamps must be strictly increasing")
    median_step = float(np.median(differences))
    regular_transitions = np.flatnonzero(differences <= 5 * median_step)
    if len(regular_transitions) == 0:
        raise ValueError("process trace has no regular timestamp transitions")
    regular_end = int(regular_transitions[-1] + 1)
    return float(times[regular_end] - times[0])


def audit_oes_day(
    oes_path: Path,
    dictionary_path: Path,
    process_traces: dict[str, ProcessTrace],
    *,
    expected_wavelength_count: int = 3_648,
    chunk_rows: int = 512,
) -> tuple[pd.DataFrame, np.ndarray, dict[str, object]]:
    """Audit dictionary codes, axes, wafer keys, and process-time alignment."""

    with Dataset(dictionary_path) as dictionary:
        decoder = np.asarray(dictionary["data"][:], dtype=np.float32)
    if len(decoder) == 0 or not np.isfinite(decoder).all():
        raise ValueError("OES dictionary is empty or non-finite")

    rows: list[dict[str, object]] = []
    reference_wavelengths: np.ndarray | None = None
    with Dataset(oes_path) as dataset:
        for group_name, group in dataset.groups.items():
            key = oes_group_to_key(oes_path, group_name)
            required = {"times", "wavelengths", "data"}
            missing = sorted(required - set(group.variables))
            if missing:
                raise ValueError(f"{group_name} is missing variables: {missing}")
            if key not in process_traces:
                raise ValueError(f"{key} has no matching process trace")

            times = np.asarray(group["times"][:], dtype=float)
            wavelengths = np.asarray(group["wavelengths"][:], dtype=float)
            encoded = group["data"]
            if encoded.shape != (len(times), len(wavelengths)):
                raise ValueError(f"{group_name} has inconsistent OES dimensions")
            if len(times) < 2 or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
                raise ValueError(f"{group_name} has invalid timestamps")
            if not np.isfinite(wavelengths).all() or np.any(np.diff(wavelengths) <= 0):
                raise ValueError(f"{group_name} has an invalid wavelength axis")
            if reference_wavelengths is None:
                reference_wavelengths = wavelengths.copy()
            wavelength_match = np.array_equal(wavelengths, reference_wavelengths)

            code_min = len(decoder)
            code_max = -1
            for start in range(0, len(times), chunk_rows):
                block = np.asarray(encoded[start : start + chunk_rows, :])
                code_min = min(code_min, int(block.min()))
                code_max = max(code_max, int(block.max()))
            valid_codes = code_min >= 0 and code_max < len(decoder)

            process = process_traces[key]
            regions = detect_process_regions(process)
            process_elapsed_start = regions.active_start_seconds - process.times[0]
            process_elapsed_end = regions.active_end_seconds - process.times[0]
            oes_duration = float(times[-1] - times[0])
            process_duration = _regular_process_duration(process.times)
            duration_difference = oes_duration - process_duration
            active_covered = (
                process_elapsed_start >= -2.0 and process_elapsed_end <= oes_duration + 2.0
            )
            time_steps = np.diff(times)
            passes = (
                wavelength_match
                and len(wavelengths) == expected_wavelength_count
                and valid_codes
                and active_covered
                and abs(duration_difference) <= 2.0
            )
            rows.append(
                {
                    "experiment_key": key,
                    "group_name": group_name,
                    "time_samples": len(times),
                    "wavelengths": len(wavelengths),
                    "wavelength_min_nm": float(wavelengths[0]),
                    "wavelength_max_nm": float(wavelengths[-1]),
                    "median_step_seconds": float(np.median(time_steps)),
                    "effective_sample_rate_hz": float(1 / np.median(time_steps)),
                    "maximum_gap_seconds": float(time_steps.max()),
                    "oes_duration_seconds": oes_duration,
                    "process_regular_duration_seconds": process_duration,
                    "duration_difference_seconds": duration_difference,
                    "process_active_start_elapsed_seconds": process_elapsed_start,
                    "process_active_end_elapsed_seconds": process_elapsed_end,
                    "minimum_dictionary_code": code_min,
                    "maximum_dictionary_code": code_max,
                    "dictionary_size": len(decoder),
                    "wavelength_axis_matches": wavelength_match,
                    "active_window_covered": active_covered,
                    "passes_integrity_gate": passes,
                }
            )

    if reference_wavelengths is None:
        raise ValueError("OES file contains no wafer groups")
    summary = pd.DataFrame(rows).sort_values("experiment_key").reset_index(drop=True)
    manifest = {
        "oes_file": oes_path.name,
        "wafer_groups": len(summary),
        "all_groups_pass": bool(summary["passes_integrity_gate"].all()),
        "all_wavelength_axes_identical": bool(summary["wavelength_axis_matches"].all()),
        "all_active_windows_covered": bool(summary["active_window_covered"].all()),
        "wavelength_count": int(len(reference_wavelengths)),
        "wavelength_range_nm": [
            float(reference_wavelengths[0]),
            float(reference_wavelengths[-1]),
        ],
        "maximum_timestamp_gap_seconds": float(summary["maximum_gap_seconds"].max()),
        "maximum_absolute_duration_mismatch_seconds": float(
            summary["duration_difference_seconds"].abs().max()
        ),
        "claim_boundary": ("one-lot integrity and alignment gate; no unseen-lot model claim"),
    }
    return summary, reference_wavelengths, manifest


def load_oes_preview(
    oes_path: Path,
    dictionary_path: Path,
    group_name: str,
    *,
    maximum_time_rows: int = 600,
) -> OESPreview:
    """Decode an evenly sampled, memory-bounded preview of one wafer."""

    with Dataset(dictionary_path) as dictionary:
        decoder = np.asarray(dictionary["data"][:], dtype=np.float32)
    with Dataset(oes_path) as dataset:
        group = dataset[group_name]
        times = np.asarray(group["times"][:], dtype=float)
        wavelengths = np.asarray(group["wavelengths"][:], dtype=float)
        stride = max(1, int(np.ceil(len(times) / maximum_time_rows)))
        indices = np.arange(0, len(times), stride)
        encoded = np.asarray(group["data"][indices, :])
    if encoded.max() >= len(decoder):
        raise ValueError(f"{group_name} preview contains an invalid dictionary code")
    decoded = decoder[encoded]
    return OESPreview(
        experiment_key=oes_group_to_key(oes_path, group_name),
        elapsed_seconds=times[indices] - times[0],
        wavelengths_nm=wavelengths,
        decoded_intensity=decoded,
        mean_spectrum=decoded.mean(axis=0),
        broadband_mean=decoded.mean(axis=1),
    )


def _nearest_process_indices(
    oes_elapsed: np.ndarray,
    process_elapsed: np.ndarray,
) -> np.ndarray:
    """Map each OES timestamp to the nearest process-sensor timestamp."""

    right = np.searchsorted(process_elapsed, oes_elapsed, side="left")
    right = np.clip(right, 0, len(process_elapsed) - 1)
    left = np.maximum(right - 1, 0)
    choose_left = np.abs(oes_elapsed - process_elapsed[left]) <= np.abs(
        process_elapsed[right] - oes_elapsed
    )
    return np.where(choose_left, left, right)


def _vector_slope(values: np.ndarray) -> np.ndarray:
    """Return a normalized-time least-squares slope for every wavelength."""

    if len(values) < 2:
        return np.zeros(values.shape[1], dtype=float)
    x = np.linspace(0.0, 1.0, len(values))
    centered = x - x.mean()
    return centered @ values / np.sum(np.square(centered))


def extract_oes_feature_table(
    oes_paths: list[Path],
    dictionary_path: Path,
    process_traces: dict[str, ProcessTrace],
    *,
    chunk_rows: int = 256,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create target-free cycle/phase spectral summaries, one row per wafer."""

    with Dataset(dictionary_path) as dictionary:
        decoder = np.asarray(dictionary["data"][:], dtype=np.float32)
    feature_rows: list[dict[str, float | str]] = []
    diagnostic_rows: list[dict[str, float | str]] = []
    reference_wavelengths: np.ndarray | None = None

    for oes_path in oes_paths:
        with Dataset(oes_path) as dataset:
            for group_name, group in dataset.groups.items():
                key = oes_group_to_key(oes_path, group_name)
                if key not in process_traces:
                    raise ValueError(f"{key} has no matching process trace")
                times = np.asarray(group["times"][:], dtype=float)
                wavelengths = np.asarray(group["wavelengths"][:], dtype=float)
                if reference_wavelengths is None:
                    reference_wavelengths = wavelengths.copy()
                elif not np.array_equal(wavelengths, reference_wavelengths):
                    raise ValueError(f"{key} has a different wavelength grid")

                process = process_traces[key]
                regions = detect_process_regions(process)
                oes_elapsed = times - times[0]
                process_elapsed = process.times - process.times[0]
                nearest = _nearest_process_indices(oes_elapsed, process_elapsed)
                active = regions.active[nearest]
                long_phase = regions.long_phase[nearest]
                short_phase = regions.short_phase[nearest]
                cycle_index = regions.cycle_index[nearest]
                active_times = oes_elapsed[active]
                active_duration = active_times[-1] - active_times[0]
                early = active & (oes_elapsed <= active_times[0] + 0.1 * active_duration)
                late = active & (oes_elapsed >= active_times[-1] - 0.1 * active_duration)
                masks = {
                    "active": active,
                    "early": early,
                    "late": late,
                    "long": long_phase,
                    "short": short_phase,
                }
                sums = {name: np.zeros(len(wavelengths)) for name in masks}
                squared_active_sum = np.zeros(len(wavelengths))
                counts = {name: int(mask.sum()) for name, mask in masks.items()}
                cycle_sums = np.zeros((regions.cycle_count, len(wavelengths)))
                cycle_counts = np.bincount(
                    cycle_index[cycle_index >= 0],
                    minlength=regions.cycle_count,
                )

                encoded_variable = group["data"]
                for start in range(0, len(times), chunk_rows):
                    stop = min(start + chunk_rows, len(times))
                    encoded = np.asarray(encoded_variable[start:stop, :])
                    if encoded.max() >= len(decoder):
                        raise ValueError(f"{key} contains an invalid dictionary code")
                    decoded = decoder[encoded].astype(np.float64, copy=False)
                    for name, mask in masks.items():
                        local = mask[start:stop]
                        if local.any():
                            sums[name] += decoded[local].sum(axis=0)
                    local_active = active[start:stop]
                    if local_active.any():
                        squared_active_sum += np.square(decoded[local_active]).sum(axis=0)
                    local_cycles = cycle_index[start:stop]
                    for cycle in np.unique(local_cycles[local_cycles >= 0]):
                        cycle_sums[cycle] += decoded[local_cycles == cycle].sum(axis=0)

                if any(counts[name] == 0 for name in masks):
                    raise ValueError(f"{key} has an empty aligned OES phase")
                active_mean = sums["active"] / counts["active"]
                active_variance = np.maximum(
                    squared_active_sum / counts["active"] - np.square(active_mean),
                    0.0,
                )
                valid_cycles = cycle_counts > 0
                cycle_means = cycle_sums[valid_cycles] / cycle_counts[valid_cycles, None]
                statistics = {
                    "active_mean": active_mean,
                    "active_std": np.sqrt(active_variance),
                    "early_late_delta": (
                        sums["late"] / counts["late"] - sums["early"] / counts["early"]
                    ),
                    "long_phase_mean": sums["long"] / counts["long"],
                    "short_phase_mean": sums["short"] / counts["short"],
                    "phase_difference": (
                        sums["long"] / counts["long"] - sums["short"] / counts["short"]
                    ),
                    "cycle_mean_slope": _vector_slope(cycle_means),
                }
                feature_row: dict[str, float | str] = {"experiment_key": key}
                for statistic in OES_STATISTICS:
                    for wavelength, value in zip(
                        wavelengths,
                        statistics[statistic],
                        strict=True,
                    ):
                        feature_row[f"wl_{wavelength:.6f}__{statistic}"] = float(value)
                feature_rows.append(feature_row)
                diagnostic_rows.append(
                    {
                        "experiment_key": key,
                        "oes_samples": len(times),
                        "aligned_active_samples": counts["active"],
                        "aligned_long_phase_samples": counts["long"],
                        "aligned_short_phase_samples": counts["short"],
                        "aligned_cycles": int(valid_cycles.sum()),
                        "nearest_time_offset_median_seconds": float(
                            np.median(np.abs(oes_elapsed - process_elapsed[nearest]))
                        ),
                        "nearest_time_offset_maximum_seconds": float(
                            np.max(np.abs(oes_elapsed - process_elapsed[nearest]))
                        ),
                    }
                )

    features = pd.DataFrame(feature_rows).set_index("experiment_key").sort_index()
    diagnostics = pd.DataFrame(diagnostic_rows).set_index("experiment_key").sort_index()
    if not np.isfinite(features.to_numpy(dtype=float)).all():
        raise ValueError("OES feature table contains non-finite values")
    return features, diagnostics


def extract_normalized_oes_shape_table(
    oes_paths: list[Path],
    dictionary_path: Path,
    process_traces: dict[str, ProcessTrace],
    *,
    chunk_rows: int = 256,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarize normalized spectral shape for compact, fold-wise OES PCA.

    Each spectrum is divided by its broadband intensity before aggregation.
    This deliberately discards absolute optical gain, which can include a
    spectrometer or chamber-state effect unrelated to the wafer target.
    """

    with Dataset(dictionary_path) as dictionary:
        decoder = np.asarray(dictionary["data"][:], dtype=np.float32)
    feature_rows: list[dict[str, float | str]] = []
    diagnostic_rows: list[dict[str, float | str]] = []
    reference_wavelengths: np.ndarray | None = None

    for oes_path in oes_paths:
        with Dataset(oes_path) as dataset:
            for group_name, group in dataset.groups.items():
                key = oes_group_to_key(oes_path, group_name)
                if key not in process_traces:
                    raise ValueError(f"{key} has no matching process trace")
                times = np.asarray(group["times"][:], dtype=float)
                wavelengths = np.asarray(group["wavelengths"][:], dtype=float)
                if reference_wavelengths is None:
                    reference_wavelengths = wavelengths.copy()
                elif not np.array_equal(wavelengths, reference_wavelengths):
                    raise ValueError(f"{key} has a different wavelength grid")

                process = process_traces[key]
                regions = detect_process_regions(process)
                elapsed = times - times[0]
                process_elapsed = process.times - process.times[0]
                nearest = _nearest_process_indices(elapsed, process_elapsed)
                active = regions.active[nearest]
                active_elapsed = elapsed[active]
                duration = active_elapsed[-1] - active_elapsed[0]
                masks = {
                    "active": active,
                    "early": active & (elapsed <= active_elapsed[0] + 0.1 * duration),
                    "late": active & (elapsed >= active_elapsed[-1] - 0.1 * duration),
                    "long_phase": regions.long_phase[nearest],
                    "short_phase": regions.short_phase[nearest],
                }
                counts = {name: int(mask.sum()) for name, mask in masks.items()}
                if any(count == 0 for count in counts.values()):
                    raise ValueError(f"{key} has an empty aligned OES phase")
                sums = {name: np.zeros(len(wavelengths)) for name in masks}
                cycle_sums = np.zeros((regions.cycle_count, len(wavelengths)))
                cycle_counts = np.bincount(
                    regions.cycle_index[nearest][regions.cycle_index[nearest] >= 0],
                    minlength=regions.cycle_count,
                )

                encoded_variable = group["data"]
                for start in range(0, len(times), chunk_rows):
                    stop = min(start + chunk_rows, len(times))
                    encoded = np.asarray(encoded_variable[start:stop, :])
                    if encoded.max() >= len(decoder):
                        raise ValueError(f"{key} contains an invalid dictionary code")
                    decoded = decoder[encoded].astype(np.float64, copy=False)
                    normalized = decoded / np.maximum(decoded.sum(axis=1, keepdims=True), 1e-12)
                    for name, mask in masks.items():
                        local = mask[start:stop]
                        if local.any():
                            sums[name] += normalized[local].sum(axis=0)
                    local_cycles = regions.cycle_index[nearest][start:stop]
                    for cycle in np.unique(local_cycles[local_cycles >= 0]):
                        cycle_sums[cycle] += normalized[local_cycles == cycle].sum(axis=0)

                valid_cycles = cycle_counts > 0
                cycle_means = cycle_sums[valid_cycles] / cycle_counts[valid_cycles, None]
                summaries = {
                    **{name: sums[name] / count for name, count in counts.items()},
                    "cycle_slope": _vector_slope(cycle_means),
                }
                row: dict[str, float | str] = {"experiment_key": key}
                for name, values in summaries.items():
                    for wavelength, value in zip(wavelengths, values, strict=True):
                        row[f"shape_wl_{wavelength:.6f}__{name}"] = float(value)
                feature_rows.append(row)
                diagnostic_rows.append(
                    {
                        "experiment_key": key,
                        "normalized_spectral_summaries": len(summaries),
                        "aligned_cycles": int(valid_cycles.sum()),
                        "active_broadband_median": float("nan"),
                    }
                )

    features = pd.DataFrame(feature_rows).set_index("experiment_key").sort_index()
    diagnostics = pd.DataFrame(diagnostic_rows).set_index("experiment_key").sort_index()
    if not np.isfinite(features.to_numpy(dtype=float)).all():
        raise ValueError("normalized OES shape feature table contains non-finite values")
    return features, diagnostics

"""Target-free validation of BOSCH cycle and phase detection."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from etch_gate.data.process import ProcessTrace, detect_process_regions

DETECTORS = (
    "quantile",
    "complementary",
    "duration_filtered",
    "period_constrained",
)


@dataclass(frozen=True)
class CycleValidation:
    """Actual-wafer diagnostics and the target-free detector decision."""

    wafer_diagnostics: pd.DataFrame
    lot_summary: pd.DataFrame
    detector_summary: pd.DataFrame
    selected_detector: str


def _run_durations(
    mask: np.ndarray,
    times: np.ndarray,
) -> np.ndarray:
    changes = np.flatnonzero(np.diff(np.r_[False, mask, False].astype(int)))
    durations = []
    median_step = float(np.median(np.diff(times)))
    for start, stop in changes.reshape(-1, 2):
        durations.append(times[stop - 1] - times[start] + median_step)
    return np.asarray(durations, dtype=float)


def _finite_summary(values: np.ndarray, prefix: str) -> dict[str, float]:
    if len(values) == 0:
        return {
            f"{prefix}_count": 0.0,
            f"{prefix}_median_seconds": np.nan,
            f"{prefix}_p05_seconds": np.nan,
            f"{prefix}_p95_seconds": np.nan,
        }
    return {
        f"{prefix}_count": float(len(values)),
        f"{prefix}_median_seconds": float(np.median(values)),
        f"{prefix}_p05_seconds": float(np.quantile(values, 0.05)),
        f"{prefix}_p95_seconds": float(np.quantile(values, 0.95)),
    }


def diagnose_trace(
    trace: ProcessTrace,
    *,
    lot_number: int,
    detector: str,
    minimum_phase_duration_seconds: float = 0.5,
    expected_cycle_period_seconds: float = 6.0,
) -> dict[str, float | int | str | bool]:
    """Return complete finite diagnostics for one process wafer."""

    regions = detect_process_regions(
        trace,
        detector=detector,
        minimum_phase_duration_seconds=minimum_phase_duration_seconds,
        expected_cycle_period_seconds=expected_cycle_period_seconds,
    )
    active = regions.active
    active_samples = int(active.sum())
    overlap = regions.long_phase & regions.short_phase
    uncovered = active & ~regions.long_phase & ~regions.short_phase
    long_durations = _run_durations(regions.long_phase, trace.times)
    short_durations = _run_durations(regions.short_phase, trace.times)
    edge_times = trace.times[regions.rising_edge_indices]
    periods = np.diff(edge_times)
    time_steps = np.diff(trace.times)
    active_positions = np.flatnonzero(active)
    cycle_values = regions.cycle_index[active_positions]
    assigned = cycle_values[cycle_values >= 0]

    row: dict[str, float | int | str | bool] = {
        "experiment_key": trace.experiment_key,
        "lot_number": int(lot_number),
        "detector": detector,
        "active_start_seconds": regions.active_start_seconds,
        "active_end_seconds": regions.active_end_seconds,
        "active_duration_seconds": (
            regions.active_end_seconds - regions.active_start_seconds
        ),
        "detected_cycle_count": int(regions.cycle_count),
        "phase_overlap_samples": int(overlap.sum()),
        "phase_overlap_fraction": float(overlap.sum() / active_samples),
        "uncovered_active_samples": int(uncovered.sum()),
        "uncovered_active_fraction": float(uncovered.sum() / active_samples),
        "maximum_timestamp_gap_seconds": float(time_steps.max()),
        "median_timestamp_step_seconds": float(np.median(time_steps)),
        "first_edge_seconds": float(edge_times[0]),
        "last_edge_seconds": float(edge_times[-1]),
        "first_edge_inside_active": bool(
            regions.active_start_seconds <= edge_times[0] <= regions.active_end_seconds
        ),
        "last_edge_inside_active": bool(
            regions.active_start_seconds <= edge_times[-1] <= regions.active_end_seconds
        ),
        "cycle_index_monotonic": bool(
            len(assigned) < 2 or np.all(np.diff(assigned) >= 0)
        ),
    }
    row.update(_finite_summary(long_durations, "long_phase"))
    row.update(_finite_summary(short_durations, "short_phase"))
    row.update(_finite_summary(periods, "cycle_period"))
    return row


def _robust_absolute_z(values: pd.Series) -> np.ndarray:
    array = values.to_numpy(dtype=float)
    center = float(np.median(array))
    mad = float(np.median(np.abs(array - center)))
    if mad <= 1e-12:
        return np.zeros(len(array), dtype=float)
    return np.abs(array - center) / (1.4826 * mad)


def _select_detector(summary: pd.DataFrame) -> str:
    ranked = summary.sort_values(
        [
            "outside_95_105",
            "median_absolute_cycle_deviation",
            "mean_phase_overlap_fraction",
            "mean_uncovered_active_fraction",
            "detector_order",
        ],
        kind="stable",
    )
    return str(ranked.iloc[0]["detector"])


def validate_cycle_detection(
    traces: dict[str, ProcessTrace],
    lot_by_key: dict[str, int],
    *,
    detectors: tuple[str, ...] = DETECTORS,
    minimum_phase_duration_seconds: float = 0.5,
    expected_cycle_period_seconds: float = 6.0,
) -> CycleValidation:
    """Compare detectors without using a metrology target."""

    missing_lots = sorted(set(traces) - set(lot_by_key))
    if missing_lots:
        raise ValueError(f"missing lot numbers for process wafers: {missing_lots[:3]}")

    rows = []
    for detector in detectors:
        for key in sorted(traces):
            rows.append(
                diagnose_trace(
                    traces[key],
                    lot_number=lot_by_key[key],
                    detector=detector,
                    minimum_phase_duration_seconds=minimum_phase_duration_seconds,
                    expected_cycle_period_seconds=expected_cycle_period_seconds,
                )
            )
    all_diagnostics = pd.DataFrame(rows)
    numeric = all_diagnostics.select_dtypes(include=[np.number])
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        non_finite = numeric.columns[~np.isfinite(numeric).all()].tolist()
        raise ValueError(f"cycle diagnostics contain non-finite values: {non_finite}")

    detector_rows = []
    for detector_order, detector in enumerate(detectors):
        group = all_diagnostics[all_diagnostics["detector"] == detector]
        cycle_deviation = np.abs(group["detected_cycle_count"] - 100)
        detector_rows.append(
            {
                "detector": detector,
                "detector_order": detector_order,
                "wafer_count": len(group),
                "median_cycle_count": float(group["detected_cycle_count"].median()),
                "minimum_cycle_count": int(group["detected_cycle_count"].min()),
                "maximum_cycle_count": int(group["detected_cycle_count"].max()),
                "outside_95_105": int(
                    (~group["detected_cycle_count"].between(95, 105)).sum()
                ),
                "median_absolute_cycle_deviation": float(np.median(cycle_deviation)),
                "mean_phase_overlap_fraction": float(
                    group["phase_overlap_fraction"].mean()
                ),
                "mean_uncovered_active_fraction": float(
                    group["uncovered_active_fraction"].mean()
                ),
            }
        )
    detector_summary = pd.DataFrame(detector_rows)
    selected = _select_detector(detector_summary)
    wafer = (
        all_diagnostics[all_diagnostics["detector"] == selected]
        .copy()
        .reset_index(drop=True)
    )
    wafer["phase_duration_anomaly_score"] = np.maximum(
        _robust_absolute_z(wafer["long_phase_median_seconds"]),
        _robust_absolute_z(wafer["short_phase_median_seconds"]),
    )
    wafer["suspicious"] = (
        ~wafer["detected_cycle_count"].between(95, 105)
        | (wafer["phase_duration_anomaly_score"] > 3.5)
        | (wafer["phase_overlap_fraction"] > 0)
        | (wafer["uncovered_active_fraction"] > 0)
        | ~wafer["cycle_index_monotonic"]
        | ~wafer["first_edge_inside_active"]
        | ~wafer["last_edge_inside_active"]
    )

    lot_summary = (
        wafer.groupby("lot_number", as_index=False)
        .agg(
            wafer_count=("experiment_key", "size"),
            median_cycle_count=("detected_cycle_count", "median"),
            minimum_cycle_count=("detected_cycle_count", "min"),
            maximum_cycle_count=("detected_cycle_count", "max"),
            median_long_phase_seconds=("long_phase_median_seconds", "median"),
            median_short_phase_seconds=("short_phase_median_seconds", "median"),
            median_cycle_period_seconds=("cycle_period_median_seconds", "median"),
            suspicious_wafers=("suspicious", "sum"),
        )
        .sort_values("lot_number")
    )
    return CycleValidation(
        wafer_diagnostics=wafer,
        lot_summary=lot_summary,
        detector_summary=detector_summary,
        selected_detector=selected,
    )


def deterministic_example_keys(diagnostics: pd.DataFrame) -> dict[str, str]:
    """Select examples by declared rules rather than visual appearance."""

    ordered = diagnostics.sort_values("experiment_key")
    median_count = float(ordered["detected_cycle_count"].median())
    return {
        "median": str(
            ordered.assign(
                distance=(ordered["detected_cycle_count"] - median_count).abs()
            )
            .sort_values(["distance", "experiment_key"])
            .iloc[0]["experiment_key"]
        ),
        "minimum": str(
            ordered.sort_values(["detected_cycle_count", "experiment_key"])
            .iloc[0]["experiment_key"]
        ),
        "maximum": str(
            ordered.sort_values(
                ["detected_cycle_count", "experiment_key"],
                ascending=[False, True],
            ).iloc[0]["experiment_key"]
        ),
        "phase_anomaly": str(
            ordered.sort_values(
                ["phase_duration_anomaly_score", "experiment_key"],
                ascending=[False, True],
            ).iloc[0]["experiment_key"]
        ),
    }

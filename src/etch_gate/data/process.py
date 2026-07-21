"""Decode BOSCH process traces and extract compact cycle-aware features."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from netCDF4 import Dataset

from etch_gate.data.audit import process_group_to_key

SOURCE_RF = "Stat3_Etch_MV_SourceRFLoadPower"
LONG_PHASE_GAS = "Stat3_Etch_MV_Gas5Flow"
SHORT_PHASE_GAS = "Stat3_Etch_MV_Gas4Flow"


@dataclass(frozen=True)
class ProcessTrace:
    """One wafer's decoded common process signals."""

    experiment_key: str
    group_name: str
    times: np.ndarray
    values: pd.DataFrame


@dataclass(frozen=True)
class ProcessRegions:
    """Detected active-process and alternating BOSCH phase masks."""

    active: np.ndarray
    long_phase: np.ndarray
    short_phase: np.ndarray
    cycle_index: np.ndarray
    cycle_count: int
    active_start_seconds: float
    active_end_seconds: float


def load_process_traces(
    process_path: Path,
    dictionary_path: Path,
) -> dict[str, ProcessTrace]:
    """Decode every process group and retain only the 31 common signals."""

    with Dataset(dictionary_path) as dictionary:
        decoder = np.asarray(dictionary["data"][:])

    with Dataset(process_path) as dataset:
        feature_sets = [
            set(str(value) for value in group["feature"][:])
            for group in dataset.groups.values()
        ]
        common_features = sorted(set.intersection(*feature_sets))
        traces = {}
        for group_name, group in dataset.groups.items():
            group_features = [str(value) for value in group["feature"][:]]
            feature_positions = [group_features.index(name) for name in common_features]
            encoded = np.asarray(group["data"][:, feature_positions])
            if (encoded >= len(decoder)).any():
                raise ValueError(f"{group_name} contains an invalid dictionary code")
            decoded = decoder[encoded].astype(float)
            if not np.isfinite(decoded).all():
                raise ValueError(f"{group_name} contains a non-finite decoded value")

            key = process_group_to_key(group_name)
            if key in traces:
                raise ValueError(f"duplicate process experiment key: {key}")
            traces[key] = ProcessTrace(
                experiment_key=key,
                group_name=group_name,
                times=np.asarray(group["times"][:], dtype=float),
                values=pd.DataFrame(decoded, columns=common_features),
            )

    return traces


def _signal_threshold(values: np.ndarray) -> float:
    low, high = np.quantile(values, [0.05, 0.95])
    return float(low + 0.5 * (high - low))


def detect_process_regions(trace: ProcessTrace) -> ProcessRegions:
    """Detect the active RF window and long/short gas phases from real timestamps."""

    required = {SOURCE_RF, LONG_PHASE_GAS, SHORT_PHASE_GAS}
    missing = sorted(required - set(trace.values.columns))
    if missing:
        raise ValueError(f"trace is missing phase-detection signals: {missing}")
    if len(trace.times) != len(trace.values):
        raise ValueError("trace timestamps and process rows have different lengths")
    if len(trace.times) < 2 or np.any(np.diff(trace.times) <= 0):
        raise ValueError("trace timestamps must be strictly increasing")

    source = trace.values[SOURCE_RF].to_numpy(dtype=float)
    source_active = source > _signal_threshold(source)
    active_indices = np.flatnonzero(source_active)
    if len(active_indices) == 0:
        raise ValueError("no active source-RF window was detected")

    active_start_index = int(active_indices[0])
    active_end_index = int(active_indices[-1])
    active = np.zeros(len(trace.times), dtype=bool)
    active[active_start_index : active_end_index + 1] = True

    long_phase_signal = trace.values[LONG_PHASE_GAS].to_numpy(dtype=float)
    short_phase_signal = trace.values[SHORT_PHASE_GAS].to_numpy(dtype=float)
    long_phase = active & (
        long_phase_signal > _signal_threshold(long_phase_signal)
    )
    short_phase = active & (
        short_phase_signal > _signal_threshold(short_phase_signal)
    )

    rising_edges = np.flatnonzero(
        long_phase & ~np.r_[False, long_phase[:-1]]
    )
    retained_edges = []
    for edge in rising_edges:
        if (
            not retained_edges
            or trace.times[edge] - trace.times[retained_edges[-1]] > 3.0
        ):
            retained_edges.append(int(edge))
    if len(retained_edges) < 2:
        raise ValueError("fewer than two BOSCH cycles were detected")

    cycle_index = np.full(len(trace.times), -1, dtype=int)
    edge_times = trace.times[retained_edges]
    assigned = np.searchsorted(edge_times, trace.times, side="right") - 1
    valid = active & (assigned >= 0)
    cycle_index[valid] = assigned[valid]

    return ProcessRegions(
        active=active,
        long_phase=long_phase,
        short_phase=short_phase,
        cycle_index=cycle_index,
        cycle_count=len(retained_edges),
        active_start_seconds=float(trace.times[active_start_index]),
        active_end_seconds=float(trace.times[active_end_index]),
    )


def _normalized_slope(
    values: np.ndarray,
    positions: np.ndarray | None = None,
) -> float:
    if len(values) < 2:
        return 0.0
    if positions is None:
        x = np.linspace(0.0, 1.0, len(values))
    else:
        x = np.asarray(positions, dtype=float)
        duration = x[-1] - x[0]
        if duration <= 0:
            return 0.0
        x = (x - x[0]) / duration
    return float(np.polyfit(x, values, 1)[0])


def extract_trace_features(
    trace: ProcessTrace,
    regions: ProcessRegions,
) -> tuple[dict[str, float], dict[str, float]]:
    """Summarize every common signal over active, phase, and cycle views."""

    active_indices = np.flatnonzero(regions.active)
    if len(active_indices) < 10:
        raise ValueError("active process window is too short")
    active_times = trace.times[active_indices]
    active_duration = active_times[-1] - active_times[0]
    early_indices = active_indices[
        active_times <= active_times[0] + 0.1 * active_duration
    ]
    late_indices = active_indices[
        active_times >= active_times[-1] - 0.1 * active_duration
    ]

    features = {}
    for signal in trace.values.columns:
        values = trace.values[signal].to_numpy(dtype=float)
        active_values = values[regions.active]
        long_phase_values = values[regions.long_phase]
        short_phase_values = values[regions.short_phase]
        if len(long_phase_values) == 0 or len(short_phase_values) == 0:
            raise ValueError(f"{signal} has an empty detected BOSCH phase")

        cycle_means = []
        for cycle in range(regions.cycle_count):
            mask = regions.cycle_index == cycle
            if mask.any():
                cycle_means.append(float(values[mask].mean()))
        cycle_values = np.asarray(cycle_means, dtype=float)
        prefix = f"{signal}__"
        features.update(
            {
                prefix + "active_mean": float(active_values.mean()),
                prefix + "active_std": float(active_values.std(ddof=0)),
                prefix + "active_range": float(
                    np.quantile(active_values, 0.95)
                    - np.quantile(active_values, 0.05)
                ),
                prefix + "active_slope": _normalized_slope(
                    active_values, active_times
                ),
                prefix + "early_late_delta": float(
                    values[late_indices].mean() - values[early_indices].mean()
                ),
                prefix + "long_phase_mean": float(long_phase_values.mean()),
                prefix + "short_phase_mean": float(short_phase_values.mean()),
                prefix + "phase_difference": float(
                    long_phase_values.mean() - short_phase_values.mean()
                ),
                prefix + "cycle_mean_std": float(cycle_values.std(ddof=0)),
                prefix + "cycle_mean_slope": _normalized_slope(cycle_values),
            }
        )

    time_steps = np.diff(trace.times)
    active_time_steps = np.diff(trace.times[regions.active])
    diagnostics = {
        "samples": float(len(trace.times)),
        "median_step_seconds": float(np.median(time_steps)),
        "maximum_gap_seconds": float(time_steps.max()),
        "active_maximum_gap_seconds": float(active_time_steps.max()),
        "active_duration_seconds": (
            regions.active_end_seconds - regions.active_start_seconds
        ),
        "detected_cycles": float(regions.cycle_count),
        "long_phase_sample_fraction": float(
            regions.long_phase[regions.active].mean()
        ),
        "short_phase_sample_fraction": float(
            regions.short_phase[regions.active].mean()
        ),
    }
    return features, diagnostics


def build_process_feature_table(
    traces: dict[str, ProcessTrace],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create one fixed-width process-feature row and one diagnostic row per wafer."""

    feature_rows = []
    diagnostic_rows = []
    for key in sorted(traces):
        trace = traces[key]
        regions = detect_process_regions(trace)
        features, diagnostics = extract_trace_features(trace, regions)
        feature_rows.append({"experiment_key": key, **features})
        diagnostic_rows.append({"experiment_key": key, **diagnostics})

    feature_table = pd.DataFrame(feature_rows).set_index("experiment_key")
    diagnostic_table = pd.DataFrame(diagnostic_rows).set_index("experiment_key")
    if not np.isfinite(feature_table.to_numpy(dtype=float)).all():
        raise ValueError("process feature table contains non-finite values")
    return feature_table, diagnostic_table

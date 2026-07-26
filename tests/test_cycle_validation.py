import numpy as np
import pandas as pd

from etch_gate.analysis.cycle_validation import (
    deterministic_example_keys,
    diagnose_trace,
    validate_cycle_detection,
)
from etch_gate.data.process import (
    LONG_PHASE_GAS,
    SHORT_PHASE_GAS,
    SOURCE_RF,
    ProcessTrace,
    detect_process_regions,
)


def _trace(key: str, cycles: int = 8) -> ProcessTrace:
    period = 6.0
    times = np.arange(0.0, 6.0 + cycles * period, 0.2)
    active = (times >= 3.0) & (times < 3.0 + cycles * period)
    phase = np.mod(times - 3.0, period)
    values = pd.DataFrame(
        {
            SOURCE_RF: np.where(active, 100.0, 0.0),
            LONG_PHASE_GAS: np.where(active & (phase < 4.5), 600.0, 0.0),
            SHORT_PHASE_GAS: np.where(active & (phase >= 4.5), 300.0, 0.0),
            "sensor": times,
        }
    )
    return ProcessTrace(key, key, times, values)


def test_period_constrained_regions_obey_boundaries() -> None:
    trace = _trace("2025-01-01-01")
    regions = detect_process_regions(trace, detector="period_constrained")

    assert not regions.active[0]
    assert not (regions.long_phase & ~regions.active).any()
    assert not (regions.short_phase & ~regions.active).any()
    assigned = regions.cycle_index[regions.cycle_index >= 0]
    assert np.all(np.diff(assigned) >= 0)
    assert regions.active_start_seconds <= trace.times[regions.rising_edge_indices[0]]
    assert trace.times[regions.rising_edge_indices[-1]] <= regions.active_end_seconds


def test_cycle_diagnostics_are_finite_and_target_free() -> None:
    trace = _trace("2025-01-01-01")
    row = diagnose_trace(trace, lot_number=1, detector="period_constrained")
    numeric = [value for value in row.values() if isinstance(value, (int, float))]

    assert np.isfinite(numeric).all()
    assert row["detected_cycle_count"] == 8
    assert row["phase_overlap_samples"] == 0
    assert row["uncovered_active_samples"] == 0


def test_detector_comparison_and_example_selection_are_deterministic() -> None:
    traces = {
        "2025-01-01-01": _trace("2025-01-01-01", 7),
        "2025-01-01-02": _trace("2025-01-01-02", 8),
        "2025-01-02-01": _trace("2025-01-02-01", 9),
    }
    result = validate_cycle_detection(
        traces,
        {key: index // 2 + 1 for index, key in enumerate(sorted(traces))},
        detectors=("quantile", "period_constrained"),
        expected_cycle_period_seconds=6.0,
    )
    examples = deterministic_example_keys(result.wafer_diagnostics)

    assert len(result.wafer_diagnostics) == 3
    assert set(examples) == {"median", "minimum", "maximum", "phase_anomaly"}

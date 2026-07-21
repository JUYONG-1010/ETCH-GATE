import numpy as np
import pandas as pd

from etch_gate.data.process import (
    LONG_PHASE_GAS,
    SHORT_PHASE_GAS,
    SOURCE_RF,
    ProcessTrace,
    detect_process_regions,
    extract_trace_features,
)


def _synthetic_trace() -> ProcessTrace:
    times = np.arange(0.0, 30.0, 0.2)
    source = np.zeros_like(times)
    source[(times >= 3.0) & (times < 27.0)] = 100.0
    long_phase = np.zeros_like(times)
    short_phase = np.zeros_like(times)
    active_time = times - 3.0
    active = (active_time >= 0) & (active_time < 24.0)
    phase_time = np.mod(active_time, 6.0)
    long_phase[active & (phase_time < 4.5)] = 600.0
    short_phase[active & (phase_time >= 4.5)] = 300.0
    drift = times * 2.0
    values = pd.DataFrame(
        {
            SOURCE_RF: source,
            LONG_PHASE_GAS: long_phase,
            SHORT_PHASE_GAS: short_phase,
            "sensor_with_drift": drift,
        }
    )
    return ProcessTrace(
        experiment_key="synthetic_01",
        group_name="synthetic",
        times=times,
        values=values,
    )


def test_detect_process_regions_finds_active_window_and_cycles() -> None:
    trace = _synthetic_trace()

    regions = detect_process_regions(trace)

    assert regions.cycle_count == 4
    assert regions.active_start_seconds == 3.0
    assert regions.active_end_seconds == 26.8
    assert regions.long_phase.sum() > regions.short_phase.sum()


def test_extract_trace_features_preserves_drift_direction() -> None:
    trace = _synthetic_trace()
    regions = detect_process_regions(trace)

    features, diagnostics = extract_trace_features(trace, regions)

    assert features["sensor_with_drift__active_slope"] > 0
    assert features["sensor_with_drift__early_late_delta"] > 0
    assert diagnostics["detected_cycles"] == 4
    assert diagnostics["active_duration_seconds"] > 23

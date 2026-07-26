import numpy as np
import pandas as pd

from etch_gate.analysis.uncertainty_calibration import (
    conformal_quantile,
    evaluate_conformal_uncertainty,
)


def _problem() -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_rows = []
    dense_rows = []
    for lot in range(1, 7):
        for wafer in range(4):
            key = f"2025-01-{lot:02d}_{wafer:02d}"
            process = lot + wafer / 4
            feature_rows.append(
                {"experiment_key": key, "signal_a": process, "signal_b": process**2}
            )
            for point in range(3):
                dense_rows.append(
                    {
                        "experiment_key": key,
                        "lot_number": lot,
                        "X": float(point),
                        "Y": 0.0,
                        "stepheight": 10 + point + 0.2 * process,
                    }
                )
    return (
        pd.DataFrame(feature_rows).set_index("experiment_key"),
        pd.DataFrame(dense_rows),
    )


def test_conformal_quantile_reports_unattainable_small_sample_level() -> None:
    bound, rank, attainable, resolution = conformal_quantile(
        np.arange(10, dtype=float),
        0.95,
    )

    assert bound == 9
    assert rank == 10
    assert not attainable
    assert np.isclose(resolution, 1 / 11)


def test_outer_test_targets_cannot_change_prediction_or_interval_width() -> None:
    features, dense = _problem()
    changed = dense.copy()
    changed.loc[changed["lot_number"] == 4, "stepheight"] += 1000
    options = {
        "nominal_coverages": (0.8,),
        "minimum_fit_lots": 2,
        "maximum_residual_components": 2,
    }

    original = evaluate_conformal_uncertainty(features, dense, **options)
    perturbed = evaluate_conformal_uncertainty(features, changed, **options)
    original_points = original.point_diagnostics[
        original.point_diagnostics["test_lot"] == 4
    ]
    changed_points = perturbed.point_diagnostics[
        perturbed.point_diagnostics["test_lot"] == 4
    ]

    assert np.allclose(original_points["predicted"], changed_points["predicted"])
    assert np.allclose(
        original_points["point_half_width"],
        changed_points["point_half_width"],
    )
    assert not np.allclose(
        original_points["absolute_error"],
        changed_points["absolute_error"],
    )

import numpy as np
import pandas as pd

from etch_gate.analysis.chronological import (
    evaluate_chronological_vm,
    expanding_window_splits,
)


def _problem() -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_rows = []
    dense_rows = []
    for lot in range(1, 6):
        for wafer in range(3):
            key = f"2025-01-{lot:02d}_{wafer:02d}"
            value = lot + wafer / 3
            feature_rows.append({"experiment_key": key, "signal": value})
            for point in range(3):
                dense_rows.append(
                    {
                        "experiment_key": key,
                        "lot_number": lot,
                        "X": float(point),
                        "Y": 0.0,
                        "stepheight": 10 + point + 0.2 * value,
                    }
                )
    return (
        pd.DataFrame(feature_rows).set_index("experiment_key"),
        pd.DataFrame(dense_rows),
    )


def test_expanding_window_never_uses_future_lots() -> None:
    lots = np.repeat(np.arange(1, 7), 2)
    splits = expanding_window_splits(lots, minimum_training_lots=3)

    assert [test_lot for _, _, test_lot in splits] == [4, 5, 6]
    for train, test, test_lot in splits:
        assert lots[train].max() < test_lot
        assert np.unique(lots[test]).tolist() == [test_lot]


def test_current_forward_prediction_ignores_current_target_and_future_features() -> None:
    features, dense = _problem()
    changed_target = dense.copy()
    changed_target.loc[changed_target["lot_number"] == 4, "stepheight"] += 1000
    changed_future = features.copy()
    changed_future.loc[changed_future.index.str.contains("01-05"), "signal"] += 1000
    kwargs = {
        "families": ("ridge",),
        "minimum_training_lots": 3,
        "ridge_parameters": (1.0,),
        "maximum_residual_components": 2,
    }

    original = evaluate_chronological_vm(features, dense, **kwargs)
    perturbed_target = evaluate_chronological_vm(features, changed_target, **kwargs)
    perturbed_future = evaluate_chronological_vm(changed_future, dense, **kwargs)

    def lot_four(result):
        return result.point_predictions[
            result.point_predictions["lot_number"] == 4
        ].sort_values(["experiment_key", "stage", "X", "Y"])["predicted"]

    assert np.allclose(lot_four(original), lot_four(perturbed_target))
    assert np.allclose(lot_four(original), lot_four(perturbed_future))

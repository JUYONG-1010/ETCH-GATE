import numpy as np
import pandas as pd

from etch_gate.analysis.causal_replay import (
    causal_quota_decisions,
    evaluate_causal_replay,
)


def _problem() -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_rows = []
    dense_rows = []
    for lot in range(1, 5):
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


def test_causal_quota_never_uses_future_ranking_and_meets_rounded_budget() -> None:
    scores = np.array([0.95, 0.10, 0.90, 0.20, 0.80])

    selected = causal_quota_decisions(scores, budget=0.4, threshold=0.6)

    assert selected.sum() == 2
    assert selected.tolist() == [True, False, True, False, False]


def test_future_target_cannot_change_earlier_risk_decision_or_prediction() -> None:
    features, dense = _problem()
    changed = dense.copy()
    last_key = "2025-01-04_03"
    changed.loc[changed["experiment_key"] == last_key, "stepheight"] += 1000
    options = {
        "minimum_training_lots": 3,
        "budgets": (0.5,),
        "random_replicates": 2,
        "bootstrap_replicates": 20,
        "maximum_residual_components": 2,
    }

    original = evaluate_causal_replay(features, dense, **options).wafer_timeline
    perturbed = evaluate_causal_replay(features, changed, **options).wafer_timeline
    columns = [
        "risk",
        "measured",
        "vm_error_before_measurement",
        "system_error",
    ]
    earlier = (
        (original["mode"] == "causal_feedback")
        & (original["wafer_order"] < 4)
    )

    assert np.allclose(
        original.loc[earlier, columns].astype(float),
        perturbed.loc[earlier, columns].astype(float),
        equal_nan=True,
    )

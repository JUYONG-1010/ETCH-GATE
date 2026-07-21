import numpy as np
import pandas as pd

from etch_gate.analysis.drift import evaluate_drift_risk


def _problem() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    feature_rows = []
    dense_rows = []
    fold_rows = []
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
        for family in ("ridge", "pls"):
            fold_rows.append(
                {
                    "held_out_lot": lot,
                    "family": family,
                    "mean_parameter": 1.0,
                    "residual_parameter": 1.0,
                }
            )
    return (
        pd.DataFrame(feature_rows).set_index("experiment_key"),
        pd.DataFrame(dense_rows),
        pd.DataFrame(fold_rows),
    )


def test_drift_evaluation_returns_every_policy_and_wafer() -> None:
    features, dense, folds = _problem()

    result = evaluate_drift_risk(
        features,
        dense,
        folds,
        pca_components=2,
        budgets=(0.0, 0.5),
        random_replicates=20,
        maximum_residual_components=2,
    )

    assert len(result.wafer_scores) == 16
    assert set(result.lot_summary["policy"]) == {
        "random",
        "periodic",
        "ood",
        "delta",
        "ewma",
        "disagreement",
        "combined",
        "oracle",
    }
    assert np.isfinite(result.wafer_scores["combined_risk"]).all()


def test_held_out_targets_cannot_change_target_free_scores() -> None:
    features, dense, folds = _problem()
    changed = dense.copy()
    changed.loc[changed["lot_number"] == 1, "stepheight"] += 1000

    original = evaluate_drift_risk(
        features,
        dense,
        folds,
        pca_components=2,
        budgets=(0.0, 0.5),
        random_replicates=10,
        maximum_residual_components=2,
    ).wafer_scores
    perturbed = evaluate_drift_risk(
        features,
        changed,
        folds,
        pca_components=2,
        budgets=(0.0, 0.5),
        random_replicates=10,
        maximum_residual_components=2,
    ).wafer_scores

    columns = [
        "ood_percentile",
        "delta_percentile",
        "ewma_percentile",
        "disagreement_percentile",
        "combined_risk",
    ]
    assert np.allclose(
        original.loc[original["lot_number"] == 1, columns],
        perturbed.loc[perturbed["lot_number"] == 1, columns],
    )
    assert not np.allclose(
        original.loc[original["lot_number"] == 1, "true_pls_mae"],
        perturbed.loc[perturbed["lot_number"] == 1, "true_pls_mae"],
    )

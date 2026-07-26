import numpy as np
import pandas as pd

from etch_gate.analysis.drift import (
    evaluate_drift_risk,
    sequential_change_scores,
    summarize_policy_robustness,
)


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
        "initial_state",
        "delta",
        "ewma",
        "disagreement",
        "combined",
        "training_weighted_candidate",
        "oracle",
    }
    assert np.isfinite(result.wafer_scores["combined_risk"]).all()
    first = (
        result.wafer_scores.sort_values(["lot_number", "experiment_key"])
        .groupby("lot_number")
        .head(1)
    )
    assert np.allclose(first["delta_percentile"], 0.5)
    assert np.allclose(first["ewma_percentile"], 0.5)


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
        "initial_state_percentile",
        "delta_percentile",
        "ewma_percentile",
        "disagreement_percentile",
        "combined_risk",
        "training_weighted_risk",
    ]
    assert np.allclose(
        original.loc[original["lot_number"] == 1, columns],
        perturbed.loc[perturbed["lot_number"] == 1, columns],
    )
    assert not np.allclose(
        original.loc[original["lot_number"] == 1, "true_pls_mae"],
        perturbed.loc[perturbed["lot_number"] == 1, "true_pls_mae"],
    )


def test_sequential_change_uses_alpha_and_never_uses_zero_origin_as_previous() -> None:
    values = np.array([[10.0], [12.0], [13.0]])

    initial, delta, slow = sequential_change_scores(
        values,
        centroid=np.array([11.0]),
        ewma_alpha=0.1,
    )
    _, _, fast = sequential_change_scores(
        values,
        centroid=np.array([11.0]),
        ewma_alpha=0.5,
    )

    assert np.allclose(initial, [1.0, 1.0, 2.0])
    assert np.isnan(delta[0])
    assert np.allclose(delta[1:], [2.0, 1.0])
    assert np.isnan(slow[0])
    assert slow[2] > fast[2]


def test_lot_cluster_bootstrap_is_reproducible() -> None:
    summary = pd.DataFrame(
        {
            "lot_number": np.repeat([1, 2, 3], 2),
            "policy": ["random", "combined"] * 3,
            "aurc": [0.3, 0.2, 0.4, 0.35, 0.5, 0.3],
        }
    )

    _, first = summarize_policy_robustness(
        summary,
        bootstrap_replicates=100,
        random_seed=9,
    )
    _, second = summarize_policy_robustness(
        summary,
        bootstrap_replicates=100,
        random_seed=9,
    )

    assert first.equals(second)

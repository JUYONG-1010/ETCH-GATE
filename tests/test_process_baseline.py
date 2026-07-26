import numpy as np
import pandas as pd

from etch_gate.analysis.process_baseline import (
    GPRSettings,
    evaluate_process_baselines,
    fit_residual_basis,
    prepare_feature_transform,
)


def _small_problem() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    features = []
    coordinates = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    for lot in range(3):
        for wafer in range(3):
            key = f"lot{lot}_wafer{wafer}"
            process_value = float(lot * 3 + wafer)
            features.append(
                {"experiment_key": key, "signal": process_value, "constant": 1.0}
            )
            for point, (x, y) in enumerate(coordinates):
                rows.append(
                    {
                        "experiment_key": key,
                        "lot_number": lot,
                        "X": x,
                        "Y": y,
                        "stepheight": 10.0 + point + 0.2 * process_value,
                    }
                )
    return (
        pd.DataFrame(features).set_index("experiment_key"),
        pd.DataFrame(rows),
    )


def test_feature_transform_removes_training_constant() -> None:
    values = np.array([[1.0, 3.0], [2.0, 3.0], [4.0, 3.0]])
    transform = prepare_feature_transform(values)

    assert transform.retained.tolist() == [True, False]
    assert np.allclose(transform.apply(values).mean(axis=0), 0.0)


def test_residual_basis_has_bounded_components() -> None:
    residuals = np.arange(30, dtype=float).reshape(10, 3)
    basis = fit_residual_basis(residuals, maximum_components=2)

    assert 1 <= len(basis.components) <= 2
    assert basis.inverse_transform(basis.transform(residuals)).shape == residuals.shape


def test_nested_lolo_returns_every_wafer_and_stage() -> None:
    features, dense = _small_problem()

    points, wafers, folds = evaluate_process_baselines(
        features,
        dense,
        families=("ridge",),
        ridge_parameters=(1.0,),
        maximum_residual_components=2,
    )

    assert len(folds) == 3
    assert wafers["experiment_key"].nunique() == 9
    assert set(wafers["stage"]) == {"template", "mean_shift", "full_map"}
    assert len(points) == 9 * 3 * 3


def test_held_out_lot_targets_cannot_change_its_predictions() -> None:
    features, dense = _small_problem()
    changed = dense.copy()
    changed.loc[changed["lot_number"] == 0, "stepheight"] += 1000.0

    original, _, _ = evaluate_process_baselines(
        features,
        dense,
        families=("ridge",),
        ridge_parameters=(1.0,),
        maximum_residual_components=2,
    )
    perturbed, _, _ = evaluate_process_baselines(
        features,
        changed,
        families=("ridge",),
        ridge_parameters=(1.0,),
        maximum_residual_components=2,
    )
    original_lot = original[original["lot_number"] == 0].sort_values(
        ["experiment_key", "stage", "X", "Y"]
    )
    perturbed_lot = perturbed[perturbed["lot_number"] == 0].sort_values(
        ["experiment_key", "stage", "X", "Y"]
    )

    assert np.allclose(original_lot["predicted"], perturbed_lot["predicted"])


def test_gpr_returns_positive_uncertainty_without_test_target_access() -> None:
    features, dense = _small_problem()
    changed = dense.copy()
    changed.loc[changed["lot_number"] == 0, "stepheight"] += 1000.0
    settings = (GPRSettings(2, 2.0, 0.01),)

    original, wafers, _ = evaluate_process_baselines(
        features,
        dense,
        families=("gpr",),
        gpr_parameters=settings,
        maximum_residual_components=2,
    )
    perturbed, _, _ = evaluate_process_baselines(
        features,
        changed,
        families=("gpr",),
        gpr_parameters=settings,
        maximum_residual_components=2,
    )
    modeled_points = original[original["stage"].isin(["mean_shift", "full_map"])]
    assert np.isfinite(modeled_points["predicted_std"]).all()
    assert (modeled_points["predicted_std"] > 0).all()
    assert np.isfinite(
        wafers.loc[wafers["stage"].isin(["mean_shift", "full_map"]), "mean_predicted_std"]
    ).all()

    original_lot = original[original["lot_number"] == 0].sort_values(
        ["experiment_key", "stage", "X", "Y"]
    )
    perturbed_lot = perturbed[perturbed["lot_number"] == 0].sort_values(
        ["experiment_key", "stage", "X", "Y"]
    )
    assert np.allclose(original_lot["predicted"], perturbed_lot["predicted"])
    assert np.allclose(
        original_lot["predicted_std"],
        perturbed_lot["predicted_std"],
        equal_nan=True,
    )

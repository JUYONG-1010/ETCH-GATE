"""Strict expanding-window virtual-metrology evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from etch_gate.analysis.process_baseline import (
    GPRSettings,
    decompose_maps,
    evaluate_process_baselines,
    fit_regressor,
    fit_residual_basis,
    ordered_dense_maps,
    predict_regressor,
    prepare_feature_transform,
    select_parameter,
    validate_feature_table,
)


@dataclass(frozen=True)
class ChronologicalResult:
    """Forward predictions, fold diagnostics, and LOLO comparison."""

    point_predictions: pd.DataFrame
    wafer_metrics: pd.DataFrame
    fold_diagnostics: pd.DataFrame
    comparison: pd.DataFrame


def expanding_window_splits(
    lots: np.ndarray,
    *,
    minimum_training_lots: int = 3,
) -> list[tuple[np.ndarray, np.ndarray, int]]:
    """Return train/test indices where every training lot precedes the test lot."""

    unique_lots = np.asarray(sorted(np.unique(lots)))
    if len(unique_lots) <= minimum_training_lots:
        raise ValueError("not enough lots for expanding-window evaluation")
    splits = []
    for position in range(minimum_training_lots, len(unique_lots)):
        test_lot = int(unique_lots[position])
        training_lots = unique_lots[:position]
        train = np.flatnonzero(np.isin(lots, training_lots))
        test = np.flatnonzero(lots == test_lot)
        if lots[train].max() >= test_lot:
            raise ValueError("chronological split includes a future training lot")
        splits.append((train, test, test_lot))
    return splits


def _family_parameters(
    family: str,
    *,
    ridge_parameters: tuple[float, ...],
    pls_parameters: tuple[float, ...],
    gpr_parameters: tuple[GPRSettings, ...],
) -> list[float | GPRSettings]:
    if family == "ridge":
        return list(ridge_parameters)
    if family == "pls":
        return list(pls_parameters)
    if family == "gpr":
        return list(gpr_parameters)
    raise ValueError(f"unknown model family: {family}")


def _evaluate_forward(
    feature_table: pd.DataFrame,
    dense: pd.DataFrame,
    *,
    families: tuple[str, ...],
    minimum_training_lots: int,
    ridge_parameters: tuple[float, ...],
    pls_parameters: tuple[float, ...],
    gpr_parameters: tuple[GPRSettings, ...],
    residual_variance_target: float,
    maximum_residual_components: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    wafer_rows, coordinates, maps, lots = ordered_dense_maps(
        dense, set(feature_table.index)
    )
    keys = wafer_rows["experiment_key"].tolist()
    raw_features = feature_table.loc[keys].to_numpy(dtype=float)
    point_rows = []
    wafer_rows_out = []
    fold_rows = []
    for train_indices, test_indices, test_lot in expanding_window_splits(
        lots, minimum_training_lots=minimum_training_lots
    ):
        train_mask = np.zeros(len(lots), dtype=bool)
        test_mask = np.zeros(len(lots), dtype=bool)
        train_mask[train_indices] = True
        test_mask[test_indices] = True
        transform = prepare_feature_transform(raw_features[train_mask])
        x_train = transform.apply(raw_features[train_mask])
        x_test = transform.apply(raw_features[test_mask])
        (
            reference,
            template,
            training_shift,
            _,
            training_residual,
            _,
        ) = decompose_maps(maps[train_mask], maps[test_mask])
        baseline = np.broadcast_to(
            reference + template, maps[test_mask].shape
        )
        for family in families:
            parameters = _family_parameters(
                family,
                ridge_parameters=ridge_parameters,
                pls_parameters=pls_parameters,
                gpr_parameters=gpr_parameters,
            )
            mean_parameter, mean_inner_score = select_parameter(
                raw_features[train_mask],
                maps[train_mask],
                lots[train_mask],
                family=family,
                parameters=parameters,
                target_part="mean_shift",
                variance_target=residual_variance_target,
                maximum_components=maximum_residual_components,
            )
            residual_parameter, residual_inner_score = select_parameter(
                raw_features[train_mask],
                maps[train_mask],
                lots[train_mask],
                family=family,
                parameters=parameters,
                target_part="residual",
                variance_target=residual_variance_target,
                maximum_components=maximum_residual_components,
            )
            mean_model = fit_regressor(
                family, mean_parameter, x_train, training_shift
            )
            predicted_shift = predict_regressor(mean_model, x_test)[:, 0]
            mean_only = baseline + predicted_shift[:, None]
            basis = fit_residual_basis(
                training_residual,
                variance_target=residual_variance_target,
                maximum_components=maximum_residual_components,
            )
            residual_model = fit_regressor(
                family,
                residual_parameter,
                x_train,
                basis.transform(training_residual),
            )
            predicted_residual = basis.inverse_transform(
                predict_regressor(residual_model, x_test)
            )
            full = mean_only + predicted_residual
            fold_rows.append(
                {
                    "test_lot": test_lot,
                    "family": family,
                    "training_lots": ",".join(map(str, sorted(np.unique(lots[train_mask])))),
                    "maximum_training_lot": int(lots[train_mask].max()),
                    "training_wafers": int(train_mask.sum()),
                    "test_wafers": int(test_mask.sum()),
                    "retained_features": int(transform.retained.sum()),
                    "mean_parameter": str(mean_parameter),
                    "mean_inner_lot_macro_mae": mean_inner_score,
                    "residual_parameter": str(residual_parameter),
                    "residual_inner_lot_macro_rmse": residual_inner_score,
                    "residual_components": len(basis.components),
                }
            )
            for local_index, global_index in enumerate(test_indices):
                observed = maps[global_index]
                for stage, prediction in (
                    ("template", baseline[local_index]),
                    ("mean_shift", mean_only[local_index]),
                    ("full_map", full[local_index]),
                ):
                    error = prediction - observed
                    observed_centered = observed - observed.mean()
                    predicted_centered = prediction - prediction.mean()
                    residual_error = predicted_centered - observed_centered
                    wafer_rows_out.append(
                        {
                            "experiment_key": keys[global_index],
                            "lot_number": int(lots[global_index]),
                            "family": family,
                            "stage": stage,
                            "mae": float(np.mean(np.abs(error))),
                            "rmse": float(np.sqrt(np.mean(np.square(error)))),
                            "mean_shift_absolute_error": float(abs(error.mean())),
                            "residual_profile_mae": float(
                                np.mean(np.abs(residual_error))
                            ),
                            "residual_profile_rmse": float(
                                np.sqrt(np.mean(np.square(residual_error)))
                            ),
                        }
                    )
                    for point, (x, y) in enumerate(coordinates):
                        point_rows.append(
                            {
                                "experiment_key": keys[global_index],
                                "lot_number": int(lots[global_index]),
                                "family": family,
                                "stage": stage,
                                "X": float(x),
                                "Y": float(y),
                                "observed": float(observed[point]),
                                "predicted": float(prediction[point]),
                            }
                        )
    return (
        pd.DataFrame(point_rows),
        pd.DataFrame(wafer_rows_out),
        pd.DataFrame(fold_rows),
    )


def _comparison(
    chronological: pd.DataFrame,
    lolo: pd.DataFrame,
) -> pd.DataFrame:
    lolo_full = lolo[lolo["stage"] == "full_map"].copy()
    chronological_full = chronological[chronological["stage"] == "full_map"].copy()
    rows = []
    for family in sorted(chronological_full["family"].unique()):
        forward_family = chronological_full[
            chronological_full["family"] == family
        ]
        eligible_lots = sorted(forward_family["lot_number"].unique())
        lolo_family = lolo_full[
            (lolo_full["family"] == family)
            & (lolo_full["lot_number"].isin(eligible_lots))
        ]
        lolo_lots = lolo_family.groupby("lot_number")["mae"].mean()
        forward_lots = forward_family.groupby("lot_number")["mae"].mean()
        lolo_macro = float(lolo_lots.mean())
        forward_macro = float(forward_lots.mean())
        for lot in eligible_lots:
            rows.append(
                {
                    "scope": "lot",
                    "family": family,
                    "lot_number": int(lot),
                    "lolo_mae": float(lolo_lots.loc[lot]),
                    "chronological_mae": float(forward_lots.loc[lot]),
                    "relative_degradation": float(
                        forward_lots.loc[lot] / lolo_lots.loc[lot] - 1
                    ),
                }
            )
        rows.append(
            {
                "scope": "macro",
                "family": family,
                "lot_number": np.nan,
                "lolo_mae": lolo_macro,
                "chronological_mae": forward_macro,
                "relative_degradation": forward_macro / lolo_macro - 1,
            }
        )
    return pd.DataFrame(rows)


def evaluate_chronological_vm(
    feature_table: pd.DataFrame,
    dense: pd.DataFrame,
    *,
    families: tuple[str, ...] = ("ridge", "pls"),
    minimum_training_lots: int = 3,
    ridge_parameters: tuple[float, ...] = (0.1, 1.0, 10.0, 100.0, 1000.0),
    pls_parameters: tuple[float, ...] = (1.0, 2.0, 4.0),
    gpr_parameters: tuple[GPRSettings, ...] = (
        GPRSettings(8, 3.0, 0.05, optimize_kernel=True),
    ),
    residual_variance_target: float = 0.90,
    maximum_residual_components: int = 8,
) -> ChronologicalResult:
    """Compare nested LOLO with a strictly past-to-future evaluation."""

    validate_feature_table(feature_table)
    points, wafers, folds = _evaluate_forward(
        feature_table,
        dense,
        families=families,
        minimum_training_lots=minimum_training_lots,
        ridge_parameters=ridge_parameters,
        pls_parameters=pls_parameters,
        gpr_parameters=gpr_parameters,
        residual_variance_target=residual_variance_target,
        maximum_residual_components=maximum_residual_components,
    )
    _, lolo_wafers, _ = evaluate_process_baselines(
        feature_table,
        dense,
        families=families,
        ridge_parameters=ridge_parameters,
        pls_parameters=pls_parameters,
        gpr_parameters=gpr_parameters,
        residual_variance_target=residual_variance_target,
        maximum_residual_components=maximum_residual_components,
    )
    return ChronologicalResult(
        point_predictions=points,
        wafer_metrics=wafers,
        fold_diagnostics=folds,
        comparison=_comparison(wafers, lolo_wafers),
    )

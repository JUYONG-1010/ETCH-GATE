"""Group-aware split-conformal intervals for dense wafer-map VM."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from etch_gate.analysis.process_baseline import (
    decompose_maps,
    fit_regressor,
    fit_residual_basis,
    ordered_dense_maps,
    predict_regressor,
    prepare_feature_transform,
    select_parameter,
    validate_feature_table,
)


@dataclass(frozen=True)
class ConformalResult:
    """Coverage summaries, lot diagnostics, and point-level interval checks."""

    coverage_summary: pd.DataFrame
    lot_coverage: pd.DataFrame
    point_diagnostics: pd.DataFrame


def conformal_quantile(
    scores: np.ndarray,
    nominal_coverage: float,
) -> tuple[float, int, bool, float]:
    """Return finite-sample split-conformal order statistic and resolution."""

    values = np.sort(np.asarray(scores, dtype=float))
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("conformal scores must be a finite non-empty vector")
    if not 0 < nominal_coverage < 1:
        raise ValueError("nominal_coverage must be in (0, 1)")
    raw_rank = int(np.ceil((len(values) + 1) * nominal_coverage))
    attainable = raw_rank <= len(values)
    rank = min(raw_rank, len(values))
    return float(values[rank - 1]), rank, attainable, 1 / (len(values) + 1)


def _predict_map_model(
    x: np.ndarray,
    *,
    reference: float,
    template: np.ndarray,
    basis: object,
    mean_model: object,
    residual_model: object,
) -> np.ndarray:
    shift = predict_regressor(mean_model, x)[:, 0]
    residual = basis.inverse_transform(predict_regressor(residual_model, x))
    return reference + template + shift[:, None] + residual


def evaluate_conformal_uncertainty(
    feature_table: pd.DataFrame,
    dense: pd.DataFrame,
    *,
    nominal_coverages: tuple[float, ...] = (0.80, 0.90, 0.95),
    minimum_fit_lots: int = 2,
    pls_parameters: tuple[float, ...] = (1.0, 2.0, 4.0),
    residual_variance_target: float = 0.90,
    maximum_residual_components: int = 8,
) -> ConformalResult:
    """Evaluate prior-lot calibration and strictly later outer test lots."""

    validate_feature_table(feature_table)
    wafer_table, coordinates, maps, lots = ordered_dense_maps(
        dense,
        set(feature_table.index),
    )
    keys = wafer_table["experiment_key"].to_numpy()
    features = feature_table.loc[keys].to_numpy(dtype=float)
    unique_lots = np.asarray(sorted(np.unique(lots)))
    lot_rows: list[dict[str, float | int | bool]] = []
    point_rows: list[dict[str, float | int | str | bool]] = []

    for test_position in range(minimum_fit_lots + 1, len(unique_lots)):
        test_lot = int(unique_lots[test_position])
        calibration_lot = int(unique_lots[test_position - 1])
        fit_lots = unique_lots[: test_position - 1]
        fit = np.isin(lots, fit_lots)
        calibration = lots == calibration_lot
        test = lots == test_lot
        transform = prepare_feature_transform(features[fit])
        x_fit = transform.apply(features[fit])
        x_calibration = transform.apply(features[calibration])
        x_test = transform.apply(features[test])
        (
            reference,
            template,
            fit_shift,
            _,
            fit_residual,
            _,
        ) = decompose_maps(maps[fit], maps[calibration])
        basis = fit_residual_basis(
            fit_residual,
            variance_target=residual_variance_target,
            maximum_components=maximum_residual_components,
        )
        mean_parameter, _ = select_parameter(
            features[fit],
            maps[fit],
            lots[fit],
            family="pls",
            parameters=list(pls_parameters),
            target_part="mean_shift",
            variance_target=residual_variance_target,
            maximum_components=maximum_residual_components,
        )
        residual_parameter, _ = select_parameter(
            features[fit],
            maps[fit],
            lots[fit],
            family="pls",
            parameters=list(pls_parameters),
            target_part="residual",
            variance_target=residual_variance_target,
            maximum_components=maximum_residual_components,
        )
        mean_model = fit_regressor("pls", mean_parameter, x_fit, fit_shift)
        residual_model = fit_regressor(
            "pls",
            residual_parameter,
            x_fit,
            basis.transform(fit_residual),
        )
        calibration_prediction = _predict_map_model(
            x_calibration,
            reference=reference,
            template=template,
            basis=basis,
            mean_model=mean_model,
            residual_model=residual_model,
        )
        test_prediction = _predict_map_model(
            x_test,
            reference=reference,
            template=template,
            basis=basis,
            mean_model=mean_model,
            residual_model=residual_model,
        )
        calibration_error = np.abs(calibration_prediction - maps[calibration])
        test_error = np.abs(test_prediction - maps[test])
        template_error = np.abs(reference + template - maps[test])
        calibration_count = int(calibration.sum())

        for nominal in nominal_coverages:
            point_bounds = np.array(
                [
                    conformal_quantile(calibration_error[:, point], nominal)[0]
                    for point in range(calibration_error.shape[1])
                ]
            )
            point_rank_data = conformal_quantile(
                calibration_error[:, 0],
                nominal,
            )
            simultaneous_bound, simultaneous_rank, simultaneous_attainable, _ = (
                conformal_quantile(calibration_error.max(axis=1), nominal)
            )
            point_covered = test_error <= point_bounds
            simultaneous_covered = (test_error <= simultaneous_bound).all(axis=1)
            lot_rows.append(
                {
                    "test_lot": test_lot,
                    "calibration_lot": calibration_lot,
                    "fit_maximum_lot": int(max(fit_lots)),
                    "fit_wafers": int(fit.sum()),
                    "calibration_wafers": calibration_count,
                    "nominal_coverage": nominal,
                    "point_empirical_coverage": float(point_covered.mean()),
                    "simultaneous_map_coverage": float(
                        simultaneous_covered.mean()
                    ),
                    "mean_point_interval_width": float(2 * point_bounds.mean()),
                    "simultaneous_interval_width": float(
                        2 * simultaneous_bound
                    ),
                    "template_baseline_mae": float(template_error.mean()),
                    "point_half_width_vs_template_mae": float(
                        point_bounds.mean() / template_error.mean()
                    ),
                    "point_quantile_rank": point_rank_data[1],
                    "simultaneous_quantile_rank": simultaneous_rank,
                    "nominal_attainable": bool(
                        point_rank_data[2] and simultaneous_attainable
                    ),
                    "coverage_resolution": point_rank_data[3],
                }
            )
            test_indices = np.flatnonzero(test)
            for local_wafer, global_wafer in enumerate(test_indices):
                for point, (x, y) in enumerate(coordinates):
                    point_rows.append(
                        {
                            "experiment_key": keys[global_wafer],
                            "test_lot": test_lot,
                            "calibration_lot": calibration_lot,
                            "nominal_coverage": nominal,
                            "X": float(x),
                            "Y": float(y),
                            "observed": float(maps[global_wafer, point]),
                            "predicted": float(test_prediction[local_wafer, point]),
                            "absolute_error": float(test_error[local_wafer, point]),
                            "point_half_width": float(point_bounds[point]),
                            "point_covered": bool(point_covered[local_wafer, point]),
                            "simultaneous_half_width": simultaneous_bound,
                            "simultaneous_map_covered": bool(
                                simultaneous_covered[local_wafer]
                            ),
                        }
                    )

    lots_frame = pd.DataFrame(lot_rows)
    summary = (
        lots_frame.groupby("nominal_coverage", as_index=False)
        .agg(
            evaluated_lots=("test_lot", "nunique"),
            mean_calibration_wafers=("calibration_wafers", "mean"),
            point_empirical_coverage=("point_empirical_coverage", "mean"),
            simultaneous_map_coverage=("simultaneous_map_coverage", "mean"),
            mean_point_interval_width=("mean_point_interval_width", "mean"),
            mean_simultaneous_interval_width=(
                "simultaneous_interval_width",
                "mean",
            ),
            mean_template_baseline_mae=("template_baseline_mae", "mean"),
            mean_point_half_width_vs_template_mae=(
                "point_half_width_vs_template_mae",
                "mean",
            ),
            attainable_lot_fraction=("nominal_attainable", "mean"),
            mean_coverage_resolution=("coverage_resolution", "mean"),
            minimum_lot_point_coverage=("point_empirical_coverage", "min"),
            minimum_lot_simultaneous_coverage=(
                "simultaneous_map_coverage",
                "min",
            ),
        )
    )
    return ConformalResult(
        coverage_summary=summary,
        lot_coverage=lots_frame,
        point_diagnostics=pd.DataFrame(point_rows),
    )

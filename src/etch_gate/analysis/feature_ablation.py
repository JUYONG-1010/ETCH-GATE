"""Feature-group ablation and fold-wise stability for process-trace VM."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cross_decomposition import PLSRegression
from sklearn.linear_model import Ridge

from etch_gate.analysis.process_baseline import (
    decompose_maps,
    evaluate_process_baselines,
    fit_regressor,
    ordered_dense_maps,
    prepare_feature_transform,
    select_parameter,
)

FEATURE_GROUPS = {
    "G1_level": ("active_mean", "active_std", "active_range"),
    "G2_temporal_drift": ("active_slope", "early_late_delta"),
    "G3_bosch_phase": (
        "long_phase_mean",
        "short_phase_mean",
        "phase_difference",
    ),
    "G4_cycle_behavior": ("cycle_mean_std", "cycle_mean_slope"),
}

CUMULATIVE_ABLATIONS = {
    "A_G1": ("G1_level",),
    "B_G1_G2": ("G1_level", "G2_temporal_drift"),
    "C_G1_G2_G3": ("G1_level", "G2_temporal_drift", "G3_bosch_phase"),
    "D_all": tuple(FEATURE_GROUPS),
}


@dataclass(frozen=True)
class FeatureAblationResult:
    """Ablation summaries, fold metrics, and fold-wise feature stability."""

    summary: pd.DataFrame
    fold_metrics: pd.DataFrame
    feature_stability: pd.DataFrame


def feature_group(column: str) -> str:
    """Return the declared statistic group for one engineered feature."""

    if "__" not in column:
        raise ValueError(f"feature lacks signal/statistic separator: {column}")
    statistic = column.rsplit("__", 1)[1]
    matches = [
        group
        for group, statistics in FEATURE_GROUPS.items()
        if statistic in statistics
    ]
    if len(matches) != 1:
        raise ValueError(f"unrecognized or ambiguous feature statistic: {column}")
    return matches[0]


def sensor_family(column: str) -> str:
    """Classify released channel labels without assigning hidden chemistry."""

    signal = column.split("__", 1)[0].lower()
    if "gas" in signal or "heliumbpflow" in signal:
        return "gas_or_backside_flow"
    if "pressure" in signal:
        return "pressure"
    if "heater" in signal:
        return "heater_temperature"
    if "rf" in signal or "dcbias" in signal:
        return "rf_power_matching_electrical"
    return "remaining_process_signals"


def select_feature_groups(
    feature_table: pd.DataFrame,
    groups: tuple[str, ...],
) -> pd.DataFrame:
    """Select only columns belonging to the requested declared groups."""

    unknown = sorted(set(groups) - set(FEATURE_GROUPS))
    if unknown:
        raise ValueError(f"unknown feature groups: {unknown}")
    columns = [
        column for column in feature_table if feature_group(column) in set(groups)
    ]
    if not columns:
        raise ValueError("feature-group selection retained no columns")
    return feature_table.loc[:, columns]


def pls_vip(model: PLSRegression) -> np.ndarray:
    """Compute standard PLS VIP scores over all fitted latent components.

    VIP_j = sqrt(p * sum_a(SSY_a * (w_ja / ||w_a||)^2) / sum_a SSY_a),
    where SSY_a is the response sum of squares represented by component a.
    """

    scores = np.asarray(model.x_scores_, dtype=float)
    weights = np.asarray(model.x_weights_, dtype=float)
    loadings = np.asarray(model.y_loadings_, dtype=float)
    if scores.ndim != 2 or weights.ndim != 2 or loadings.ndim != 2:
        raise ValueError("PLS latent arrays must be matrices")
    component_response = np.sum(np.square(scores), axis=0) * np.sum(
        np.square(loadings), axis=0
    )
    total = float(component_response.sum())
    if total <= 1e-15:
        return np.zeros(weights.shape[0], dtype=float)
    normalized_weights = np.square(weights) / np.maximum(
        np.sum(np.square(weights), axis=0, keepdims=True), 1e-15
    )
    return np.sqrt(
        weights.shape[0] * (normalized_weights @ component_response) / total
    )


def _residual_metrics(points: pd.DataFrame) -> tuple[float, float]:
    centered = points.copy()
    groups = centered.groupby("experiment_key")
    centered["observed_centered"] = centered["observed"] - groups["observed"].transform(
        "mean"
    )
    centered["predicted_centered"] = centered[
        "predicted"
    ] - groups["predicted"].transform("mean")
    error = centered["predicted_centered"] - centered["observed_centered"]
    wafer_mae = error.abs().groupby(centered["experiment_key"]).mean()
    wafer_rmse = (
        error.pow(2).groupby(centered["experiment_key"]).mean().pow(0.5)
    )
    return float(wafer_mae.mean()), float(wafer_rmse.mean())


def _evaluate_ablation(
    label: str,
    features: pd.DataFrame,
    dense: pd.DataFrame,
    *,
    pls_parameters: tuple[float, ...],
    residual_variance_target: float,
    maximum_residual_components: int,
) -> tuple[dict[str, float | int | str], pd.DataFrame]:
    started = time.perf_counter()
    points, wafers, folds = evaluate_process_baselines(
        features,
        dense,
        families=("pls",),
        pls_parameters=pls_parameters,
        residual_variance_target=residual_variance_target,
        maximum_residual_components=maximum_residual_components,
    )
    full = wafers[wafers["stage"] == "full_map"].copy()
    mean = wafers[wafers["stage"] == "mean_shift"].copy()
    full_points = points[points["stage"] == "full_map"].copy()
    residual_mae, residual_rmse = _residual_metrics(full_points)
    lot_mae = full.groupby("lot_number")["mae"].mean()
    row: dict[str, float | int | str] = {
        "ablation": label,
        "retained_feature_count": features.shape[1],
        "wafer_macro_full_map_mae": float(full["mae"].mean()),
        "wafer_macro_full_map_rmse": float(full["rmse"].mean()),
        "lot_macro_full_map_mae": float(lot_mae.mean()),
        "wafer_mean_shift_mae": float(mean["mean_error"].abs().mean()),
        "residual_profile_mae": residual_mae,
        "residual_profile_rmse": residual_rmse,
        "worst_lot_mae": float(lot_mae.max()),
        "runtime_seconds": time.perf_counter() - started,
    }
    fold_metrics = folds.copy()
    fold_metrics.insert(0, "ablation", label)
    fold_metrics = fold_metrics.merge(
        lot_mae.rename("held_out_lot_mae"),
        left_on="held_out_lot",
        right_index=True,
        validate="many_to_one",
    )
    return row, fold_metrics


def _fold_feature_stability(
    feature_table: pd.DataFrame,
    dense: pd.DataFrame,
    *,
    pls_parameters: tuple[float, ...],
    ridge_parameters: tuple[float, ...],
    residual_variance_target: float,
    maximum_residual_components: int,
) -> pd.DataFrame:
    wafer_rows, _, maps, lots = ordered_dense_maps(dense, set(feature_table.index))
    keys = wafer_rows["experiment_key"].tolist()
    raw_features = feature_table.loc[keys].to_numpy(dtype=float)
    columns = np.asarray(feature_table.columns)
    rows = []
    for held_out_lot in np.unique(lots):
        train = lots != held_out_lot
        transform = prepare_feature_transform(raw_features[train])
        x_train = transform.apply(raw_features[train])
        retained_columns = columns[transform.retained]
        _, _, shifts, _, _, _ = decompose_maps(maps[train], maps[~train])
        for family, parameters in (
            ("pls", list(pls_parameters)),
            ("ridge", list(ridge_parameters)),
        ):
            parameter, _ = select_parameter(
                raw_features[train],
                maps[train],
                lots[train],
                family=family,
                parameters=parameters,
                target_part="mean_shift",
                variance_target=residual_variance_target,
                maximum_components=maximum_residual_components,
            )
            model = fit_regressor(family, parameter, x_train, shifts)
            if isinstance(model, PLSRegression):
                importance = pls_vip(model)
                coefficients = np.asarray(model.coef_).reshape(-1)
                metric = "VIP"
            elif isinstance(model, Ridge):
                coefficients = np.asarray(model.coef_).reshape(-1)
                importance = np.abs(coefficients)
                metric = "absolute_standardized_coefficient"
            else:
                raise TypeError("feature stability supports PLS and Ridge only")
            order = np.argsort(-importance, kind="stable")
            ranks = np.empty(len(order), dtype=int)
            ranks[order] = np.arange(1, len(order) + 1)
            top_count = min(20, len(order))
            for index, column in enumerate(retained_columns):
                rows.append(
                    {
                        "held_out_lot": int(held_out_lot),
                        "family": family,
                        "feature": str(column),
                        "feature_group": feature_group(str(column)),
                        "sensor_family": sensor_family(str(column)),
                        "importance_metric": metric,
                        "importance": float(importance[index]),
                        "coefficient_sign": int(np.sign(coefficients[index])),
                        "rank": int(ranks[index]),
                        "top_20": bool(ranks[index] <= top_count),
                    }
                )
    return pd.DataFrame(rows)


def evaluate_feature_ablation(
    feature_table: pd.DataFrame,
    dense: pd.DataFrame,
    *,
    pls_parameters: tuple[float, ...] = (1.0, 2.0, 4.0),
    ridge_parameters: tuple[float, ...] = (0.1, 1.0, 10.0, 100.0, 1000.0),
    residual_variance_target: float = 0.90,
    maximum_residual_components: int = 8,
    include_sensor_family_ablation: bool = True,
) -> FeatureAblationResult:
    """Run cumulative and optional family-only ablations on identical LOLO splits."""

    evaluations: list[tuple[str, pd.DataFrame]] = [
        (label, select_feature_groups(feature_table, groups))
        for label, groups in CUMULATIVE_ABLATIONS.items()
    ]
    if include_sensor_family_ablation:
        families = sorted({sensor_family(column) for column in feature_table})
        evaluations.extend(
            (
                f"family_only__{family}",
                feature_table.loc[
                    :, [column for column in feature_table if sensor_family(column) == family]
                ],
            )
            for family in families
        )

    summary_rows = []
    fold_frames = []
    previous_lot_mae: pd.Series | None = None
    for label, selected in evaluations:
        row, folds = _evaluate_ablation(
            label,
            selected,
            dense,
            pls_parameters=pls_parameters,
            residual_variance_target=residual_variance_target,
            maximum_residual_components=maximum_residual_components,
        )
        current_lot_mae = folds.set_index("held_out_lot")["held_out_lot_mae"]
        row["lots_improved_over_previous"] = (
            np.nan
            if previous_lot_mae is None or label.startswith("family_only")
            else int((current_lot_mae < previous_lot_mae).sum())
        )
        if not label.startswith("family_only"):
            previous_lot_mae = current_lot_mae
        summary_rows.append(row)
        fold_frames.append(folds)

    stability = _fold_feature_stability(
        feature_table,
        dense,
        pls_parameters=pls_parameters,
        ridge_parameters=ridge_parameters,
        residual_variance_target=residual_variance_target,
        maximum_residual_components=maximum_residual_components,
    )
    return FeatureAblationResult(
        summary=pd.DataFrame(summary_rows),
        fold_metrics=pd.concat(fold_frames, ignore_index=True),
        feature_stability=stability,
    )

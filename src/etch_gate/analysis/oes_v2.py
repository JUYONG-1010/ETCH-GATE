"""Physics-constrained OES V2: global shift from OES, spatial map from process data."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from etch_gate.analysis.process_baseline import (
    _decompose_maps,
    _fit_regressor,
    _ordered_dense_maps,
    _predict,
    _select_parameter,
    fit_residual_basis,
    prepare_feature_transform,
)


@dataclass(frozen=True)
class CompactOESSettings:
    """Training-fold-only PCA rank and Ridge penalty for OES mean shift."""

    components: int
    alpha: float

    @property
    def label(self) -> str:
        return f"pca={self.components};alpha={self.alpha:g}"


@dataclass(frozen=True)
class CompactOESRegressor:
    """A fold-local spectral-shape scaler, PCA, and regularized regressor."""

    retained: np.ndarray
    scaler: StandardScaler
    pca: PCA
    ridge: Ridge

    def predict(self, values: np.ndarray) -> np.ndarray:
        transformed = self.scaler.transform(values[:, self.retained])
        return self.ridge.predict(self.pca.transform(transformed))


def _fit_compact_oes_regressor(
    values: np.ndarray,
    targets: np.ndarray,
    settings: CompactOESSettings,
) -> CompactOESRegressor:
    retained = np.var(values, axis=0) > 1e-18
    if not retained.any():
        raise ValueError("all normalized OES features are constant")
    scaler = StandardScaler().fit(values[:, retained])
    scaled = scaler.transform(values[:, retained])
    components = min(settings.components, len(scaled) - 1, scaled.shape[1])
    if components < 1:
        raise ValueError("at least two OES training wafers are required")
    pca = PCA(n_components=components, svd_solver="full").fit(scaled)
    ridge = Ridge(alpha=settings.alpha).fit(pca.transform(scaled), targets)
    return CompactOESRegressor(retained=retained, scaler=scaler, pca=pca, ridge=ridge)


def _select_oes_settings(
    oes: np.ndarray,
    maps: np.ndarray,
    lots: np.ndarray,
    candidates: tuple[CompactOESSettings, ...],
) -> tuple[CompactOESSettings, float]:
    scores = {candidate: [] for candidate in candidates}
    maximum_components = max(candidate.components for candidate in candidates)
    for held_out_lot in np.unique(lots):
        train = lots != held_out_lot
        validation = ~train
        _, _, training_shift, validation_shift, _, _ = _decompose_maps(
            maps[train], maps[validation]
        )
        retained = np.var(oes[train], axis=0) > 1e-18
        scaler = StandardScaler().fit(oes[train][:, retained])
        train_scaled = scaler.transform(oes[train][:, retained])
        validation_scaled = scaler.transform(oes[validation][:, retained])
        components = min(maximum_components, len(train_scaled) - 1, train_scaled.shape[1])
        pca = PCA(n_components=components, svd_solver="full").fit(train_scaled)
        train_scores = pca.transform(train_scaled)
        validation_scores = pca.transform(validation_scaled)
        for candidate in candidates:
            count = min(candidate.components, train_scores.shape[1])
            model = Ridge(alpha=candidate.alpha).fit(train_scores[:, :count], training_shift)
            prediction = model.predict(validation_scores[:, :count]).reshape(-1)
            scores[candidate].append(float(np.mean(np.abs(prediction - validation_shift))))
    scored = [(candidate, float(np.mean(values))) for candidate, values in scores.items()]
    return min(scored, key=lambda item: (item[1], item[0].label))


def evaluate_physics_constrained_oes_v2(
    process_features: pd.DataFrame,
    oes_shape_features: pd.DataFrame,
    dense: pd.DataFrame,
    *,
    selected_lots: tuple[int, ...],
    oes_components: tuple[int, ...] = (2, 4, 8),
    ridge_alphas: tuple[float, ...] = (1.0, 10.0, 100.0),
    process_pls_parameters: tuple[float, ...] = (1.0, 2.0, 4.0),
    residual_variance_target: float = 0.90,
    maximum_residual_components: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Predict OES global shift and process-feature spatial residual per held-out lot."""

    selected_dense = dense[dense["lot_number"].isin(selected_lots)].copy()
    selected_keys = set(selected_dense["experiment_key"].unique())
    missing_process = sorted(selected_keys - set(process_features.index))
    missing_oes = sorted(selected_keys - set(oes_shape_features.index))
    if missing_process or missing_oes:
        raise ValueError(
            "selected dense wafer is missing features: "
            f"process={missing_process}, oes={missing_oes}"
        )
    wafer_rows, coordinates, maps, lots = _ordered_dense_maps(selected_dense, selected_keys)
    keys = wafer_rows["experiment_key"].tolist()
    process = process_features.loc[keys].to_numpy(dtype=float)
    oes = oes_shape_features.loc[keys].to_numpy(dtype=float)
    candidates = tuple(
        CompactOESSettings(components=component, alpha=alpha)
        for component in oes_components
        for alpha in ridge_alphas
    )
    point_rows = []
    wafer_metrics = []
    fold_rows = []

    for held_out_lot in np.unique(lots):
        train = lots != held_out_lot
        test = ~train
        reference, template, training_shift, _, training_residual, _ = _decompose_maps(
            maps[train], maps[test]
        )
        baseline = np.broadcast_to(reference + template, maps[test].shape)
        oes_settings, oes_inner_mae = _select_oes_settings(
            oes[train], maps[train], lots[train], candidates
        )
        oes_model = _fit_compact_oes_regressor(oes[train], training_shift, oes_settings)
        predicted_shift = oes_model.predict(oes[test]).reshape(-1)
        mean_prediction = baseline + predicted_shift[:, None]

        process_transform = prepare_feature_transform(process[train])
        process_train = process_transform.apply(process[train])
        process_test = process_transform.apply(process[test])
        residual_parameter, residual_inner_rmse = _select_parameter(
            process[train],
            maps[train],
            lots[train],
            family="pls",
            parameters=list(process_pls_parameters),
            target_part="residual",
            variance_target=residual_variance_target,
            maximum_components=maximum_residual_components,
        )
        basis = fit_residual_basis(
            training_residual,
            variance_target=residual_variance_target,
            maximum_components=maximum_residual_components,
        )
        residual_model = _fit_regressor(
            "pls", residual_parameter, process_train, basis.transform(training_residual)
        )
        residual_prediction = basis.inverse_transform(_predict(residual_model, process_test))
        full_prediction = mean_prediction + residual_prediction

        fold_rows.append(
            {
                "held_out_lot": int(held_out_lot),
                "family": "physics_constrained_oes_v2",
                "training_wafers": int(train.sum()),
                "test_wafers": int(test.sum()),
                "oes_shape_features": int(oes.shape[1]),
                "oes_retained_features": int(oes_model.retained.sum()),
                "oes_settings": oes_settings.label,
                "oes_inner_lot_macro_mae": oes_inner_mae,
                "residual_parameter": str(residual_parameter),
                "residual_inner_lot_macro_rmse": residual_inner_rmse,
                "residual_components": len(basis.components),
            }
        )
        for local_index, global_index in enumerate(np.flatnonzero(test)):
            observed = maps[global_index]
            predictions = {
                "template": baseline[local_index],
                "mean_shift": mean_prediction[local_index],
                "full_map": full_prediction[local_index],
            }
            for stage, prediction in predictions.items():
                error = prediction - observed
                wafer_metrics.append(
                    {
                        "experiment_key": keys[global_index],
                        "lot_number": int(lots[global_index]),
                        "family": "physics_constrained_oes_v2",
                        "stage": stage,
                        "mae": float(np.mean(np.abs(error))),
                        "rmse": float(np.sqrt(np.mean(np.square(error)))),
                        "mean_error": float(prediction.mean() - observed.mean()),
                        "mean_predicted_std": np.nan,
                    }
                )
                for point, (x, y) in enumerate(coordinates):
                    point_rows.append(
                        {
                            "experiment_key": keys[global_index],
                            "lot_number": int(lots[global_index]),
                            "family": "physics_constrained_oes_v2",
                            "stage": stage,
                            "X": x,
                            "Y": y,
                            "observed": observed[point],
                            "predicted": prediction[point],
                            "error": error[point],
                            "predicted_std": np.nan,
                        }
                    )

    wafers = pd.DataFrame(wafer_metrics)
    full = wafers[wafers["stage"] == "full_map"]
    summary = {
        "selected_lots": list(selected_lots),
        "dense_wafers": len(keys),
        "oes_shape_features": int(oes.shape[1]),
        "physics_constrained_lot_macro_mae": float(full.groupby("lot_number")["mae"].mean().mean()),
    }
    return pd.DataFrame(point_rows), wafers, pd.DataFrame(fold_rows), summary

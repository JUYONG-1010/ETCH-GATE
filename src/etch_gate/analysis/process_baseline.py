"""Nested lot-aware process baselines for dense step-height prediction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cross_decomposition import PLSRegression
from sklearn.decomposition import PCA
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class FeatureTransform:
    """Training-fold-only constant filter and standardization."""

    retained: np.ndarray
    scaler: StandardScaler

    def apply(self, values: np.ndarray) -> np.ndarray:
        return self.scaler.transform(values[:, self.retained])


@dataclass(frozen=True)
class ResidualBasis:
    """Training-fold-only low-dimensional basis for 89-point residual maps."""

    mean: np.ndarray
    components: np.ndarray
    explained_variance: float

    def transform(self, maps: np.ndarray) -> np.ndarray:
        return (maps - self.mean) @ self.components.T

    def inverse_transform(self, scores: np.ndarray) -> np.ndarray:
        return scores @ self.components + self.mean


@dataclass(frozen=True)
class GPRSettings:
    """Fixed candidate selected by the inner lot-wise validation loop."""

    pca_components: int
    length_scale: float
    noise_level: float
    optimize_kernel: bool = False

    @property
    def label(self) -> str:
        return (
            f"pca={self.pca_components};length={self.length_scale:g};"
            f"noise={self.noise_level:g};optimize={self.optimize_kernel}"
        )


@dataclass(frozen=True)
class PCAGaussianProcess:
    """Training-only PCA followed by a fixed-kernel multi-output GPR."""

    pca: PCA
    regressor: GaussianProcessRegressor

    def predict(
        self,
        features: np.ndarray,
        *,
        return_std: bool = False,
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        return self.regressor.predict(
            self.pca.transform(features),
            return_std=return_std,
        )


def prepare_feature_transform(values: np.ndarray) -> FeatureTransform:
    """Fit constant removal and z-score scaling using training wafers only."""

    retained = np.var(values, axis=0) > 1e-12
    if not retained.any():
        raise ValueError("all process features are constant in this training fold")
    scaler = StandardScaler().fit(values[:, retained])
    return FeatureTransform(retained=retained, scaler=scaler)


def fit_residual_basis(
    residual_maps: np.ndarray,
    *,
    variance_target: float = 0.90,
    maximum_components: int = 8,
) -> ResidualBasis:
    """Fit PCA on training residual maps and retain a small shape basis."""

    maximum = min(maximum_components, len(residual_maps) - 1, residual_maps.shape[1])
    if maximum < 1:
        raise ValueError("at least two training wafers are required for residual PCA")
    pca = PCA(n_components=maximum, svd_solver="full").fit(residual_maps)
    cumulative = np.cumsum(pca.explained_variance_ratio_)
    count = min(int(np.searchsorted(cumulative, variance_target) + 1), maximum)
    return ResidualBasis(
        mean=pca.mean_.copy(),
        components=pca.components_[:count].copy(),
        explained_variance=float(cumulative[count - 1]),
    )


def _fit_regressor(
    family: str,
    parameter: float | GPRSettings,
    features: np.ndarray,
    targets: np.ndarray,
) -> Ridge | PLSRegression | PCAGaussianProcess:
    if family == "ridge":
        if isinstance(parameter, GPRSettings):
            raise TypeError("Ridge parameter must be a float")
        model = Ridge(alpha=float(parameter))
    elif family == "pls":
        if isinstance(parameter, GPRSettings):
            raise TypeError("PLS parameter must be a float")
        components = min(int(parameter), features.shape[1], len(features) - 1)
        model = PLSRegression(n_components=components, scale=False, max_iter=1000)
    elif family == "gpr":
        if not isinstance(parameter, GPRSettings):
            raise TypeError("GPR parameter must be GPRSettings")
        component_count = min(
            parameter.pca_components,
            features.shape[1],
            len(features) - 1,
        )
        pca = PCA(n_components=component_count, whiten=True, svd_solver="full").fit(
            features
        )
        constant_bounds: tuple[float, float] | str = (
            (1e-3, 1e3) if parameter.optimize_kernel else "fixed"
        )
        length_bounds: tuple[float, float] | str = (
            (1e-2, 1e3) if parameter.optimize_kernel else "fixed"
        )
        noise_bounds: tuple[float, float] | str = (
            (1e-5, 1e1) if parameter.optimize_kernel else "fixed"
        )
        kernel = (
            ConstantKernel(1.0, constant_value_bounds=constant_bounds)
            * RBF(parameter.length_scale, length_scale_bounds=length_bounds)
            + WhiteKernel(parameter.noise_level, noise_level_bounds=noise_bounds)
        )
        regressor = GaussianProcessRegressor(
            kernel=kernel,
            optimizer="fmin_l_bfgs_b" if parameter.optimize_kernel else None,
            normalize_y=True,
            random_state=0,
        ).fit(pca.transform(features), targets)
        return PCAGaussianProcess(pca=pca, regressor=regressor)
    else:
        raise ValueError(f"unknown model family: {family}")
    return model.fit(features, targets)


def _predict(
    model: Ridge | PLSRegression | PCAGaussianProcess,
    features: np.ndarray,
) -> np.ndarray:
    prediction = np.asarray(model.predict(features))
    return prediction.reshape(len(features), -1)


def _predict_with_std(
    model: Ridge | PLSRegression | PCAGaussianProcess,
    features: np.ndarray,
) -> tuple[np.ndarray, np.ndarray | None]:
    if not isinstance(model, PCAGaussianProcess):
        return _predict(model, features), None
    prediction, standard_deviation = model.predict(features, return_std=True)
    prediction = np.asarray(prediction).reshape(len(features), -1)
    standard_deviation = np.asarray(standard_deviation).reshape(len(features), -1)
    return prediction, standard_deviation


def _parameter_label(parameter: float | GPRSettings) -> float | str:
    return parameter.label if isinstance(parameter, GPRSettings) else parameter


def _fitted_model_label(
    model: Ridge | PLSRegression | PCAGaussianProcess,
) -> str | None:
    if isinstance(model, PCAGaussianProcess):
        return str(model.regressor.kernel_)
    return None


def _decompose_maps(
    training_maps: np.ndarray,
    evaluation_maps: np.ndarray,
) -> tuple[
    float,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    """Build a template from training maps and decompose both map sets."""

    reference_mean = float(training_maps.mean())
    centered_template = training_maps.mean(axis=0) - reference_mean
    training_shift = training_maps.mean(axis=1) - reference_mean
    evaluation_shift = evaluation_maps.mean(axis=1) - reference_mean
    training_residual = (
        training_maps
        - training_maps.mean(axis=1, keepdims=True)
        - centered_template
    )
    evaluation_residual = (
        evaluation_maps
        - evaluation_maps.mean(axis=1, keepdims=True)
        - centered_template
    )
    return (
        reference_mean,
        centered_template,
        training_shift,
        evaluation_shift,
        training_residual,
        evaluation_residual,
    )


def _inner_score(
    features: np.ndarray,
    maps: np.ndarray,
    lots: np.ndarray,
    *,
    family: str,
    parameter: float | GPRSettings,
    target_part: str,
    variance_target: float,
    maximum_components: int,
) -> float:
    lot_scores = []
    for held_out_lot in np.unique(lots):
        train = lots != held_out_lot
        validation = ~train
        transform = prepare_feature_transform(features[train])
        x_train = transform.apply(features[train])
        x_validation = transform.apply(features[validation])
        _, _, training_shift, validation_shift, training_residual, validation_residual = (
            _decompose_maps(
            maps[train], maps[validation]
            )
        )

        if target_part == "mean_shift":
            model = _fit_regressor(
                family, parameter, x_train, training_shift
            )
            predicted = _predict(model, x_validation)[:, 0]
            score = np.mean(np.abs(predicted - validation_shift))
        elif target_part == "residual":
            basis = fit_residual_basis(
                training_residual,
                variance_target=variance_target,
                maximum_components=maximum_components,
            )
            scores = basis.transform(training_residual)
            model = _fit_regressor(family, parameter, x_train, scores)
            predicted = basis.inverse_transform(_predict(model, x_validation))
            score = np.sqrt(
                np.mean(np.square(predicted - validation_residual))
            )
        else:
            raise ValueError(f"unknown target part: {target_part}")
        lot_scores.append(float(score))
    return float(np.mean(lot_scores))


def _select_parameter(
    features: np.ndarray,
    maps: np.ndarray,
    lots: np.ndarray,
    *,
    family: str,
    parameters: list[float | GPRSettings],
    target_part: str,
    variance_target: float,
    maximum_components: int,
) -> tuple[float | GPRSettings, float]:
    scored = [
        (
            parameter,
            _inner_score(
            features,
            maps,
            lots,
            family=family,
            parameter=parameter,
            target_part=target_part,
            variance_target=variance_target,
            maximum_components=maximum_components,
            ),
        )
        for parameter in parameters
    ]
    selected, score = min(
        scored,
        key=lambda item: (item[1], str(_parameter_label(item[0]))),
    )
    return selected, float(score)


def _ordered_dense_maps(
    dense: pd.DataFrame,
    feature_keys: set[str],
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    required = {"experiment_key", "lot_number", "X", "Y", "stepheight"}
    missing = sorted(required - set(dense.columns))
    if missing:
        raise ValueError(f"dense table is missing columns: {missing}")
    dense = dense[dense["experiment_key"].isin(feature_keys)].copy()
    coordinates = (
        dense[["X", "Y"]].drop_duplicates().sort_values(["Y", "X"]).reset_index(drop=True)
    )
    coordinate_index = pd.MultiIndex.from_frame(coordinates)
    wafer_rows = (
        dense[["experiment_key", "lot_number"]]
        .drop_duplicates()
        .sort_values("experiment_key")
        .reset_index(drop=True)
    )
    maps = []
    for key in wafer_rows["experiment_key"]:
        wafer = dense[dense["experiment_key"] == key].set_index(["X", "Y"])
        values = wafer["stepheight"].reindex(coordinate_index).to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"{key} does not contain the complete coordinate grid")
        maps.append(values)
    return (
        wafer_rows,
        coordinates.to_numpy(dtype=float),
        np.asarray(maps),
        wafer_rows["lot_number"].to_numpy(),
    )


def evaluate_process_baselines(
    feature_table: pd.DataFrame,
    dense: pd.DataFrame,
    *,
    families: tuple[str, ...] = ("ridge", "pls"),
    ridge_parameters: tuple[float, ...] = (0.1, 1.0, 10.0, 100.0, 1000.0),
    pls_parameters: tuple[float, ...] = (1.0, 2.0, 4.0),
    gpr_parameters: tuple[GPRSettings, ...] = (
        GPRSettings(pca_components=8, length_scale=2.0, noise_level=0.05),
    ),
    residual_variance_target: float = 0.90,
    maximum_residual_components: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Evaluate template, mean-shift, and full-map models with nested LOLO."""

    wafer_rows, coordinates, maps, lots = _ordered_dense_maps(
        dense, set(feature_table.index)
    )
    keys = wafer_rows["experiment_key"].tolist()
    features = feature_table.loc[keys].to_numpy(dtype=float)
    point_rows = []
    wafer_metrics = []
    fold_rows = []

    for held_out_lot in np.unique(lots):
        train = lots != held_out_lot
        test = ~train
        transform = prepare_feature_transform(features[train])
        x_train = transform.apply(features[train])
        x_test = transform.apply(features[test])
        (
            reference,
            template,
            training_shift,
            _,
            training_residual,
            _,
        ) = _decompose_maps(
            maps[train], maps[test]
        )
        baseline = np.broadcast_to(reference + template, maps[test].shape)

        for family in families:
            if family == "ridge":
                parameters: list[float | GPRSettings] = list(ridge_parameters)
            elif family == "pls":
                parameters = list(pls_parameters)
            elif family == "gpr":
                parameters = list(gpr_parameters)
            else:
                raise ValueError(f"unknown model family: {family}")
            mean_parameter, mean_inner_mae = _select_parameter(
                features[train],
                maps[train],
                lots[train],
                family=family,
                parameters=parameters,
                target_part="mean_shift",
                variance_target=residual_variance_target,
                maximum_components=maximum_residual_components,
            )
            residual_parameter, residual_inner_rmse = _select_parameter(
                features[train],
                maps[train],
                lots[train],
                family=family,
                parameters=parameters,
                target_part="residual",
                variance_target=residual_variance_target,
                maximum_components=maximum_residual_components,
            )
            mean_model = _fit_regressor(
                family, mean_parameter, x_train, training_shift
            )
            predicted_shift_array, shift_std_array = _predict_with_std(
                mean_model, x_test
            )
            predicted_shift = predicted_shift_array[:, 0]
            shift_std = None if shift_std_array is None else shift_std_array[:, 0]
            mean_only = baseline + predicted_shift[:, None]
            mean_only_std = (
                None
                if shift_std is None
                else np.broadcast_to(shift_std[:, None], mean_only.shape)
            )

            basis = fit_residual_basis(
                training_residual,
                variance_target=residual_variance_target,
                maximum_components=maximum_residual_components,
            )
            residual_scores = basis.transform(training_residual)
            residual_model = _fit_regressor(
                family, residual_parameter, x_train, residual_scores
            )
            predicted_scores, score_std = _predict_with_std(residual_model, x_test)
            predicted_residual = basis.inverse_transform(predicted_scores)
            full_prediction = mean_only + predicted_residual
            full_std = None
            if shift_std is not None and score_std is not None:
                residual_variance = np.square(score_std) @ np.square(basis.components)
                full_std = np.sqrt(np.square(shift_std[:, None]) + residual_variance)

            fold_rows.append(
                {
                    "held_out_lot": held_out_lot,
                    "family": family,
                    "training_wafers": int(train.sum()),
                    "test_wafers": int(test.sum()),
                    "retained_features": int(transform.retained.sum()),
                    "mean_parameter": _parameter_label(mean_parameter),
                    "mean_fitted_model": _fitted_model_label(mean_model),
                    "mean_inner_lot_macro_mae": mean_inner_mae,
                    "residual_parameter": _parameter_label(residual_parameter),
                    "residual_fitted_model": _fitted_model_label(residual_model),
                    "residual_inner_lot_macro_rmse": residual_inner_rmse,
                    "residual_components": len(basis.components),
                    "residual_explained_variance": basis.explained_variance,
                }
            )
            for local_index, global_index in enumerate(np.flatnonzero(test)):
                observed = maps[global_index]
                predictions = {
                    "template": (baseline[local_index], None),
                    "mean_shift": (mean_only[local_index], mean_only_std),
                    "full_map": (full_prediction[local_index], full_std),
                }
                for stage, (prediction, prediction_std) in predictions.items():
                    error = prediction - observed
                    wafer_std = (
                        np.nan
                        if prediction_std is None
                        else float(np.mean(prediction_std[local_index]))
                    )
                    wafer_metrics.append(
                        {
                            "experiment_key": keys[global_index],
                            "lot_number": lots[global_index],
                            "family": family,
                            "stage": stage,
                            "mae": float(np.mean(np.abs(error))),
                            "rmse": float(np.sqrt(np.mean(np.square(error)))),
                            "mean_error": float(prediction.mean() - observed.mean()),
                            "mean_predicted_std": wafer_std,
                        }
                    )
                    for point, (x, y) in enumerate(coordinates):
                        point_rows.append(
                            {
                                "experiment_key": keys[global_index],
                                "lot_number": lots[global_index],
                                "family": family,
                                "stage": stage,
                                "X": x,
                                "Y": y,
                                "observed": observed[point],
                                "predicted": prediction[point],
                                "error": error[point],
                                "predicted_std": (
                                    np.nan
                                    if prediction_std is None
                                    else prediction_std[local_index, point]
                                ),
                            }
                        )

    return (
        pd.DataFrame(point_rows),
        pd.DataFrame(wafer_metrics),
        pd.DataFrame(fold_rows),
    )

"""Leakage-safe process-drift and VM failure-risk evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import pairwise_distances

from etch_gate.analysis.process_baseline import (
    _decompose_maps,
    _fit_regressor,
    _ordered_dense_maps,
    _predict,
    fit_residual_basis,
    prepare_feature_transform,
)


@dataclass(frozen=True)
class RiskEvaluation:
    """Wafer scores, budget curves, and per-lot policy summaries."""

    wafer_scores: pd.DataFrame
    risk_curves: pd.DataFrame
    lot_summary: pd.DataFrame


def _empirical_percentile(reference: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Map a score to its outer-training empirical percentile."""

    ordered = np.sort(np.asarray(reference, dtype=float))
    return np.searchsorted(ordered, values, side="right") / len(ordered)


def _sequential_change_scores(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute previous-wafer and causal EWMA distances for one ordered lot."""

    delta = np.empty(len(values), dtype=float)
    ewma = np.empty(len(values), dtype=float)
    previous = np.zeros(values.shape[1], dtype=float)
    running = np.zeros(values.shape[1], dtype=float)
    for index, current in enumerate(values):
        delta[index] = np.linalg.norm(current - previous)
        ewma[index] = np.linalg.norm(current - running)
        previous = current
        running = current if index == 0 else 0.3 * current + 0.7 * running
    return delta, ewma


def _grouped_change_scores(
    values: np.ndarray,
    keys: np.ndarray,
    lots: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply causal change scores independently inside each lot."""

    delta = np.empty(len(values), dtype=float)
    ewma = np.empty(len(values), dtype=float)
    for lot in np.unique(lots):
        positions = np.flatnonzero(lots == lot)
        positions = positions[np.argsort(keys[positions])]
        delta[positions], ewma[positions] = _sequential_change_scores(
            values[positions]
        )
    return delta, ewma


def _fit_family_predictions(
    family: str,
    x_train: np.ndarray,
    x_test: np.ndarray,
    training_maps: np.ndarray,
    *,
    mean_parameter: float,
    residual_parameter: float,
    residual_variance_target: float,
    maximum_residual_components: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit one frozen Milestone 3 model and predict train and test features."""

    reference, template, shifts, _, residuals, _ = _decompose_maps(
        training_maps, training_maps[:1]
    )
    basis = fit_residual_basis(
        residuals,
        variance_target=residual_variance_target,
        maximum_components=maximum_residual_components,
    )
    mean_model = _fit_regressor(family, mean_parameter, x_train, shifts)
    residual_model = _fit_regressor(
        family,
        residual_parameter,
        x_train,
        basis.transform(residuals),
    )

    def predict(features: np.ndarray) -> np.ndarray:
        shift = _predict(mean_model, features)[:, 0]
        residual = basis.inverse_transform(_predict(residual_model, features))
        return reference + template + shift[:, None] + residual

    return predict(x_train), predict(x_test)


def _retained_risk(errors: np.ndarray, selected: np.ndarray) -> float:
    retained = np.ones(len(errors), dtype=bool)
    retained[selected] = False
    return float(errors[retained].mean()) if retained.any() else np.nan


def _periodic_selection(size: int, count: int) -> np.ndarray:
    if count == 0:
        return np.array([], dtype=int)
    return np.unique(np.rint(np.linspace(0, size - 1, count)).astype(int))


def _policy_curve(
    errors: np.ndarray,
    scores: np.ndarray | None,
    budgets: tuple[float, ...],
    *,
    periodic: bool = False,
) -> list[dict[str, float | int]]:
    rows = []
    ranking = None if scores is None else np.argsort(-scores, kind="stable")
    for budget in budgets:
        count = min(int(np.rint(budget * len(errors))), len(errors) - 1)
        selected = (
            _periodic_selection(len(errors), count)
            if periodic
            else ranking[:count]
        )
        rows.append(
            {
                "requested_budget": budget,
                "selected_wafers": len(selected),
                "actual_metrology_fraction": len(selected) / len(errors),
                "retained_mae": _retained_risk(errors, selected),
            }
        )
    return rows


def _aurc(errors: np.ndarray, scores: np.ndarray) -> float:
    ranking = np.argsort(-scores, kind="stable")
    risks = [_retained_risk(errors, ranking[:count]) for count in range(len(errors))]
    coverages = np.arange(len(errors), 0, -1, dtype=float) / len(errors)
    return float(np.trapezoid(risks[::-1], coverages[::-1]) / (1 - 1 / len(errors)))


def evaluate_drift_risk(
    feature_table: pd.DataFrame,
    dense: pd.DataFrame,
    fold_diagnostics: pd.DataFrame,
    *,
    pca_components: int = 10,
    ewma_alpha: float = 0.3,
    budgets: tuple[float, ...] = tuple(np.arange(0.0, 1.0, 0.1)),
    random_replicates: int = 10000,
    random_seed: int = 20260721,
    residual_variance_target: float = 0.90,
    maximum_residual_components: int = 8,
) -> RiskEvaluation:
    """Evaluate target-free risk rankings under outer leave-one-lot-out splits."""

    if ewma_alpha != 0.3:
        raise ValueError("the preregistered EWMA alpha is 0.3")
    wafer_rows, _, maps, lots = _ordered_dense_maps(dense, set(feature_table.index))
    keys = wafer_rows["experiment_key"].to_numpy()
    raw_features = feature_table.loc[keys].to_numpy(dtype=float)
    generator = np.random.default_rng(random_seed)
    score_rows: list[dict[str, float | int | str]] = []
    curve_rows: list[dict[str, float | int | str]] = []
    summary_rows: list[dict[str, float | int | str]] = []

    for held_out_lot in np.unique(lots):
        train = lots != held_out_lot
        test = ~train
        transform = prepare_feature_transform(raw_features[train])
        x_train = transform.apply(raw_features[train])
        x_test = transform.apply(raw_features[test])
        component_count = min(pca_components, len(x_train) - 1, x_train.shape[1])
        pca = PCA(n_components=component_count, svd_solver="full").fit(x_train)
        z_train = pca.transform(x_train)
        z_test = pca.transform(x_test)

        train_distances = pairwise_distances(z_train)
        np.fill_diagonal(train_distances, np.inf)
        train_ood = train_distances.min(axis=1)
        test_ood = pairwise_distances(z_test, z_train).min(axis=1)
        train_delta, train_ewma = _grouped_change_scores(
            z_train, keys[train], lots[train]
        )
        test_delta, test_ewma = _grouped_change_scores(
            z_test, keys[test], lots[test]
        )

        predictions = {}
        training_predictions = {}
        for family in ("ridge", "pls"):
            row = fold_diagnostics[
                (fold_diagnostics["held_out_lot"] == held_out_lot)
                & (fold_diagnostics["family"] == family)
            ].iloc[0]
            training_predictions[family], predictions[family] = (
                _fit_family_predictions(
                    family,
                    x_train,
                    x_test,
                    maps[train],
                    mean_parameter=float(row["mean_parameter"]),
                    residual_parameter=float(row["residual_parameter"]),
                    residual_variance_target=residual_variance_target,
                    maximum_residual_components=maximum_residual_components,
                )
            )
        train_disagreement = np.sqrt(
            np.mean(
                np.square(training_predictions["pls"] - training_predictions["ridge"]),
                axis=1,
            )
        )
        test_disagreement = np.sqrt(
            np.mean(np.square(predictions["pls"] - predictions["ridge"]), axis=1)
        )
        true_error = np.mean(np.abs(predictions["pls"] - maps[test]), axis=1)

        percentiles = {
            "ood": _empirical_percentile(train_ood, test_ood),
            "delta": _empirical_percentile(train_delta, test_delta),
            "ewma": _empirical_percentile(train_ewma, test_ewma),
            "disagreement": _empirical_percentile(
                train_disagreement, test_disagreement
            ),
        }
        combined = np.mean(np.column_stack(list(percentiles.values())), axis=1)
        policy_scores = {**percentiles, "combined": combined, "oracle": true_error}

        test_keys = keys[test]
        for index, key in enumerate(test_keys):
            score_rows.append(
                {
                    "experiment_key": key,
                    "lot_number": int(held_out_lot),
                    "true_pls_mae": true_error[index],
                    **{name + "_percentile": value[index] for name, value in percentiles.items()},
                    "combined_risk": combined[index],
                }
            )

        random_aurcs = []
        random_curve_values = {budget: [] for budget in budgets}
        for _ in range(random_replicates):
            random_scores = generator.random(len(true_error))
            random_aurcs.append(_aurc(true_error, random_scores))
            for row in _policy_curve(true_error, random_scores, budgets):
                random_curve_values[row["requested_budget"]].append(row["retained_mae"])
        for budget in budgets:
            values = np.asarray(random_curve_values[budget])
            count = min(int(np.rint(budget * len(true_error))), len(true_error) - 1)
            curve_rows.append(
                {
                    "lot_number": int(held_out_lot),
                    "policy": "random",
                    "requested_budget": budget,
                    "selected_wafers": count,
                    "actual_metrology_fraction": count / len(true_error),
                    "retained_mae": float(values.mean()),
                    "random_p025": float(np.quantile(values, 0.025)),
                    "random_p975": float(np.quantile(values, 0.975)),
                }
            )
        random_aurcs_array = np.asarray(random_aurcs)
        summary_rows.append(
            {
                "lot_number": int(held_out_lot),
                "policy": "random",
                "aurc": float(random_aurcs_array.mean()),
                "random_p025": float(np.quantile(random_aurcs_array, 0.025)),
                "random_p975": float(np.quantile(random_aurcs_array, 0.975)),
            }
        )

        periodic_score = -np.arange(len(true_error), dtype=float)
        policies = {"periodic": periodic_score, **policy_scores}
        for name, scores in policies.items():
            rows = _policy_curve(
                true_error,
                scores,
                budgets,
                periodic=name == "periodic",
            )
            for row in rows:
                curve_rows.append(
                    {
                        "lot_number": int(held_out_lot),
                        "policy": name,
                        **row,
                        "random_p025": np.nan,
                        "random_p975": np.nan,
                    }
                )
            if name == "periodic":
                periodic_risks = []
                for count in range(len(true_error)):
                    periodic_risks.append(
                        _retained_risk(
                            true_error, _periodic_selection(len(true_error), count)
                        )
                    )
                coverage = np.arange(len(true_error), 0, -1) / len(true_error)
                aurc = float(
                    np.trapezoid(periodic_risks[::-1], coverage[::-1])
                    / (1 - 1 / len(true_error))
                )
            else:
                aurc = _aurc(true_error, scores)
            summary_rows.append(
                {
                    "lot_number": int(held_out_lot),
                    "policy": name,
                    "aurc": aurc,
                    "random_p025": np.nan,
                    "random_p975": np.nan,
                }
            )

    return RiskEvaluation(
        wafer_scores=pd.DataFrame(score_rows),
        risk_curves=pd.DataFrame(curve_rows),
        lot_summary=pd.DataFrame(summary_rows),
    )

"""Leakage-safe process-drift and VM failure-risk evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import permutations, product

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
from sklearn.metrics import pairwise_distances

from etch_gate.analysis.process_baseline import (
    decompose_maps,
    fit_regressor,
    fit_residual_basis,
    ordered_dense_maps,
    predict_regressor,
    prepare_feature_transform,
    validate_feature_table,
)
from etch_gate.statistics import lot_cluster_bootstrap_mean


@dataclass(frozen=True)
class RiskEvaluation:
    """Wafer scores, budget curves, and per-lot policy summaries."""

    wafer_scores: pd.DataFrame
    risk_curves: pd.DataFrame
    lot_summary: pd.DataFrame
    score_correlations: pd.DataFrame = field(default_factory=pd.DataFrame)
    alpha_sensitivity: pd.DataFrame = field(default_factory=pd.DataFrame)
    influence_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    bootstrap_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    small_lot_resolution: pd.DataFrame = field(default_factory=pd.DataFrame)
    weight_selection: pd.DataFrame = field(default_factory=pd.DataFrame)


def _empirical_percentile(reference: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Map a score to its outer-training empirical percentile."""

    reference = np.asarray(reference, dtype=float)
    values = np.asarray(values, dtype=float)
    ordered = np.sort(reference[np.isfinite(reference)])
    if not len(ordered):
        raise ValueError("percentile reference has no finite values")
    result = np.full(values.shape, 0.5, dtype=float)
    finite = np.isfinite(values)
    result[finite] = (
        np.searchsorted(ordered, values[finite], side="right") / len(ordered)
    )
    return result


def empirical_percentile(reference: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Public training-reference percentile transform with neutral missing values."""

    return _empirical_percentile(reference, values)


def sequential_change_scores(
    values: np.ndarray,
    *,
    centroid: np.ndarray,
    ewma_alpha: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute initial-state, previous-wafer, and causal-EWMA distances."""

    values = np.asarray(values, dtype=float)
    centroid = np.asarray(centroid, dtype=float)
    if values.ndim != 2 or centroid.shape != (values.shape[1],):
        raise ValueError("values must be 2D and centroid must match one feature row")
    if not 0 < ewma_alpha <= 1:
        raise ValueError("ewma_alpha must be in (0, 1]")
    initial = np.linalg.norm(values - centroid, axis=1)
    delta = np.full(len(values), np.nan, dtype=float)
    ewma = np.full(len(values), np.nan, dtype=float)
    if not len(values):
        return initial, delta, ewma
    previous = values[0].copy()
    running = values[0].copy()
    for index, current in enumerate(values):
        if index == 0:
            continue
        delta[index] = np.linalg.norm(current - previous)
        ewma[index] = np.linalg.norm(current - running)
        previous = current
        running = ewma_alpha * current + (1 - ewma_alpha) * running
    return initial, delta, ewma


def _grouped_change_scores(
    values: np.ndarray,
    keys: np.ndarray,
    lots: np.ndarray,
    *,
    centroid: np.ndarray,
    ewma_alpha: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Apply causal change scores independently inside each lot."""

    initial = np.empty(len(values), dtype=float)
    delta = np.full(len(values), np.nan, dtype=float)
    ewma = np.full(len(values), np.nan, dtype=float)
    for lot in np.unique(lots):
        positions = np.flatnonzero(lots == lot)
        positions = positions[np.argsort(keys[positions])]
        initial[positions], delta[positions], ewma[positions] = (
            sequential_change_scores(
                values[positions],
                centroid=centroid,
                ewma_alpha=ewma_alpha,
            )
        )
    return initial, delta, ewma


def grouped_change_scores(
    values: np.ndarray,
    keys: np.ndarray,
    lots: np.ndarray,
    *,
    centroid: np.ndarray,
    ewma_alpha: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Public lot-isolated causal change-score calculation."""

    return _grouped_change_scores(
        values,
        keys,
        lots,
        centroid=centroid,
        ewma_alpha=ewma_alpha,
    )


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

    reference, template, shifts, _, residuals, _ = decompose_maps(
        training_maps, training_maps[:1]
    )
    basis = fit_residual_basis(
        residuals,
        variance_target=residual_variance_target,
        maximum_components=maximum_residual_components,
    )
    mean_model = fit_regressor(family, mean_parameter, x_train, shifts)
    residual_model = fit_regressor(
        family,
        residual_parameter,
        x_train,
        basis.transform(residuals),
    )

    def predict(features: np.ndarray) -> np.ndarray:
        shift = predict_regressor(mean_model, features)[:, 0]
        residual = basis.inverse_transform(predict_regressor(residual_model, features))
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


def _score_correlation_rows(
    scores: dict[str, np.ndarray],
    *,
    held_out_lot: int,
    split: str,
) -> list[dict[str, float | int | str]]:
    """Return pairwise Spearman correlations with missing first-wafer scores omitted."""

    rows: list[dict[str, float | int | str]] = []
    names = list(scores)
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            left_values = np.asarray(scores[left], dtype=float)
            right_values = np.asarray(scores[right], dtype=float)
            finite = np.isfinite(left_values) & np.isfinite(right_values)
            correlation = (
                float(spearmanr(left_values[finite], right_values[finite]).statistic)
                if finite.sum() >= 3
                else np.nan
            )
            rows.append(
                {
                    "held_out_lot": held_out_lot,
                    "split": split,
                    "score_a": left,
                    "score_b": right,
                    "spearman": correlation,
                    "n_pairs": int(finite.sum()),
                }
            )
    return rows


def _simplex_weight_grid(component_count: int, denominator: int = 4) -> np.ndarray:
    """Enumerate a small non-negative weight grid whose rows sum to one."""

    integer_weights = [
        candidate
        for candidate in product(range(denominator + 1), repeat=component_count)
        if sum(candidate) == denominator
    ]
    return np.asarray(integer_weights, dtype=float) / denominator


def _inner_lot_weight_selection(
    raw_features: np.ndarray,
    maps: np.ndarray,
    lots: np.ndarray,
    keys: np.ndarray,
    *,
    components: list[str],
    pca_components: int,
    ewma_alpha: float,
    mean_parameters: dict[str, float],
    residual_parameters: dict[str, float],
    residual_variance_target: float,
    maximum_residual_components: int,
) -> tuple[np.ndarray, dict[str, float | int | bool]]:
    """Select proxy weights using only inner held-out training lots."""

    validation_rows: list[pd.DataFrame] = []
    for validation_lot in np.unique(lots):
        inner_train = lots != validation_lot
        inner_test = ~inner_train
        transform = prepare_feature_transform(raw_features[inner_train])
        x_train = transform.apply(raw_features[inner_train])
        x_test = transform.apply(raw_features[inner_test])
        count = min(pca_components, len(x_train) - 1, x_train.shape[1])
        pca = PCA(n_components=count, svd_solver="full").fit(x_train)
        z_train = pca.transform(x_train)
        z_test = pca.transform(x_test)
        centroid = z_train.mean(axis=0)

        train_distances = pairwise_distances(z_train)
        np.fill_diagonal(train_distances, np.inf)
        train_initial, train_delta, train_ewma = _grouped_change_scores(
            z_train,
            keys[inner_train],
            lots[inner_train],
            centroid=centroid,
            ewma_alpha=ewma_alpha,
        )
        test_initial, test_delta, test_ewma = _grouped_change_scores(
            z_test,
            keys[inner_test],
            lots[inner_test],
            centroid=centroid,
            ewma_alpha=ewma_alpha,
        )
        train_ood = train_distances.min(axis=1)
        test_ood = pairwise_distances(z_test, z_train).min(axis=1)

        train_predictions: dict[str, np.ndarray] = {}
        test_predictions: dict[str, np.ndarray] = {}
        for family in ("ridge", "pls"):
            train_predictions[family], test_predictions[family] = (
                _fit_family_predictions(
                    family,
                    x_train,
                    x_test,
                    maps[inner_train],
                    mean_parameter=mean_parameters[family],
                    residual_parameter=residual_parameters[family],
                    residual_variance_target=residual_variance_target,
                    maximum_residual_components=maximum_residual_components,
                )
            )
        train_disagreement = np.sqrt(
            np.mean(
                np.square(train_predictions["pls"] - train_predictions["ridge"]),
                axis=1,
            )
        )
        test_disagreement = np.sqrt(
            np.mean(
                np.square(test_predictions["pls"] - test_predictions["ridge"]),
                axis=1,
            )
        )
        component_values = {
            "ood": _empirical_percentile(train_ood, test_ood),
            "initial_state": _empirical_percentile(train_initial, test_initial),
            "delta": _empirical_percentile(train_delta, test_delta),
            "ewma": _empirical_percentile(train_ewma, test_ewma),
            "disagreement": _empirical_percentile(
                train_disagreement,
                test_disagreement,
            ),
        }
        validation_rows.append(
            pd.DataFrame(
                {
                    "validation_lot": validation_lot,
                    "true_error": np.mean(
                        np.abs(test_predictions["pls"] - maps[inner_test]),
                        axis=1,
                    ),
                    **{name: component_values[name] for name in components},
                }
            )
        )

    validation = pd.concat(validation_rows, ignore_index=True)
    weights = _simplex_weight_grid(len(components))
    equal = np.full(len(components), 1 / len(components))

    def lot_macro_aurc(candidate: np.ndarray) -> tuple[float, np.ndarray]:
        scores = validation[components].to_numpy() @ candidate
        per_lot = []
        for lot in np.unique(validation["validation_lot"]):
            selected = validation["validation_lot"].to_numpy() == lot
            per_lot.append(
                _aurc(
                    validation.loc[selected, "true_error"].to_numpy(),
                    scores[selected],
                )
            )
        return float(np.mean(per_lot)), np.asarray(per_lot)

    equal_aurc, equal_per_lot = lot_macro_aurc(equal)
    objectives = np.array([lot_macro_aurc(candidate)[0] for candidate in weights])
    selected = weights[int(np.argmin(objectives))]
    selected_aurc, selected_per_lot = lot_macro_aurc(selected)
    relative_gain = 1 - selected_aurc / equal_aurc
    improved_fraction = float(np.mean(selected_per_lot <= equal_per_lot))
    adopted = relative_gain >= 0.02 and improved_fraction >= 0.70
    return selected, {
        "inner_equal_macro_aurc": equal_aurc,
        "inner_selected_macro_aurc": selected_aurc,
        "inner_relative_gain": relative_gain,
        "inner_improved_lot_fraction": improved_fraction,
        "adoption_rule_passed": adopted,
        "grid_candidates": len(weights),
    }


def summarize_policy_robustness(
    lot_summary: pd.DataFrame,
    *,
    excluded_lot: int = 8,
    bootstrap_replicates: int = 10000,
    random_seed: int = 20260721,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Quantify lot influence and matched policy-minus-random uncertainty."""

    pivot = lot_summary.pivot(index="lot_number", columns="policy", values="aurc")
    if "random" not in pivot:
        raise ValueError("lot_summary must contain the random policy")
    influence_rows: list[dict[str, float | int | str]] = []
    for policy in pivot:
        differences = pivot[policy] - pivot["random"]
        for removed_lot in ("none", *[str(lot) for lot in pivot.index]):
            retained = (
                pivot
                if removed_lot == "none"
                else pivot.drop(index=int(removed_lot))
            )
            influence_rows.append(
                {
                    "policy": policy,
                    "removed_lot": removed_lot,
                    "macro_aurc": float(retained[policy].mean()),
                    "macro_random_aurc": float(retained["random"].mean()),
                    "relative_reduction_vs_random": float(
                        1 - retained[policy].mean() / retained["random"].mean()
                    ),
                    "worst_lot_aurc": float(retained[policy].max()),
                    "lots_worse_than_random": int(
                        (retained[policy] > retained["random"]).sum()
                    ),
                    "median_policy_minus_random": float(differences.median()),
                    "excluded_lot_of_interest": excluded_lot,
                }
            )

    bootstrap_rows: list[dict[str, float | int | str]] = []
    for policy_index, policy in enumerate(pivot):
        if policy == "random":
            continue
        differences = (pivot[policy] - pivot["random"]).to_numpy(dtype=float)
        samples = lot_cluster_bootstrap_mean(
            differences,
            replicates=bootstrap_replicates,
            random_seed=random_seed + policy_index,
        )
        bootstrap_rows.append(
            {
                "policy": policy,
                "observed_mean_difference": float(differences.mean()),
                "observed_median_difference": float(np.median(differences)),
                "bootstrap_mean_difference": float(samples.mean()),
                "bootstrap_p025": float(np.quantile(samples, 0.025)),
                "bootstrap_p975": float(np.quantile(samples, 0.975)),
                "probability_beats_random": float(np.mean(samples < 0)),
                "bootstrap_replicates": bootstrap_replicates,
            }
        )
    return pd.DataFrame(influence_rows), pd.DataFrame(bootstrap_rows)


def small_lot_aurc_resolution(
    errors: np.ndarray,
    *,
    lot_number: int,
    budgets: tuple[float, ...],
) -> pd.DataFrame:
    """Enumerate every ranking for a small lot and report attainable AURC spacing."""

    errors = np.asarray(errors, dtype=float)
    if len(errors) > 8:
        raise ValueError("exact permutation analysis is restricted to at most 8 wafers")
    aurcs = []
    for ranking in permutations(range(len(errors))):
        scores = np.empty(len(errors), dtype=float)
        scores[np.asarray(ranking)] = np.arange(len(errors), 0, -1, dtype=float)
        aurcs.append(_aurc(errors, scores))
    unique = np.unique(np.round(aurcs, 15))
    spacings = np.diff(unique)
    budget_counts = [
        min(int(np.rint(budget * len(errors))), len(errors) - 1)
        for budget in budgets
    ]
    return pd.DataFrame(
        [
            {
                "lot_number": lot_number,
                "wafer_count": len(errors),
                "ranking_permutations": len(aurcs),
                "unique_aurc_values": len(unique),
                "minimum_aurc_spacing": (
                    float(spacings.min()) if len(spacings) else np.nan
                ),
                "requested_budgets": ",".join(f"{value:g}" for value in budgets),
                "selected_counts_after_rounding": ",".join(
                    str(value) for value in budget_counts
                ),
            }
        ]
    )


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
    redundancy_threshold: float = 0.90,
    bootstrap_replicates: int = 10000,
) -> RiskEvaluation:
    """Evaluate target-free risk rankings under outer leave-one-lot-out splits."""

    validate_feature_table(feature_table)
    if not 0 < ewma_alpha <= 1:
        raise ValueError("ewma_alpha must be in (0, 1]")
    if not 0 <= redundancy_threshold <= 1:
        raise ValueError("redundancy_threshold must be in [0, 1]")
    wafer_rows, _, maps, lots = ordered_dense_maps(
        dense, set(feature_table.index)
    )
    keys = wafer_rows["experiment_key"].to_numpy()
    raw_features = feature_table.loc[keys].to_numpy(dtype=float)
    generator = np.random.default_rng(random_seed)
    score_rows: list[dict[str, float | int | str]] = []
    curve_rows: list[dict[str, float | int | str]] = []
    summary_rows: list[dict[str, float | int | str]] = []
    correlation_rows: list[dict[str, float | int | str]] = []
    alpha_rows: list[dict[str, float | int | str]] = []
    weight_rows: list[dict[str, float | int | str | bool]] = []

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
        centroid = z_train.mean(axis=0)
        train_initial, train_delta, train_ewma = _grouped_change_scores(
            z_train,
            keys[train],
            lots[train],
            centroid=centroid,
            ewma_alpha=ewma_alpha,
        )
        test_initial, test_delta, test_ewma = _grouped_change_scores(
            z_test,
            keys[test],
            lots[test],
            centroid=centroid,
            ewma_alpha=ewma_alpha,
        )
        for sensitivity_alpha in (0.1, 0.3, 0.5):
            for split, values, split_keys, split_lots, reference_ewma in (
                (
                    "train",
                    z_train,
                    keys[train],
                    lots[train],
                    train_ewma,
                ),
                (
                    "test",
                    z_test,
                    keys[test],
                    lots[test],
                    test_ewma,
                ),
            ):
                _, _, candidate = _grouped_change_scores(
                    values,
                    split_keys,
                    split_lots,
                    centroid=centroid,
                    ewma_alpha=sensitivity_alpha,
                )
                finite = np.isfinite(candidate) & np.isfinite(reference_ewma)
                alpha_rows.append(
                    {
                        "held_out_lot": int(held_out_lot),
                        "split": split,
                        "alpha": sensitivity_alpha,
                        "mean_ewma_distance": float(np.nanmean(candidate)),
                        "median_ewma_distance": float(np.nanmedian(candidate)),
                        "spearman_vs_preregistered_alpha": (
                            float(
                                spearmanr(
                                    candidate[finite],
                                    reference_ewma[finite],
                                ).statistic
                            )
                            if finite.sum() >= 3
                            else np.nan
                        ),
                    }
                )

        predictions = {}
        training_predictions = {}
        mean_parameters: dict[str, float] = {}
        residual_parameters: dict[str, float] = {}
        for family in ("ridge", "pls"):
            row = fold_diagnostics[
                (fold_diagnostics["held_out_lot"] == held_out_lot)
                & (fold_diagnostics["family"] == family)
            ].iloc[0]
            mean_parameters[family] = float(row["mean_parameter"])
            residual_parameters[family] = float(row["residual_parameter"])
            training_predictions[family], predictions[family] = (
                _fit_family_predictions(
                    family,
                    x_train,
                    x_test,
                    maps[train],
                    mean_parameter=mean_parameters[family],
                    residual_parameter=residual_parameters[family],
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

        train_raw_scores = {
            "ood": train_ood,
            "initial_state": train_initial,
            "delta": train_delta,
            "ewma": train_ewma,
            "disagreement": train_disagreement,
        }
        test_raw_scores = {
            "ood": test_ood,
            "initial_state": test_initial,
            "delta": test_delta,
            "ewma": test_ewma,
            "disagreement": test_disagreement,
        }
        correlation_rows.extend(
            _score_correlation_rows(
                train_raw_scores,
                held_out_lot=int(held_out_lot),
                split="train",
            )
        )
        correlation_rows.extend(
            _score_correlation_rows(
                test_raw_scores,
                held_out_lot=int(held_out_lot),
                split="test",
            )
        )

        percentiles = {
            "ood": _empirical_percentile(train_ood, test_ood),
            "initial_state": _empirical_percentile(
                train_initial, test_initial
            ),
            "delta": _empirical_percentile(train_delta, test_delta),
            "ewma": _empirical_percentile(train_ewma, test_ewma),
            "disagreement": _empirical_percentile(
                train_disagreement, test_disagreement
            ),
        }
        ood_initial_correlation = spearmanr(train_ood, train_initial).statistic
        combined_names = list(percentiles)
        if abs(ood_initial_correlation) >= redundancy_threshold:
            combined_names.remove("initial_state")
        combined = np.mean(
            np.column_stack([percentiles[name] for name in combined_names]),
            axis=1,
        )
        selected_weights, selection_diagnostics = _inner_lot_weight_selection(
            raw_features[train],
            maps[train],
            lots[train],
            keys[train],
            components=combined_names,
            pca_components=pca_components,
            ewma_alpha=ewma_alpha,
            mean_parameters=mean_parameters,
            residual_parameters=residual_parameters,
            residual_variance_target=residual_variance_target,
            maximum_residual_components=maximum_residual_components,
        )
        training_weighted = (
            np.column_stack([percentiles[name] for name in combined_names])
            @ selected_weights
        )
        for name, weight in zip(combined_names, selected_weights, strict=True):
            weight_rows.append(
                {
                    "held_out_lot": int(held_out_lot),
                    "component": name,
                    "selected_weight": float(weight),
                    **selection_diagnostics,
                }
            )
        policy_scores = {
            **percentiles,
            "combined": combined,
            "training_weighted_candidate": training_weighted,
            "oracle": true_error,
        }

        test_keys = keys[test]
        for index, key in enumerate(test_keys):
            score_rows.append(
                {
                    "experiment_key": key,
                    "lot_number": int(held_out_lot),
                    "true_pls_mae": true_error[index],
                    **{name + "_percentile": value[index] for name, value in percentiles.items()},
                    "combined_risk": combined[index],
                    "training_weighted_risk": training_weighted[index],
                    "combined_components": ",".join(combined_names),
                    "ood_initial_train_spearman": float(ood_initial_correlation),
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

    wafer_scores = pd.DataFrame(score_rows)
    lot_summary = pd.DataFrame(summary_rows)
    influence, bootstrap = summarize_policy_robustness(
        lot_summary,
        bootstrap_replicates=bootstrap_replicates,
        random_seed=random_seed,
    )
    smallest_lot = int(wafer_scores.groupby("lot_number").size().idxmin())
    smallest_errors = wafer_scores.loc[
        wafer_scores["lot_number"] == smallest_lot, "true_pls_mae"
    ].to_numpy()
    resolution = small_lot_aurc_resolution(
        smallest_errors,
        lot_number=smallest_lot,
        budgets=budgets,
    )
    return RiskEvaluation(
        wafer_scores=wafer_scores,
        risk_curves=pd.DataFrame(curve_rows),
        lot_summary=lot_summary,
        score_correlations=pd.DataFrame(correlation_rows),
        alpha_sensitivity=pd.DataFrame(alpha_rows),
        influence_summary=influence,
        bootstrap_summary=bootstrap,
        small_lot_resolution=resolution,
        weight_selection=pd.DataFrame(weight_rows),
    )

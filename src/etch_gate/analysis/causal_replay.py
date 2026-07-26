"""Strictly chronological selective-metrology replay with causal feedback."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
from sklearn.metrics import pairwise_distances

from etch_gate.analysis.drift import (
    empirical_percentile,
    grouped_change_scores,
)
from etch_gate.analysis.process_baseline import (
    FeatureTransform,
    ResidualBasis,
    decompose_maps,
    fit_regressor,
    fit_residual_basis,
    ordered_dense_maps,
    predict_regressor,
    prepare_feature_transform,
    select_parameter,
    validate_feature_table,
)
from etch_gate.statistics import lot_cluster_bootstrap_mean


@dataclass(frozen=True)
class CausalReplayResult:
    """Chronological wafer decisions and policy-level summaries."""

    wafer_timeline: pd.DataFrame
    policy_budget_summary: pd.DataFrame
    lot_summary: pd.DataFrame
    bootstrap_summary: pd.DataFrame


@dataclass
class _FoldState:
    transform: FeatureTransform
    reference: float
    template: np.ndarray
    basis: ResidualBasis
    x_train: np.ndarray
    training_shift: np.ndarray
    training_residual_scores: np.ndarray
    mean_parameters: dict[str, float]
    residual_parameters: dict[str, float]
    mean_models: dict[str, object]
    residual_models: dict[str, object]
    risk_pca: PCA
    risk_references: dict[str, np.ndarray]
    combined_components: list[str]


def causal_quota_decisions(
    scores: np.ndarray,
    *,
    budget: float,
    threshold: float,
) -> np.ndarray:
    """Select online without ranking future scores while meeting a rounded lot quota."""

    scores = np.asarray(scores, dtype=float)
    if not 0 <= budget <= 1:
        raise ValueError("budget must be in [0, 1]")
    if not np.isfinite(scores).all():
        raise ValueError("scores must be finite")
    size = len(scores)
    total_quota = min(int(np.rint(budget * size)), size)
    selected = np.zeros(size, dtype=bool)
    selected_count = 0
    for index, score in enumerate(scores):
        remaining_after = size - index - 1
        minimum_required_now = max(0, total_quota - remaining_after)
        prefix_cap = min(total_quota, int(np.ceil(budget * (index + 1))))
        forced = selected_count < minimum_required_now
        risk_eligible = score >= threshold and selected_count < prefix_cap
        if selected_count < total_quota and (forced or risk_eligible):
            selected[index] = True
            selected_count += 1
    if selected_count != total_quota:
        raise RuntimeError("causal quota controller did not meet its rounded quota")
    return selected


def _periodic_decisions(size: int, budget: float) -> np.ndarray:
    total = min(int(np.rint(budget * size)), size)
    selected = np.zeros(size, dtype=bool)
    if total:
        positions = np.unique(np.rint(np.linspace(0, size - 1, total)).astype(int))
        selected[positions] = True
    return selected


def _fit_fold_state(
    raw_features: np.ndarray,
    maps: np.ndarray,
    lots: np.ndarray,
    keys: np.ndarray,
    *,
    pls_parameters: tuple[float, ...],
    ridge_parameters: tuple[float, ...],
    residual_variance_target: float,
    maximum_residual_components: int,
    risk_pca_components: int,
    ewma_alpha: float,
    redundancy_threshold: float,
) -> _FoldState:
    transform = prepare_feature_transform(raw_features)
    x_train = transform.apply(raw_features)
    reference, template, shifts, _, residuals, _ = decompose_maps(maps, maps[:1])
    basis = fit_residual_basis(
        residuals,
        variance_target=residual_variance_target,
        maximum_components=maximum_residual_components,
    )
    residual_scores = basis.transform(residuals)
    mean_parameters: dict[str, float] = {}
    residual_parameters: dict[str, float] = {}
    mean_models: dict[str, object] = {}
    residual_models: dict[str, object] = {}
    for family, parameters in (
        ("ridge", list(ridge_parameters)),
        ("pls", list(pls_parameters)),
    ):
        mean_parameter, _ = select_parameter(
            raw_features,
            maps,
            lots,
            family=family,
            parameters=parameters,
            target_part="mean_shift",
            variance_target=residual_variance_target,
            maximum_components=maximum_residual_components,
        )
        residual_parameter, _ = select_parameter(
            raw_features,
            maps,
            lots,
            family=family,
            parameters=parameters,
            target_part="residual",
            variance_target=residual_variance_target,
            maximum_components=maximum_residual_components,
        )
        mean_parameters[family] = float(mean_parameter)
        residual_parameters[family] = float(residual_parameter)
        mean_models[family] = fit_regressor(
            family,
            mean_parameter,
            x_train,
            shifts,
        )
        residual_models[family] = fit_regressor(
            family,
            residual_parameter,
            x_train,
            residual_scores,
        )

    component_count = min(risk_pca_components, len(x_train) - 1, x_train.shape[1])
    risk_pca = PCA(n_components=component_count, svd_solver="full").fit(x_train)
    z_train = risk_pca.transform(x_train)
    centroid = z_train.mean(axis=0)
    distances = pairwise_distances(z_train)
    np.fill_diagonal(distances, np.inf)
    initial, delta, ewma = grouped_change_scores(
        z_train,
        keys,
        lots,
        centroid=centroid,
        ewma_alpha=ewma_alpha,
    )
    ridge_prediction = _predict_maps(
        x_train,
        reference,
        template,
        basis,
        mean_models["ridge"],
        residual_models["ridge"],
    )
    pls_prediction = _predict_maps(
        x_train,
        reference,
        template,
        basis,
        mean_models["pls"],
        residual_models["pls"],
    )
    disagreement = np.sqrt(
        np.mean(np.square(pls_prediction - ridge_prediction), axis=1)
    )
    risk_references = {
        "ood": distances.min(axis=1),
        "initial_state": initial,
        "delta": delta,
        "ewma": ewma,
        "disagreement": disagreement,
    }
    correlation = spearmanr(risk_references["ood"], initial).statistic
    combined_components = list(risk_references)
    if abs(correlation) >= redundancy_threshold:
        combined_components.remove("initial_state")
    return _FoldState(
        transform=transform,
        reference=reference,
        template=template,
        basis=basis,
        x_train=x_train,
        training_shift=shifts,
        training_residual_scores=residual_scores,
        mean_parameters=mean_parameters,
        residual_parameters=residual_parameters,
        mean_models=mean_models,
        residual_models=residual_models,
        risk_pca=risk_pca,
        risk_references=risk_references,
        combined_components=combined_components,
    )


def _predict_maps(
    features: np.ndarray,
    reference: float,
    template: np.ndarray,
    basis: ResidualBasis,
    mean_model: object,
    residual_model: object,
) -> np.ndarray:
    shift = predict_regressor(mean_model, features)[:, 0]
    residual = basis.inverse_transform(predict_regressor(residual_model, features))
    return reference + template + shift[:, None] + residual


def _causal_risk_scores(
    state: _FoldState,
    raw_test_features: np.ndarray,
    test_keys: np.ndarray,
    test_lots: np.ndarray,
    *,
    ewma_alpha: float,
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    x_test = state.transform.apply(raw_test_features)
    z_train = state.risk_pca.transform(state.x_train)
    z_test = state.risk_pca.transform(x_test)
    centroid = z_train.mean(axis=0)
    initial, delta, ewma = grouped_change_scores(
        z_test,
        test_keys,
        test_lots,
        centroid=centroid,
        ewma_alpha=ewma_alpha,
    )
    ridge_prediction = _predict_maps(
        x_test,
        state.reference,
        state.template,
        state.basis,
        state.mean_models["ridge"],
        state.residual_models["ridge"],
    )
    pls_prediction = _predict_maps(
        x_test,
        state.reference,
        state.template,
        state.basis,
        state.mean_models["pls"],
        state.residual_models["pls"],
    )
    raw_scores = {
        "ood": pairwise_distances(z_test, z_train).min(axis=1),
        "initial_state": initial,
        "delta": delta,
        "ewma": ewma,
        "disagreement": np.sqrt(
            np.mean(np.square(pls_prediction - ridge_prediction), axis=1)
        ),
    }
    percentiles = {
        name: empirical_percentile(state.risk_references[name], values)
        for name, values in raw_scores.items()
    }
    percentiles["combined"] = np.mean(
        np.column_stack(
            [percentiles[name] for name in state.combined_components]
        ),
        axis=1,
    )
    percentiles["validated_combined"] = percentiles["combined"].copy()
    return percentiles, pls_prediction


def _replay_feedback(
    state: _FoldState,
    x_test: np.ndarray,
    targets: np.ndarray,
    selected: np.ndarray,
    *,
    feedback: str,
    bias_alpha: float,
) -> tuple[np.ndarray, np.ndarray, int, float]:
    start = perf_counter()
    mean_model = state.mean_models["pls"]
    residual_model = state.residual_models["pls"]
    extra_features: list[np.ndarray] = []
    extra_shifts: list[float] = []
    extra_residual_scores: list[np.ndarray] = []
    bias = 0.0
    predictions = []
    system_errors = []
    updates = 0
    for index, features in enumerate(x_test):
        prediction = _predict_maps(
            features[None, :],
            state.reference,
            state.template,
            state.basis,
            mean_model,
            residual_model,
        )[0]
        frozen_without_bias = prediction.copy()
        if feedback == "F1":
            prediction = prediction + bias
        predictions.append(prediction)
        error = float(np.mean(np.abs(prediction - targets[index])))
        system_errors.append(0.0 if selected[index] else error)
        if not selected[index] or feedback == "F0":
            continue
        updates += 1
        if feedback == "F1":
            observed_bias = float(np.mean(targets[index] - frozen_without_bias))
            bias = bias_alpha * observed_bias + (1 - bias_alpha) * bias
            continue
        shift = float(targets[index].mean() - state.reference)
        residual = (
            targets[index]
            - targets[index].mean()
            - state.template
        )
        extra_features.append(features.copy())
        extra_shifts.append(shift)
        extra_residual_scores.append(state.basis.transform(residual[None, :])[0])
        augmented_x = np.vstack([state.x_train, *extra_features])
        mean_model = fit_regressor(
            "pls",
            state.mean_parameters["pls"],
            augmented_x,
            np.concatenate([state.training_shift, extra_shifts]),
        )
        if feedback == "F3":
            residual_model = fit_regressor(
                "pls",
                state.residual_parameters["pls"],
                augmented_x,
                np.vstack(
                    [state.training_residual_scores, *extra_residual_scores]
                ),
            )
    return (
        np.asarray(predictions),
        np.asarray(system_errors),
        updates,
        perf_counter() - start,
    )


def _stream_metrics(
    true_errors: np.ndarray,
    system_errors: np.ndarray,
    selected: np.ndarray,
    *,
    drift_error_threshold: float,
) -> dict[str, float | int]:
    unmeasured = ~selected
    high_error_count = max(1, int(np.ceil(0.2 * len(true_errors))))
    high_error = np.argsort(-true_errors)[:high_error_count]
    captured = float(selected[high_error].mean())
    drift_positions = np.flatnonzero(true_errors > drift_error_threshold)
    drift_onset = int(drift_positions[0]) if len(drift_positions) else -1
    recovery_count = np.nan
    if drift_onset >= 0:
        recovery = np.flatnonzero(
            true_errors[drift_onset + 1 :] <= drift_error_threshold
        )
        recovery_count = float(
            recovery[0] + 1 if len(recovery) else len(true_errors) - drift_onset
        )
    return {
        "total_system_mae": float(system_errors.mean()),
        "unmeasured_wafer_mae": (
            float(true_errors[unmeasured].mean()) if unmeasured.any() else np.nan
        ),
        "measured_fraction": float(selected.mean()),
        "high_error_capture": captured,
        "p95_system_error": float(np.quantile(system_errors, 0.95)),
        "cumulative_system_error": float(system_errors.sum()),
        "measured_wafers": int(selected.sum()),
        "drift_error_threshold": drift_error_threshold,
        "drift_onset_wafer_order": drift_onset + 1 if drift_onset >= 0 else np.nan,
        "recovery_wafer_count": recovery_count,
    }


def _bootstrap_policy_difference(
    lot_summary: pd.DataFrame,
    *,
    replicates: int,
    random_seed: int,
) -> pd.DataFrame:
    rows = []
    direct = lot_summary[
        (lot_summary["mode"] == "direct_substitution")
        & (lot_summary["feedback"] == "F0")
    ]
    for budget_index, budget in enumerate(sorted(direct["budget"].unique())):
        subset = direct[direct["budget"] == budget]
        pivot = subset.pivot(
            index="test_lot",
            columns="policy",
            values="total_system_mae",
        )
        if {"combined", "random"} - set(pivot):
            continue
        differences = (pivot["combined"] - pivot["random"]).to_numpy()
        samples = lot_cluster_bootstrap_mean(
            differences,
            replicates=replicates,
            random_seed=random_seed + budget_index,
        )
        rows.append(
            {
                "budget": budget,
                "policy": "combined",
                "comparator": "random",
                "observed_mean_difference": float(differences.mean()),
                "bootstrap_p025": float(np.quantile(samples, 0.025)),
                "bootstrap_p975": float(np.quantile(samples, 0.975)),
                "probability_beats_random": float(np.mean(samples < 0)),
                "replicates": replicates,
            }
        )
    return pd.DataFrame(rows)


def evaluate_causal_replay(
    feature_table: pd.DataFrame,
    dense: pd.DataFrame,
    *,
    minimum_training_lots: int = 3,
    budgets: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.5),
    pls_parameters: tuple[float, ...] = (1.0, 2.0, 4.0),
    ridge_parameters: tuple[float, ...] = (0.1, 1.0, 10.0, 100.0, 1000.0),
    residual_variance_target: float = 0.90,
    maximum_residual_components: int = 8,
    risk_pca_components: int = 10,
    ewma_alpha: float = 0.3,
    bias_alpha: float = 0.3,
    redundancy_threshold: float = 0.90,
    random_replicates: int = 100,
    bootstrap_replicates: int = 10000,
    random_seed: int = 20260721,
) -> CausalReplayResult:
    """Replay each future lot in wafer order without future targets or scores."""

    validate_feature_table(feature_table)
    wafer_table, _, maps, lots = ordered_dense_maps(
        dense,
        set(feature_table.index),
    )
    keys = wafer_table["experiment_key"].to_numpy()
    raw_features = feature_table.loc[keys].to_numpy(dtype=float)
    unique_lots = np.asarray(sorted(np.unique(lots)))
    timeline_rows: list[dict[str, float | int | str | bool]] = []
    lot_rows: list[dict[str, float | int | str]] = []
    generator = np.random.default_rng(random_seed)
    policies = (
        "no_metrology",
        "periodic",
        "ood",
        "disagreement",
        "combined",
        "validated_combined",
        "oracle",
    )

    for lot_position in range(minimum_training_lots, len(unique_lots)):
        test_lot = int(unique_lots[lot_position])
        train = lots < test_lot
        test = lots == test_lot
        test_positions = np.flatnonzero(test)
        test_positions = test_positions[np.argsort(keys[test_positions])]
        state = _fit_fold_state(
            raw_features[train],
            maps[train],
            lots[train],
            keys[train],
            pls_parameters=pls_parameters,
            ridge_parameters=ridge_parameters,
            residual_variance_target=residual_variance_target,
            maximum_residual_components=maximum_residual_components,
            risk_pca_components=risk_pca_components,
            ewma_alpha=ewma_alpha,
            redundancy_threshold=redundancy_threshold,
        )
        test_features = raw_features[test_positions]
        x_test = state.transform.apply(test_features)
        targets = maps[test_positions]
        test_keys = keys[test_positions]
        test_lots = lots[test_positions]
        risk_scores, frozen_predictions = _causal_risk_scores(
            state,
            test_features,
            test_keys,
            test_lots,
            ewma_alpha=ewma_alpha,
        )
        true_errors = np.mean(np.abs(frozen_predictions - targets), axis=1)
        training_prediction = _predict_maps(
            state.x_train,
            state.reference,
            state.template,
            state.basis,
            state.mean_models["pls"],
            state.residual_models["pls"],
        )
        training_error_threshold = float(
            np.quantile(
                np.mean(np.abs(training_prediction - maps[train]), axis=1),
                0.95,
            )
        )
        policy_scores = {
            "ood": risk_scores["ood"],
            "disagreement": risk_scores["disagreement"],
            "combined": risk_scores["combined"],
            "validated_combined": risk_scores["validated_combined"],
            "oracle": empirical_percentile(true_errors, true_errors),
        }

        for budget in budgets:
            quota = min(int(np.rint(budget * len(test_positions))), len(test_positions))
            selections: dict[str, np.ndarray] = {
                "no_metrology": np.zeros(len(test_positions), dtype=bool),
                "periodic": _periodic_decisions(len(test_positions), budget),
            }
            for policy, scores in policy_scores.items():
                selections[policy] = causal_quota_decisions(
                    scores,
                    budget=budget,
                    threshold=1 - budget,
                )

            for policy in policies:
                selected = selections[policy]
                for mode in ("ranking_only", "direct_substitution"):
                    if mode == "ranking_only" and policy not in {
                        "no_metrology",
                        "periodic",
                    }:
                        count = quota
                        ranked = np.argsort(
                            -policy_scores[policy],
                            kind="stable",
                        )
                        selected_for_mode = np.zeros(len(test_positions), dtype=bool)
                        selected_for_mode[ranked[:count]] = True
                    else:
                        selected_for_mode = selected
                    system_errors = np.where(selected_for_mode, 0.0, true_errors)
                    metrics = _stream_metrics(
                        true_errors,
                        system_errors,
                        selected_for_mode,
                        drift_error_threshold=training_error_threshold,
                    )
                    lot_rows.append(
                        {
                            "test_lot": test_lot,
                            "mode": mode,
                            "feedback": "F0",
                            "policy": policy,
                            "budget": budget,
                            "replicate": 0,
                            "updates": 0,
                            "update_runtime_seconds": 0.0,
                            **metrics,
                        }
                    )
                    for local_index, key in enumerate(test_keys):
                        timeline_rows.append(
                            {
                                "experiment_key": key,
                                "test_lot": test_lot,
                                "wafer_order": local_index + 1,
                                "mode": mode,
                                "feedback": "F0",
                                "policy": policy,
                                "budget": budget,
                                "replicate": 0,
                                "risk": (
                                    policy_scores[policy][local_index]
                                    if policy in policy_scores
                                    else np.nan
                                ),
                                "measured": bool(selected_for_mode[local_index]),
                                "vm_error_before_measurement": true_errors[local_index],
                                "system_error": system_errors[local_index],
                            }
                        )

            for feedback in ("F0", "F1", "F2", "F3"):
                selected = selections["combined"]
                predictions, system_errors, updates, runtime = _replay_feedback(
                    state,
                    x_test,
                    targets,
                    selected,
                    feedback=feedback,
                    bias_alpha=bias_alpha,
                )
                online_errors = np.mean(np.abs(predictions - targets), axis=1)
                metrics = _stream_metrics(
                    online_errors,
                    system_errors,
                    selected,
                    drift_error_threshold=training_error_threshold,
                )
                lot_rows.append(
                    {
                        "test_lot": test_lot,
                        "mode": "causal_feedback",
                        "feedback": feedback,
                        "policy": "combined",
                        "budget": budget,
                        "replicate": 0,
                        "updates": updates,
                        "update_runtime_seconds": runtime,
                        **metrics,
                    }
                )
                for local_index, key in enumerate(test_keys):
                    timeline_rows.append(
                        {
                            "experiment_key": key,
                            "test_lot": test_lot,
                            "wafer_order": local_index + 1,
                            "mode": "causal_feedback",
                            "feedback": feedback,
                            "policy": "combined",
                            "budget": budget,
                            "replicate": 0,
                            "risk": risk_scores["combined"][local_index],
                            "measured": bool(selected[local_index]),
                            "vm_error_before_measurement": online_errors[local_index],
                            "system_error": system_errors[local_index],
                        }
                    )

            for replicate in range(random_replicates):
                random_scores = generator.random(len(test_positions))
                selected = causal_quota_decisions(
                    random_scores,
                    budget=budget,
                    threshold=1 - budget,
                )
                system_errors = np.where(selected, 0.0, true_errors)
                metrics = _stream_metrics(
                    true_errors,
                    system_errors,
                    selected,
                    drift_error_threshold=training_error_threshold,
                )
                lot_rows.append(
                    {
                        "test_lot": test_lot,
                        "mode": "direct_substitution",
                        "feedback": "F0",
                        "policy": "random",
                        "budget": budget,
                        "replicate": replicate,
                        "updates": 0,
                        "update_runtime_seconds": 0.0,
                        **metrics,
                    }
                )

    lots_frame = pd.DataFrame(lot_rows)
    lot_summary = (
        lots_frame.groupby(
            ["test_lot", "mode", "feedback", "policy", "budget"],
            as_index=False,
        )
        .agg(
            total_system_mae=("total_system_mae", "mean"),
            unmeasured_wafer_mae=("unmeasured_wafer_mae", "mean"),
            measured_fraction=("measured_fraction", "mean"),
            high_error_capture=("high_error_capture", "mean"),
            p95_system_error=("p95_system_error", "mean"),
            cumulative_system_error=("cumulative_system_error", "mean"),
            updates=("updates", "mean"),
            update_runtime_seconds=("update_runtime_seconds", "mean"),
            drift_error_threshold=("drift_error_threshold", "mean"),
            drift_onset_wafer_order=("drift_onset_wafer_order", "mean"),
            recovery_wafer_count=("recovery_wafer_count", "mean"),
            random_replicates=("replicate", "nunique"),
        )
    )
    policy_summary = (
        lot_summary.groupby(
            ["mode", "feedback", "policy", "budget"],
            as_index=False,
        )
        .agg(
            lot_macro_system_mae=("total_system_mae", "mean"),
            lot_macro_unmeasured_mae=("unmeasured_wafer_mae", "mean"),
            mean_measured_fraction=("measured_fraction", "mean"),
            mean_high_error_capture=("high_error_capture", "mean"),
            worst_lot_mae=("total_system_mae", "max"),
            mean_p95_system_error=("p95_system_error", "mean"),
            cumulative_error=("cumulative_system_error", "sum"),
            mean_updates=("updates", "mean"),
            mean_update_runtime_seconds=("update_runtime_seconds", "mean"),
            mean_recovery_wafer_count=("recovery_wafer_count", "mean"),
        )
    )
    bootstrap = _bootstrap_policy_difference(
        lot_summary,
        replicates=bootstrap_replicates,
        random_seed=random_seed,
    )
    return CausalReplayResult(
        wafer_timeline=pd.DataFrame(timeline_rows),
        policy_budget_summary=policy_summary,
        lot_summary=lot_summary,
        bootstrap_summary=bootstrap,
    )

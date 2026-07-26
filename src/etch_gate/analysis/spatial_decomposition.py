"""Detailed mean-shift, residual-map, and oracle stage evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from etch_gate.analysis.process_baseline import (
    decompose_maps,
    evaluate_process_baselines,
    fit_residual_basis,
    ordered_dense_maps,
)


@dataclass(frozen=True)
class SpatialDecompositionResult:
    """Point predictions, wafer metrics, coordinate metrics, and gate summary."""

    point_predictions: pd.DataFrame
    wafer_metrics: pd.DataFrame
    coordinate_metrics: pd.DataFrame
    stage_summary: pd.DataFrame
    gate: dict[str, object]


def coordinate_zones(coordinates: np.ndarray) -> np.ndarray:
    """Assign deterministic center/middle/edge zones by normalized wafer radius."""

    if coordinates.ndim != 2 or coordinates.shape[1] != 2:
        raise ValueError("coordinates must have shape (points, 2)")
    radii = np.linalg.norm(coordinates, axis=1)
    maximum = float(radii.max())
    if maximum <= 0:
        raise ValueError("coordinate radii must include a nonzero wafer radius")
    normalized = radii / maximum
    return np.where(
        normalized <= 1 / 3,
        "center",
        np.where(normalized <= 2 / 3, "middle", "edge"),
    )


def _oracle_predictions(
    feature_table: pd.DataFrame,
    dense: pd.DataFrame,
    *,
    residual_variance_target: float,
    maximum_residual_components: int,
) -> pd.DataFrame:
    wafer_rows, coordinates, maps, lots = ordered_dense_maps(
        dense, set(feature_table.index)
    )
    keys = wafer_rows["experiment_key"].tolist()
    rows = []
    for held_out_lot in np.unique(lots):
        train = lots != held_out_lot
        test = ~train
        (
            reference,
            template,
            _,
            test_shift,
            training_residual,
            test_residual,
        ) = decompose_maps(maps[train], maps[test])
        basis = fit_residual_basis(
            training_residual,
            variance_target=residual_variance_target,
            maximum_components=maximum_residual_components,
        )
        zero_residual = reference + template + test_shift[:, None]
        reconstructed = zero_residual + basis.inverse_transform(
            basis.transform(test_residual)
        )
        for local_index, global_index in enumerate(np.flatnonzero(test)):
            for stage, prediction in (
                ("oracle_true_mean_zero_residual", zero_residual[local_index]),
                ("oracle_true_mean_pca_reconstruction", reconstructed[local_index]),
            ):
                for point, (x, y) in enumerate(coordinates):
                    rows.append(
                        {
                            "experiment_key": keys[global_index],
                            "lot_number": int(lots[global_index]),
                            "stage": stage,
                            "X": float(x),
                            "Y": float(y),
                            "observed": float(maps[global_index, point]),
                            "predicted": float(prediction[point]),
                            "deployable": False,
                        }
                    )
    return pd.DataFrame(rows)


def _wafer_metrics(points: pd.DataFrame) -> pd.DataFrame:
    coordinates = (
        points[["X", "Y"]].drop_duplicates().sort_values(["Y", "X"]).to_numpy()
    )
    zones = coordinate_zones(coordinates)
    zone_by_coordinate = {
        (float(x), float(y)): zone
        for (x, y), zone in zip(coordinates, zones, strict=True)
    }
    rows = []
    for (key, lot, stage), group in points.groupby(
        ["experiment_key", "lot_number", "stage"], sort=True
    ):
        observed = group["observed"].to_numpy(dtype=float)
        predicted = group["predicted"].to_numpy(dtype=float)
        residual_observed = observed - observed.mean()
        residual_predicted = predicted - predicted.mean()
        error = predicted - observed
        residual_error = residual_predicted - residual_observed
        if np.std(residual_observed) <= 1e-12 or np.std(residual_predicted) <= 1e-12:
            spatial_correlation = np.nan
        else:
            spatial_correlation = float(
                np.corrcoef(residual_observed, residual_predicted)[0, 1]
            )
        group_zones = np.asarray(
            [
                zone_by_coordinate[(float(x), float(y))]
                for x, y in group[["X", "Y"]].itertuples(index=False, name=None)
            ]
        )
        zone_errors = {}
        for zone in ("center", "middle", "edge"):
            mask = group_zones == zone
            zone_errors[zone] = (
                float(abs(predicted[mask].mean() - observed[mask].mean()))
                if mask.any()
                else np.nan
            )
        observed_center_edge = (
            observed[group_zones == "center"].mean()
            - observed[group_zones == "edge"].mean()
        )
        predicted_center_edge = (
            predicted[group_zones == "center"].mean()
            - predicted[group_zones == "edge"].mean()
        )
        rows.append(
            {
                "experiment_key": key,
                "lot_number": int(lot),
                "stage": stage,
                "full_map_mae": float(np.mean(np.abs(error))),
                "full_map_rmse": float(np.sqrt(np.mean(np.square(error)))),
                "mean_shift_absolute_error": float(abs(error.mean())),
                "mean_centered_residual_mae": float(np.mean(np.abs(residual_error))),
                "mean_centered_residual_rmse": float(
                    np.sqrt(np.mean(np.square(residual_error)))
                ),
                "spatial_correlation_after_mean_removal": spatial_correlation,
                "center_mean_error": zone_errors["center"],
                "middle_zone_mean_error": zone_errors["middle"],
                "edge_mean_error": zone_errors["edge"],
                "center_to_edge_difference_error": float(
                    abs(predicted_center_edge - observed_center_edge)
                ),
                "map_standard_deviation_error": float(
                    abs(predicted.std(ddof=0) - observed.std(ddof=0))
                ),
                "map_range_error": float(abs(np.ptp(predicted) - np.ptp(observed))),
                "worst_point_absolute_error": float(np.max(np.abs(error))),
                "p95_point_absolute_error": float(np.quantile(np.abs(error), 0.95)),
            }
        )
    return pd.DataFrame(rows)


def _residual_gain_gate(
    wafer_metrics: pd.DataFrame,
    *,
    bootstrap_replicates: int,
    random_seed: int,
) -> dict[str, object]:
    paired = wafer_metrics[
        wafer_metrics["stage"].isin(["mean_shift", "full_map"])
    ].pivot(
        index=["experiment_key", "lot_number"],
        columns="stage",
        values="full_map_mae",
    )
    lot_means = paired.groupby("lot_number")[["mean_shift", "full_map"]].mean()
    gain = 1 - lot_means["full_map"].mean() / lot_means["mean_shift"].mean()
    lots = lot_means.index.to_numpy()
    generator = np.random.default_rng(random_seed)
    bootstrap = []
    for _ in range(bootstrap_replicates):
        sampled = generator.choice(lots, size=len(lots), replace=True)
        sampled_means = lot_means.loc[sampled]
        bootstrap.append(
            1
            - sampled_means["full_map"].mean()
            / sampled_means["mean_shift"].mean()
        )
    interval = np.quantile(bootstrap, [0.025, 0.975])
    improved_lots = int(
        (lot_means["full_map"] < lot_means["mean_shift"]).sum()
    )
    if gain <= 0:
        status = "FAIL"
    elif gain >= 0.05 and interval[0] > 0 and improved_lots >= 7:
        status = "PASS"
    else:
        status = "QUALIFIED"
    return {
        "status": status,
        "relative_residual_stage_gain": float(gain),
        "lot_cluster_bootstrap_95_interval": [
            float(interval[0]),
            float(interval[1]),
        ],
        "lots_improved": improved_lots,
        "total_lots": len(lot_means),
        "bootstrap_replicates": bootstrap_replicates,
        "random_seed": random_seed,
    }


def evaluate_spatial_decomposition(
    feature_table: pd.DataFrame,
    dense: pd.DataFrame,
    *,
    pls_parameters: tuple[float, ...] = (1.0, 2.0, 4.0),
    residual_variance_target: float = 0.90,
    maximum_residual_components: int = 8,
    bootstrap_replicates: int = 10000,
    random_seed: int = 20260726,
) -> SpatialDecompositionResult:
    """Evaluate deployable and oracle map stages on identical outer folds."""

    points, _, _ = evaluate_process_baselines(
        feature_table,
        dense,
        families=("pls",),
        pls_parameters=pls_parameters,
        residual_variance_target=residual_variance_target,
        maximum_residual_components=maximum_residual_components,
    )
    deployable = points.drop(columns=["family", "predicted_std"]).copy()
    deployable["deployable"] = True
    oracle = _oracle_predictions(
        feature_table,
        dense,
        residual_variance_target=residual_variance_target,
        maximum_residual_components=maximum_residual_components,
    )
    all_points = pd.concat([deployable, oracle], ignore_index=True)
    metrics = _wafer_metrics(all_points)
    coordinate_metrics = (
        all_points.assign(
            absolute_error=lambda frame: (
                frame["predicted"] - frame["observed"]
            ).abs()
        )
        .groupby(["stage", "X", "Y"], as_index=False)["absolute_error"]
        .mean()
        .rename(columns={"absolute_error": "coordinate_mae"})
    )
    stage_summary = (
        metrics.groupby("stage", as_index=False)
        .agg(
            wafer_macro_mae=("full_map_mae", "mean"),
            wafer_macro_rmse=("full_map_rmse", "mean"),
            lot_macro_mae=(
                "full_map_mae",
                lambda values: metrics.loc[values.index]
                .groupby("lot_number")["full_map_mae"]
                .mean()
                .mean(),
            ),
            mean_shift_mae=("mean_shift_absolute_error", "mean"),
            residual_mae=("mean_centered_residual_mae", "mean"),
            residual_rmse=("mean_centered_residual_rmse", "mean"),
            median_spatial_correlation=(
                "spatial_correlation_after_mean_removal",
                "median",
            ),
            worst_point_error=("worst_point_absolute_error", "mean"),
        )
    )
    gate = _residual_gain_gate(
        metrics,
        bootstrap_replicates=bootstrap_replicates,
        random_seed=random_seed,
    )
    return SpatialDecompositionResult(
        point_predictions=all_points,
        wafer_metrics=metrics,
        coordinate_metrics=coordinate_metrics,
        stage_summary=stage_summary,
        gate=gate,
    )

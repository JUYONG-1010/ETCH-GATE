"""Statistical summaries for the process-model benchmark."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def summarize_model_benchmark(
    wafer_metrics: pd.DataFrame,
    point_predictions: pd.DataFrame,
    *,
    bootstrap_replicates: int = 10_000,
    random_seed: int = 20260721,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Compare full-map models and audit raw GPR uncertainty."""

    full = wafer_metrics[wafer_metrics["stage"] == "full_map"].copy()
    model_summary = (
        full.groupby("family")
        .agg(
            wafer_macro_mae=("mae", "mean"),
            wafer_macro_rmse=("rmse", "mean"),
            median_wafer_mae=("mae", "median"),
        )
        .reset_index()
    )
    mean_shift_rmse = (
        full.assign(squared_mean_error=np.square(full["mean_error"]))
        .groupby("family")["squared_mean_error"]
        .mean()
        .pow(0.5)
        .rename("wafer_mean_rmse")
        .reset_index()
    )
    lot_metrics = (
        full.groupby(["lot_number", "family"])["mae"]
        .mean()
        .rename("lot_mae")
        .reset_index()
    )
    lot_wide = lot_metrics.pivot(index="lot_number", columns="family", values="lot_mae")
    wins = lot_wide.idxmin(axis=1).value_counts()
    model_summary = model_summary.merge(mean_shift_rmse, on="family")
    model_summary["best_lots"] = model_summary["family"].map(wins).fillna(0).astype(int)

    if not {"pls", "gpr"}.issubset(lot_wide.columns):
        raise ValueError("PLS and GPR full-map results are required")
    paired = full.pivot(
        index=["experiment_key", "lot_number"],
        columns="family",
        values="mae",
    ).reset_index()
    lot_arrays = {
        lot: group[["pls", "gpr"]].to_numpy(dtype=float)
        for lot, group in paired.groupby("lot_number")
    }
    lots = np.asarray(sorted(lot_arrays))
    generator = np.random.default_rng(random_seed)
    bootstrap_difference = np.empty(bootstrap_replicates, dtype=float)
    for replicate in range(bootstrap_replicates):
        sampled_lots = generator.choice(lots, size=len(lots), replace=True)
        sampled = np.vstack([lot_arrays[lot] for lot in sampled_lots])
        bootstrap_difference[replicate] = sampled[:, 1].mean() / sampled[:, 0].mean() - 1

    gpr_wafers = full[full["family"] == "gpr"].copy()
    rho, p_value = spearmanr(gpr_wafers["mean_predicted_std"], gpr_wafers["mae"])
    selection_count = max(1, int(np.ceil(0.20 * len(gpr_wafers))))
    high_error = set(gpr_wafers.nlargest(selection_count, "mae")["experiment_key"])
    high_uncertainty = set(
        gpr_wafers.nlargest(selection_count, "mean_predicted_std")["experiment_key"]
    )
    gpr_points = point_predictions[
        (point_predictions["family"] == "gpr")
        & (point_predictions["stage"] == "full_map")
    ].copy()
    raw_95_coverage = float(
        (gpr_points["error"].abs() <= 1.96 * gpr_points["predicted_std"]).mean()
    )
    pls_mae = float(model_summary.loc[model_summary["family"] == "pls", "wafer_macro_mae"].iloc[0])
    gpr_mae = float(model_summary.loc[model_summary["family"] == "gpr", "wafer_macro_mae"].iloc[0])
    audit = {
        "primary_model": "pls",
        "gpr_relative_mae_change_vs_pls": gpr_mae / pls_mae - 1,
        "gpr_relative_mae_change_lot_bootstrap_95_interval": np.quantile(
            bootstrap_difference, [0.025, 0.975]
        ).tolist(),
        "pls_lot_wins_over_gpr": int((lot_wide["pls"] < lot_wide["gpr"]).sum()),
        "total_lots": int(len(lot_wide)),
        "gpr_uncertainty_wafer_mae_spearman_rho": float(rho),
        "gpr_uncertainty_wafer_mae_spearman_p": float(p_value),
        "gpr_top_20_percent_error_capture": len(high_error & high_uncertainty)
        / len(high_error),
        "gpr_raw_pointwise_95_interval_coverage": raw_95_coverage,
        "gpr_mean_pointwise_standard_deviation_um": float(
            gpr_points["predicted_std"].mean()
        ),
        "uncertainty_claim": "uncalibrated proxy; rejected for metrology routing",
        "bootstrap_replicates": bootstrap_replicates,
        "random_seed": random_seed,
    }
    return model_summary, lot_metrics, audit

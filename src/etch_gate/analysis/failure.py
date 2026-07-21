"""Failure decomposition for held-out process-model lots."""

from __future__ import annotations

import numpy as np
import pandas as pd


def summarize_lot_failure(
    point_results: pd.DataFrame,
    *,
    family: str,
    lot_number: int,
) -> pd.DataFrame:
    """Return wafer-level mean-shift and stage-error diagnostics for one lot."""

    selected = point_results[
        (point_results["family"] == family)
        & (point_results["lot_number"] == lot_number)
    ]
    required_stages = {"template", "mean_shift", "full_map"}
    if set(selected["stage"]) != required_stages:
        raise ValueError("point results do not contain all required stages")

    rows = []
    for key, wafer in selected.groupby("experiment_key", sort=True):
        stages = {
            stage: wafer[wafer["stage"] == stage] for stage in required_stages
        }
        template = stages["template"]
        mean_shift = stages["mean_shift"]
        full_map = stages["full_map"]
        rows.append(
            {
                "experiment_key": key,
                "wafer_order": int(key.rsplit("_", maxsplit=1)[1]),
                "observed_mean": float(full_map["observed"].mean()),
                "template_mean": float(template["predicted"].mean()),
                "true_mean_shift": float(
                    full_map["observed"].mean() - template["predicted"].mean()
                ),
                "predicted_mean_shift": float(
                    mean_shift["predicted"].mean()
                    - template["predicted"].mean()
                ),
                "template_mae": float(template["error"].abs().mean()),
                "mean_shift_mae": float(mean_shift["error"].abs().mean()),
                "full_map_mae": float(full_map["error"].abs().mean()),
            }
        )
    result = pd.DataFrame(rows).sort_values("wafer_order").reset_index(drop=True)
    result["mean_shift_error"] = (
        result["predicted_mean_shift"] - result["true_mean_shift"]
    )
    result["residual_shape_mae_gain"] = (
        result["mean_shift_mae"] - result["full_map_mae"]
    )
    return result


def lot_feature_z_scores(
    feature_table: pd.DataFrame,
    lot_keys: list[str],
    *,
    top_count: int = 12,
) -> pd.DataFrame:
    """Rank one lot's features against means and scales from all other lots."""

    training = feature_table.drop(index=lot_keys)
    scales = training.std(ddof=0).replace(0.0, np.nan)
    z_scores = (feature_table.loc[lot_keys] - training.mean()) / scales
    ranking = z_scores.abs().max(axis=0).sort_values(ascending=False)
    return z_scores.loc[:, ranking.head(top_count).index]

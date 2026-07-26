"""Controlled process-only versus process-plus-OES pilot evaluation."""

from __future__ import annotations

import pandas as pd

from etch_gate.analysis.process_baseline import evaluate_process_baselines


def evaluate_oes_pilot(
    process_features: pd.DataFrame,
    oes_features: pd.DataFrame,
    dense: pd.DataFrame,
    *,
    selected_lots: tuple[int, ...],
    pls_parameters: tuple[float, ...] = (1.0, 2.0, 4.0),
    residual_variance_target: float = 0.90,
    maximum_residual_components: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Compare frozen process-only PLS with the same PLS plus OES features."""

    selected_dense = dense[dense["lot_number"].isin(selected_lots)].copy()
    selected_keys = sorted(selected_dense["experiment_key"].unique())
    missing_process = sorted(set(selected_keys) - set(process_features.index))
    missing_oes = sorted(set(selected_keys) - set(oes_features.index))
    if missing_process or missing_oes:
        raise ValueError(
            "selected dense wafer is missing features: "
            f"process={missing_process}, oes={missing_oes}"
        )

    process_selected = process_features.loc[selected_keys].copy()
    combined = pd.concat(
        [process_selected, oes_features.loc[selected_keys].add_prefix("oes__")],
        axis=1,
    )
    evaluations = []
    for family, features in [
        ("process_only_pls", process_selected),
        ("process_oes_pls", combined),
    ]:
        points, wafers, folds = evaluate_process_baselines(
            features,
            selected_dense,
            families=("pls",),
            pls_parameters=pls_parameters,
            residual_variance_target=residual_variance_target,
            maximum_residual_components=maximum_residual_components,
        )
        for table in (points, wafers, folds):
            table["family"] = family
        evaluations.append((points, wafers, folds))

    points = pd.concat([entry[0] for entry in evaluations], ignore_index=True)
    wafers = pd.concat([entry[1] for entry in evaluations], ignore_index=True)
    folds = pd.concat([entry[2] for entry in evaluations], ignore_index=True)
    full = wafers[wafers["stage"] == "full_map"]
    lot_metrics = full.groupby(["family", "lot_number"])["mae"].mean().unstack("family")
    process_wafer_mae = float(
        full[full["family"] == "process_only_pls"]["mae"].mean()
    )
    process_oes_wafer_mae = float(
        full[full["family"] == "process_oes_pls"]["mae"].mean()
    )
    process_lot_macro_mae = float(lot_metrics["process_only_pls"].mean())
    process_oes_lot_macro_mae = float(lot_metrics["process_oes_pls"].mean())
    relative_reduction = 1 - process_oes_lot_macro_mae / process_lot_macro_mae
    lots_improved = int(
        (lot_metrics["process_oes_pls"] < lot_metrics["process_only_pls"]).sum()
    )
    summary = {
        "selected_lots": list(selected_lots),
        "dense_wafers": len(selected_keys),
        "process_features": int(process_selected.shape[1]),
        "oes_features": int(oes_features.shape[1]),
        "combined_features": int(combined.shape[1]),
        "process_only_wafer_macro_mae": process_wafer_mae,
        "process_oes_wafer_macro_mae": process_oes_wafer_mae,
        "process_only_lot_macro_mae": process_lot_macro_mae,
        "process_oes_lot_macro_mae": process_oes_lot_macro_mae,
        "lot_macro_relative_mae_reduction": relative_reduction,
        "lots_improved": lots_improved,
        "total_lots": len(lot_metrics),
    }
    return points, wafers, folds, summary

"""Run the fixed physics-constrained OES V2 pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from etch_gate.analysis.oes_v2 import evaluate_physics_constrained_oes_v2
from etch_gate.analysis.process_baseline import evaluate_process_baselines
from etch_gate.data.process import build_process_feature_table, load_process_traces


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--oes-features", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    traces = load_process_traces(
        args.data_dir / "Process_data.nc", args.data_dir / "Dictionary_process.nc"
    )
    process_features, _ = build_process_feature_table(traces)
    oes_features = pd.read_csv(args.oes_features, index_col="experiment_key")
    dense = pd.read_csv(args.data_dir / "Si_Oxide_etch_89_points.csv")
    selected_dense = dense[dense["lot_number"].isin(config["selected_lots"])]
    baseline_points, baseline_wafers, baseline_folds = evaluate_process_baselines(
        process_features,
        selected_dense,
        families=("pls",),
    )
    for table in (baseline_points, baseline_wafers, baseline_folds):
        table["family"] = "process_only_pls"
    v2_points, v2_wafers, v2_folds, summary = evaluate_physics_constrained_oes_v2(
        process_features,
        oes_features,
        dense,
        selected_lots=tuple(config["selected_lots"]),
        oes_components=tuple(config["oes_preprocessing"]["candidate_latent_components"]),
        ridge_alphas=tuple(config["mean_shift_model"]["candidate_alpha"]),
    )
    points = pd.concat([baseline_points, v2_points], ignore_index=True)
    wafers = pd.concat([baseline_wafers, v2_wafers], ignore_index=True)
    folds = pd.concat([baseline_folds, v2_folds], ignore_index=True)
    full = wafers[wafers["stage"] == "full_map"]
    lot = full.groupby(["lot_number", "family"])["mae"].mean().unstack("family")
    baseline_mae = float(lot["process_only_pls"].mean())
    v2_mae = float(lot["physics_constrained_oes_v2"].mean())
    summary.update(
        {
            "process_only_lot_macro_mae": baseline_mae,
            "physics_constrained_lot_macro_mae": v2_mae,
            "lot_macro_relative_mae_reduction": 1 - v2_mae / baseline_mae,
            "lots_improved": int(
                (lot["physics_constrained_oes_v2"] < lot["process_only_pls"]).sum()
            ),
            "total_lots": len(lot),
            "retain_gate": config["retain_gate"],
        }
    )
    gate = config["retain_gate"]
    summary["passes_retain_gate"] = bool(
        summary["lot_macro_relative_mae_reduction"] >= gate["relative_mae_reduction_minimum"]
        and summary["lots_improved"] >= gate["lots_improved_minimum"]
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    points.to_csv(args.output_dir / "point_predictions.csv", index=False)
    wafers.to_csv(args.output_dir / "wafer_metrics.csv", index=False)
    folds.to_csv(args.output_dir / "fold_diagnostics.csv", index=False)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

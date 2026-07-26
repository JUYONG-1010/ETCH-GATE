"""Run the preregistered four-lot OES incremental-value pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from etch_gate.analysis.oes_pilot import evaluate_oes_pilot
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
        args.data_dir / "Process_data.nc",
        args.data_dir / "Dictionary_process.nc",
    )
    process_features, _ = build_process_feature_table(traces)
    oes_features = pd.read_csv(args.oes_features, index_col="experiment_key")
    dense = pd.read_csv(args.data_dir / "Si_Oxide_etch_89_points.csv")
    points, wafers, folds, summary = evaluate_oes_pilot(
        process_features,
        oes_features,
        dense,
        selected_lots=tuple(config["selected_lots"]),
        pls_parameters=tuple(config.get("pls_parameters", [1, 2, 4])),
        residual_variance_target=config.get("residual_variance_target", 0.90),
        maximum_residual_components=config.get("maximum_residual_components", 8),
    )
    gate = config["retain_gate"]
    summary["retain_gate"] = gate
    summary["passes_retain_gate"] = bool(
        summary["lot_macro_relative_mae_reduction"]
        >= gate["relative_mae_reduction_minimum"]
        and summary["lots_improved"] >= gate["lots_improved_minimum"]
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    points.to_csv(args.output_dir / "point_predictions.csv", index=False)
    wafers.to_csv(args.output_dir / "wafer_metrics.csv", index=False)
    folds.to_csv(args.output_dir / "fold_diagnostics.csv", index=False)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

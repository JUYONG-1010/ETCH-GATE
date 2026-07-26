"""Run detailed deployable/oracle spatial target decomposition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from etch_gate.analysis.spatial_decomposition import evaluate_spatial_decomposition
from etch_gate.data.process import build_process_feature_table, load_process_traces
from etch_gate.visualization.spatial_decomposition import plot_spatial_decomposition


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--figure-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    traces = load_process_traces(
        args.data_dir / "Process_data.nc",
        args.data_dir / "Dictionary_process.nc",
    )
    features, _ = build_process_feature_table(
        traces, detector=config["cycle_detector"]
    )
    dense = pd.read_csv(args.data_dir / "Si_Oxide_etch_89_points.csv")
    result = evaluate_spatial_decomposition(
        features,
        dense,
        pls_parameters=tuple(config["pls_parameters"]),
        residual_variance_target=config["residual_variance_target"],
        maximum_residual_components=config["maximum_residual_components"],
        bootstrap_replicates=config["bootstrap_replicates"],
        random_seed=config["random_seed"],
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result.point_predictions.to_csv(
        args.output_dir / "point_predictions.csv", index=False
    )
    result.wafer_metrics.to_csv(args.output_dir / "wafer_metrics.csv", index=False)
    result.coordinate_metrics.to_csv(
        args.output_dir / "coordinate_metrics.csv", index=False
    )
    result.stage_summary.to_csv(args.output_dir / "stage_summary.csv", index=False)
    (args.output_dir / "summary.json").write_text(
        json.dumps(
            {
                "analysis": "mean_shift_residual_oracle_decomposition",
                "configuration": config,
                "residual_contribution_gate": result.gate,
                "claim_boundaries": [
                    "oracle stages are non-deployable upper bounds",
                    "spatial contribution follows the frozen gate",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    plot_spatial_decomposition(
        result.point_predictions,
        result.wafer_metrics,
        result.stage_summary,
        result.gate,
        args.figure_dir / "spatial-decomposition-dashboard.png",
    )
    summary = result.stage_summary.set_index("stage")
    interval = result.gate["lot_cluster_bootstrap_95_interval"]
    oracle_mean = summary.loc[
        "oracle_true_mean_zero_residual", "lot_macro_mae"
    ]
    oracle_pca = summary.loc[
        "oracle_true_mean_pca_reconstruction", "lot_macro_mae"
    ]
    args.report.write_text(
        f"""# Mean-Shift and Spatial-Residual Decomposition

## Deployable stages

- Training-lot coordinate template MAE: {summary.loc["template", "lot_macro_mae"]:.4f} um
- Template + predicted mean shift: {summary.loc["mean_shift", "lot_macro_mae"]:.4f} um
- Template + predicted mean + predicted residual: {summary.loc["full_map", "lot_macro_mae"]:.4f} um

## Oracle diagnostics

- True mean shift + zero residual: {oracle_mean:.4f} um
- True mean shift + training-PCA residual reconstruction: {oracle_pca:.4f} um

Oracle rows use test targets and are upper-bound diagnostics, not deployable
models.

## Residual contribution gate

- Status: **{result.gate["status"]}**
- Relative residual-stage gain: {result.gate["relative_residual_stage_gain"]:.2%}
- Lot-cluster bootstrap 95% interval: [{interval[0]:.2%}, {interval[1]:.2%}]
- Lots improved: {result.gate["lots_improved"]}/{result.gate["total_lots"]}

Zones are defined deterministically by normalized wafer radius: center <= 1/3,
middle <= 2/3, and edge > 2/3. Per-wafer zone, range, standard-deviation,
worst-point, p95-point, and mean-centered spatial errors are stored in
`wafer_metrics.csv`.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

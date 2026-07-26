"""Run nested LOLO and strict expanding-window VM evaluations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from etch_gate.analysis.chronological import evaluate_chronological_vm
from etch_gate.analysis.process_baseline import GPRSettings
from etch_gate.data.process import build_process_feature_table, load_process_traces
from etch_gate.visualization.chronological import plot_lolo_vs_forward_dashboard


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
    result = evaluate_chronological_vm(
        features,
        dense,
        families=tuple(config["families"]),
        minimum_training_lots=config["minimum_training_lots"],
        ridge_parameters=tuple(config["ridge_parameters"]),
        pls_parameters=tuple(config["pls_parameters"]),
        gpr_parameters=tuple(
            GPRSettings(**parameters) for parameters in config["gpr_parameters"]
        ),
        residual_variance_target=config["residual_variance_target"],
        maximum_residual_components=config["maximum_residual_components"],
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result.fold_diagnostics.to_csv(
        args.output_dir / "fold_diagnostics.csv", index=False
    )
    result.wafer_metrics.to_csv(args.output_dir / "wafer_metrics.csv", index=False)
    result.point_predictions.to_csv(
        args.output_dir / "point_predictions.csv", index=False
    )
    result.comparison.to_csv(args.output_dir / "comparison.csv", index=False)
    macro = result.comparison[result.comparison["scope"] == "macro"].copy()
    summary = {
        "analysis": "nested_lolo_vs_expanding_window_vm",
        "configuration": config,
        "eligible_test_lots": sorted(
            result.wafer_metrics["lot_number"].unique().tolist()
        ),
        "family_macro_comparison": macro.to_dict(orient="records"),
        "claim_boundaries": [
            "LOLO evaluates domain generalization",
            "expanding-window evaluates strict forward deployment",
            "neither establishes production suitability",
        ],
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    plot_lolo_vs_forward_dashboard(
        result.comparison,
        result.point_predictions,
        result.wafer_metrics,
        args.figure_dir / "lolo-vs-forward-dashboard.png",
    )
    lines = [
        "# Chronological Virtual-Metrology Results",
        "",
        "Every forward fold fits filtering, scaling, template, residual PCA,",
        "hyperparameter selection, and regression using earlier lots only.",
        "",
        "| Model | Eligible-lot LOLO MAE | Forward MAE | Relative degradation |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in macro.itertuples(index=False):
        lines.append(
            f"| {row.family.upper()} | {row.lolo_mae:.4f} | "
            f"{row.chronological_mae:.4f} | {row.relative_degradation:.2%} |"
        )
    lines.extend(
        [
            "",
            "LOLO tests whether a complete lot can be generalized from the other",
            "lots, including chronologically later ones. The forward evaluation tests",
            "the harder condition in which future process regimes do not exist at fit",
            "time. A degradation is therefore reported as temporal-regime sensitivity,",
            "not hidden by the domain-generalization average.",
        ]
    )
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

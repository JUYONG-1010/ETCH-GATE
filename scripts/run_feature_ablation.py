"""Run cumulative process-feature ablation and stability analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from etch_gate.analysis.feature_ablation import evaluate_feature_ablation
from etch_gate.data.process import build_process_feature_table, load_process_traces
from etch_gate.visualization.feature_ablation import (
    plot_ablation_dashboard,
    plot_feature_stability,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--figure-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def _markdown_table(frame: pd.DataFrame) -> str:
    lines = [
        "| " + " | ".join(map(str, frame.columns)) + " |",
        "| " + " | ".join(["---"] * len(frame.columns)) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        values = [
            f"{value:.4f}" if isinstance(value, float) else str(value) for value in row
        ]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


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
    result = evaluate_feature_ablation(
        features,
        dense,
        pls_parameters=tuple(config["pls_parameters"]),
        ridge_parameters=tuple(config["ridge_parameters"]),
        residual_variance_target=config["residual_variance_target"],
        maximum_residual_components=config["maximum_residual_components"],
        include_sensor_family_ablation=config["include_sensor_family_ablation"],
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result.summary.to_csv(args.output_dir / "ablation_summary.csv", index=False)
    result.fold_metrics.to_csv(args.output_dir / "fold_metrics.csv", index=False)
    result.feature_stability.to_csv(
        args.output_dir / "feature_stability.csv", index=False
    )
    cumulative = result.summary[
        ~result.summary["ablation"].str.startswith("family_only")
    ].copy()
    level = cumulative.iloc[0]
    full = cumulative.iloc[-1]
    phase_gain = 1 - cumulative.iloc[2]["lot_macro_full_map_mae"] / cumulative.iloc[1][
        "lot_macro_full_map_mae"
    ]
    cycle_gain = 1 - full["lot_macro_full_map_mae"] / cumulative.iloc[2][
        "lot_macro_full_map_mae"
    ]
    manifest = {
        "analysis": "nested_lolo_process_feature_ablation",
        "configuration": config,
        "level_only_lot_macro_mae": level["lot_macro_full_map_mae"],
        "all_features_lot_macro_mae": full["lot_macro_full_map_mae"],
        "phase_incremental_gain": phase_gain,
        "cycle_incremental_gain": cycle_gain,
        "pass_fail_gate": "DESCRIPTIVE",
        "claim_boundaries": [
            "released channel labels only",
            "no hidden gas chemistry assigned",
            "association is not process causality",
        ],
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    plot_ablation_dashboard(
        result.summary,
        result.feature_stability,
        dense,
        args.figure_dir / "ablation-dashboard.png",
    )
    plot_feature_stability(
        result.feature_stability,
        args.figure_dir / "feature-stability.png",
    )
    report_table = cumulative[
        [
            "ablation",
            "retained_feature_count",
            "lot_macro_full_map_mae",
            "wafer_mean_shift_mae",
            "residual_profile_mae",
            "worst_lot_mae",
            "lots_improved_over_previous",
        ]
    ]
    args.report.write_text(
        f"""# Process Feature Ablation Results

All rows use the same nested leave-one-lot-out PLS evaluation. Only the
declared feature group changes.

{_markdown_table(report_table)}

## Incremental findings

- Level-only lot-macro MAE: {level["lot_macro_full_map_mae"]:.4f} um
- All-feature lot-macro MAE: {full["lot_macro_full_map_mae"]:.4f} um
- Phase-group incremental gain: {phase_gain:.2%}
- Cycle-group incremental gain: {cycle_gain:.2%}

The family-only comparison is an over-dependence audit, not a claim that the
released anonymous/partial channel names identify a causal chamber mechanism.
PLS VIP is computed inside each outer-training fold from the standard weighted
sum of response variance represented by each latent component. Coefficient
signs and ranks are reported per fold rather than averaged before inspection.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

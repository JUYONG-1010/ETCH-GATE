"""Run ETCH-GATE Milestone 4 drift and failure-risk evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from etch_gate.analysis.drift import evaluate_drift_risk
from etch_gate.visualization.drift import (
    plot_failure_risk_dashboard,
    plot_risk_robustness_dashboard,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--figure-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    features = pd.read_csv(
        args.baseline_dir / "process_features.csv", index_col="experiment_key"
    )
    folds = pd.read_csv(args.baseline_dir / "fold_diagnostics.csv")
    dense = pd.read_csv(args.data_dir / "Si_Oxide_etch_89_points.csv")
    result = evaluate_drift_risk(
        features,
        dense,
        folds,
        pca_components=config["pca_components"],
        ewma_alpha=config["ewma_alpha"],
        budgets=tuple(config["budgets"]),
        random_replicates=config["random_replicates"],
        random_seed=config["random_seed"],
        redundancy_threshold=config["ood_initial_redundancy_threshold"],
        bootstrap_replicates=config["lot_cluster_bootstrap_replicates"],
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result.wafer_scores.to_csv(args.output_dir / "wafer_risk_scores.csv", index=False)
    result.risk_curves.to_csv(args.output_dir / "risk_curves.csv", index=False)
    result.lot_summary.to_csv(args.output_dir / "lot_policy_summary.csv", index=False)
    result.score_correlations.to_csv(
        args.output_dir / "score_correlations.csv", index=False
    )
    result.alpha_sensitivity.to_csv(
        args.output_dir / "ewma_alpha_sensitivity.csv", index=False
    )
    result.influence_summary.to_csv(
        args.output_dir / "lot_influence_summary.csv", index=False
    )
    result.bootstrap_summary.to_csv(
        args.output_dir / "bootstrap_summary.csv", index=False
    )
    result.small_lot_resolution.to_csv(
        args.output_dir / "small_lot_resolution.csv", index=False
    )
    result.weight_selection.to_csv(
        args.output_dir / "training_weight_selection.csv", index=False
    )

    macro = result.lot_summary.groupby("policy")["aurc"].mean()
    random_aurc = float(macro["random"])
    combined_reduction = float(1 - macro["combined"] / random_aurc)
    paired = result.lot_summary.pivot(index="lot_number", columns="policy", values="aurc")
    improved_lots = int((paired["combined"] < paired["random"]).sum())
    passed = (
        combined_reduction >= config["minimum_aurc_reduction"]
        and improved_lots >= config["minimum_improved_lots"]
    )
    manifest = {
        "milestone": config["milestone"],
        "analysis": "target_free_drift_and_failure_risk",
        "configuration": config,
        "lot_macro_aurc": {key: float(value) for key, value in macro.items()},
        "combined_vs_random_aurc_reduction": combined_reduction,
        "combined_improved_lots": improved_lots,
        "total_lots": int(paired.shape[0]),
        "preregistered_gate_passed": passed,
        "first_wafer_rule": config["first_wafer_rule"],
        "ewma_alpha_selection": {
            "selected": config["ewma_alpha"],
            "selection_basis": "preregistered_before_test_scoring",
            "sensitivity_only": config["ewma_sensitivity_alphas"],
        },
        "claim_boundary": {
            "risk_score_is_calibrated_uncertainty": False,
            "ewma_is_a_production_ooc_limit": False,
            "held_out_target_used_to_construct_risk": False,
            "test_target_used_only_for_retrospective_scoring": True,
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    plot_failure_risk_dashboard(
        result.wafer_scores,
        result.risk_curves,
        result.lot_summary,
        args.figure_dir / "failure-risk-dashboard.png",
        minimum_reduction=config["minimum_aurc_reduction"],
        minimum_lots=config["minimum_improved_lots"],
    )
    plot_risk_robustness_dashboard(
        result.wafer_scores,
        result.influence_summary,
        result.bootstrap_summary,
        result.score_correlations,
        dense,
        args.figure_dir / "risk-robustness-dashboard.png",
    )


if __name__ == "__main__":
    main()

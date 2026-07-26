"""Run chronological selective-metrology replay from raw released inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from etch_gate.analysis.causal_replay import evaluate_causal_replay
from etch_gate.data.process import build_process_feature_table, load_process_traces
from etch_gate.visualization.causal_replay import (
    plot_causal_replay_dashboard,
    plot_cumulative_error_timeline,
)


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
        traces,
        detector=config["cycle_detector"],
    )
    dense = pd.read_csv(args.data_dir / "Si_Oxide_etch_89_points.csv")
    result = evaluate_causal_replay(
        features,
        dense,
        minimum_training_lots=config["minimum_training_lots"],
        budgets=tuple(config["budgets"]),
        pls_parameters=tuple(config["pls_parameters"]),
        ridge_parameters=tuple(config["ridge_parameters"]),
        residual_variance_target=config["residual_variance_target"],
        maximum_residual_components=config["maximum_residual_components"],
        risk_pca_components=config["risk_pca_components"],
        ewma_alpha=config["ewma_alpha"],
        bias_alpha=config["bias_update_alpha"],
        redundancy_threshold=config["ood_initial_redundancy_threshold"],
        random_replicates=config["random_replicates"],
        bootstrap_replicates=config["lot_cluster_bootstrap_replicates"],
        random_seed=config["random_seed"],
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result.wafer_timeline.to_csv(
        args.output_dir / "wafer_timeline.csv",
        index=False,
    )
    result.policy_budget_summary.to_csv(
        args.output_dir / "policy_budget_summary.csv",
        index=False,
    )
    result.lot_summary.to_csv(args.output_dir / "lot_summary.csv", index=False)
    result.bootstrap_summary.to_csv(
        args.output_dir / "bootstrap_summary.csv",
        index=False,
    )

    direct = result.policy_budget_summary[
        (result.policy_budget_summary["mode"] == "direct_substitution")
        & (result.policy_budget_summary["feedback"] == "F0")
    ]
    pivot = direct.pivot(
        index="budget",
        columns="policy",
        values="lot_macro_system_mae",
    )
    improvements = {
        f"{budget:g}": float(1 - pivot.loc[budget, "combined"] / pivot.loc[budget, "random"])
        for budget in (0.1, 0.2, 0.3)
    }
    direct_lots = result.lot_summary[
        (result.lot_summary["mode"] == "direct_substitution")
        & (result.lot_summary["feedback"] == "F0")
        & (result.lot_summary["policy"].isin(["combined", "random"]))
        & (result.lot_summary["budget"].isin([0.1, 0.2, 0.3]))
    ]
    lot_pivot = direct_lots.pivot(
        index=["test_lot", "budget"],
        columns="policy",
        values="total_system_mae",
    ).reset_index()
    lot_win_fraction = {
        f"{budget:g}": float(
            (
                lot_pivot.loc[lot_pivot["budget"] == budget, "combined"]
                <= lot_pivot.loc[lot_pivot["budget"] == budget, "random"]
            ).mean()
        )
        for budget in (0.1, 0.2, 0.3)
    }
    without_lot8 = {
        f"{budget:g}": float(
            (
                lot_pivot[
                    (lot_pivot["budget"] == budget)
                    & (lot_pivot["test_lot"] != 8)
                ]["random"]
                - lot_pivot[
                    (lot_pivot["budget"] == budget)
                    & (lot_pivot["test_lot"] != 8)
                ]["combined"]
            ).mean()
        )
        for budget in (0.1, 0.2, 0.3)
    }
    worst_lot_relative_change = {
        f"{budget:g}": float(
            direct.loc[
                (direct["budget"] == budget)
                & (direct["policy"] == "combined"),
                "worst_lot_mae",
            ].iloc[0]
            / direct.loc[
                (direct["budget"] == budget)
                & (direct["policy"] == "random"),
                "worst_lot_mae",
            ].iloc[0]
            - 1
        )
        for budget in (0.1, 0.2, 0.3)
    }
    feedback = result.policy_budget_summary[
        (result.policy_budget_summary["mode"] == "causal_feedback")
        & (result.policy_budget_summary["policy"] == "combined")
    ]
    feedback_pivot = feedback.pivot(
        index="budget",
        columns="feedback",
        values="lot_macro_system_mae",
    )
    feedback_gain = {
        mode: float(
            (
                1
                - feedback_pivot[mode]
                / feedback_pivot["F0"]
            )
            .replace([float("inf"), -float("inf")], float("nan"))
            .mean()
        )
        for mode in ("F1", "F2", "F3")
    }
    low_budget_bootstrap = result.bootstrap_summary[
        result.bootstrap_summary["budget"].isin([0.1, 0.2, 0.3])
    ]
    gate_checks = {
        "at_least_two_low_budgets_improve_random": (
            sum(value > 0 for value in improvements.values()) >= 2
        ),
        "bootstrap_improvement_interval_not_cross_zero": bool(
            (low_budget_bootstrap["bootstrap_p975"] < 0).sum() >= 2
        ),
        "at_least_70_percent_lots_equal_or_better": (
            max(lot_win_fraction.values()) >= 0.70
        ),
        "lot8_excluded_direction_remains_better": (
            sum(value > 0 for value in without_lot8.values()) >= 2
        ),
        "worst_lot_not_degraded_more_than_10_percent": (
            max(worst_lot_relative_change.values()) <= 0.10
        ),
    }
    manifest = {
        "analysis": "strict_chronological_causal_selective_metrology",
        "configuration": config,
        "combined_vs_random_system_mae_reduction": improvements,
        "feedback_mean_relative_gain_vs_frozen": feedback_gain,
        "combined_lot_win_fraction": lot_win_fraction,
        "random_minus_combined_mae_without_lot8": without_lot8,
        "worst_lot_relative_change": worst_lot_relative_change,
        "policy_gate_checks": gate_checks,
        "policy_gate": "PASS" if all(gate_checks.values()) else "FAIL",
        "validated_combined_definition": (
            "equal-weight combined; training-weight candidate was rejected "
            "by the separate risk audit"
        ),
        "claim_boundaries": [
            "direct measurement is treated as error-free substitution",
            "oracle uses target and is not deployable",
            "released lot size is known to the quota controller",
            "future process scores and future metrology targets are not ranked",
        ],
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    plot_causal_replay_dashboard(
        result.wafer_timeline,
        result.policy_budget_summary,
        result.bootstrap_summary,
        dense,
        args.figure_dir / "causal-replay-dashboard.png",
    )
    plot_cumulative_error_timeline(
        result.wafer_timeline,
        result.lot_summary,
        dense,
        args.figure_dir / "cumulative-error-timeline.png",
    )

    lines = [
        "# Causal Selective-Metrology Results",
        "",
        "This replay processes Lots 4-10 in order. Each decision uses earlier lots,",
        "the current process trace, and only previously selected direct measurements.",
        "It never sorts future test-lot risk scores.",
        "",
        "## Direct-result substitution",
        "",
        "| Budget | Combined MAE reduction vs Random |",
        "| ---: | ---: |",
    ]
    for budget, reduction in improvements.items():
        lines.append(f"| {float(budget):.0%} | {reduction:.2%} |")
    lines.extend(
        [
            "",
            "## Feedback update",
            "",
            "| Update | Mean relative gain vs frozen F0 |",
            "| --- | ---: |",
        ]
    )
    for mode, gain in feedback_gain.items():
        lines.append(f"| {mode} | {gain:.2%} |")
    lines.extend(
        [
            "",
            "F0 is frozen VM. F1 updates one scalar mean bias. F2 refits only the",
            "mean-shift PLS model with measured wafers. F3 also refits the residual",
            "shape-score model while keeping preprocessing, template, PCA basis, and",
            "hyperparameters fixed from past lots.",
            "",
            "## Policy gate",
            "",
            f"Overall gate: **{'PASS' if all(gate_checks.values()) else 'FAIL'}**",
            "",
            "| Check | Result |",
            "| --- | --- |",
        ]
    )
    for check, passed in gate_checks.items():
        lines.append(f"| {check.replace('_', ' ')} | {'PASS' if passed else 'FAIL'} |")
    lines.extend(
        [
            "",
            "A failed gate means the online adaptive policy is not retained as a",
            "headline contribution. Static ranking evidence remains a separate result.",
        ]
    )
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

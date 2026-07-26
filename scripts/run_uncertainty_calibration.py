"""Run strictly ordered group-aware conformal uncertainty evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from etch_gate.analysis.uncertainty_calibration import (
    evaluate_conformal_uncertainty,
)
from etch_gate.data.process import build_process_feature_table, load_process_traces
from etch_gate.visualization.uncertainty_calibration import (
    plot_coverage_width_dashboard,
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
    result = evaluate_conformal_uncertainty(
        features,
        dense,
        nominal_coverages=tuple(config["nominal_coverages"]),
        minimum_fit_lots=config["minimum_fit_lots"],
        pls_parameters=tuple(config["pls_parameters"]),
        residual_variance_target=config["residual_variance_target"],
        maximum_residual_components=config["maximum_residual_components"],
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result.coverage_summary.to_csv(
        args.output_dir / "coverage_summary.csv",
        index=False,
    )
    result.lot_coverage.to_csv(args.output_dir / "lot_coverage.csv", index=False)
    result.point_diagnostics.to_csv(
        args.output_dir / "point_diagnostics.csv",
        index=False,
    )

    lots = result.lot_coverage.copy()
    lots["point_within_tolerance"] = (
        lots["point_empirical_coverage"]
        >= lots["nominal_coverage"] - config["maximum_coverage_shortfall"]
    )
    lots["map_within_tolerance"] = (
        lots["simultaneous_map_coverage"]
        >= lots["nominal_coverage"] - config["maximum_coverage_shortfall"]
    )
    stable_fraction = (
        lots.assign(
            stable=lots["point_within_tolerance"]
            & lots["map_within_tolerance"]
        )
        .groupby("nominal_coverage")["stable"]
        .mean()
    )
    checks = {
        "coverage_within_tolerance": bool(
            (
                result.coverage_summary["point_empirical_coverage"]
                >= result.coverage_summary["nominal_coverage"]
                - config["maximum_coverage_shortfall"]
            ).all()
            and (
                result.coverage_summary["simultaneous_map_coverage"]
                >= result.coverage_summary["nominal_coverage"]
                - config["maximum_coverage_shortfall"]
            ).all()
        ),
        "half_width_below_template_baseline_mae": bool(
            (
                result.coverage_summary["mean_point_half_width_vs_template_mae"]
                <= config["maximum_half_width_to_template_mae"]
            ).all()
        ),
        "stable_across_lots": bool(
            (stable_fraction >= config["minimum_stable_lot_fraction"]).all()
        ),
        "requested_levels_attainable": bool(
            (
                result.coverage_summary["attainable_lot_fraction"]
                == 1
            ).all()
        ),
    }
    manifest = {
        "analysis": "strict_group_aware_split_conformal",
        "configuration": config,
        "gate_checks": checks,
        "gate": "PASS" if all(checks.values()) else "FAIL",
        "claim_boundary": (
            "Intervals are not used for risk routing when this gate fails."
        ),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    plot_coverage_width_dashboard(
        result.coverage_summary,
        result.lot_coverage,
        result.point_diagnostics,
        args.figure_dir / "coverage-width-dashboard.png",
    )

    lines = [
        "# Uncertainty Calibration Results",
        "",
        "For each outer test lot, the immediately preceding lot is calibration-only",
        "and all earlier lots fit the VM. Test targets never determine interval width.",
        "",
        "| Nominal | Point coverage | Simultaneous map coverage | "
        "Point width (um) | Map width (um) | Attainable lots |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in result.coverage_summary.itertuples(index=False):
        lines.append(
            f"| {row.nominal_coverage:.0%} | "
            f"{row.point_empirical_coverage:.2%} | "
            f"{row.simultaneous_map_coverage:.2%} | "
            f"{row.mean_point_interval_width:.4f} | "
            f"{row.mean_simultaneous_interval_width:.4f} | "
            f"{row.attainable_lot_fraction:.0%} |"
        )
    lines.extend(
        [
            "",
            f"Overall gate: **{'PASS' if all(checks.values()) else 'FAIL'}**",
            "",
            "| Gate check | Result |",
            "| --- | --- |",
        ]
    )
    for check, passed in checks.items():
        lines.append(f"| {check.replace('_', ' ')} | {'PASS' if passed else 'FAIL'} |")
    lines.extend(
        [
            "",
            "A failed gate stops any claim that raw GPR variance or these conformal",
            "intervals are calibrated enough for selective-metrology routing.",
            "",
            "![Coverage-width dashboard](figures/uncertainty_calibration/"
            "coverage-width-dashboard.png)",
        ]
    )
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

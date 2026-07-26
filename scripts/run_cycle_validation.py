"""Validate BOSCH cycle detection on all actual process wafers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from etch_gate.analysis.cycle_validation import (
    deterministic_example_keys,
    validate_cycle_detection,
)
from etch_gate.data.process import load_process_traces
from etch_gate.visualization.cycle_validation import (
    plot_anomalous_cycle_examples,
    plot_cycle_count_by_lot,
    plot_phase_duration_distribution,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--figure-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def _lot_mapping(dense: pd.DataFrame, trace_keys: set[str]) -> dict[str, int]:
    wafer_lots = (
        dense[["experiment_key", "lot_number"]]
        .drop_duplicates()
        .set_index("experiment_key")["lot_number"]
        .astype(int)
        .to_dict()
    )
    date_lots: dict[str, int] = {}
    for key, lot in wafer_lots.items():
        date = str(key).rsplit("_", 1)[0]
        if date in date_lots and date_lots[date] != lot:
            raise ValueError(f"date {date} maps to multiple lots")
        date_lots[date] = lot
    result = {}
    for key in trace_keys:
        date = str(key).rsplit("_", 1)[0]
        if date not in date_lots:
            raise ValueError(f"no dense-wafer lot mapping for process date {date}")
        result[key] = date_lots[date]
    return result


def _report_text(
    result,
    config: dict[str, object],
) -> str:
    def markdown_table(frame: pd.DataFrame) -> str:
        headers = [str(column) for column in frame.columns]
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        for row in frame.itertuples(index=False, name=None):
            values = [
                f"{value:.4f}" if isinstance(value, float) else str(value)
                for value in row
            ]
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    wafer = result.wafer_diagnostics
    selected = result.selected_detector
    examples = deterministic_example_keys(wafer)
    outside = wafer.loc[
        ~wafer["detected_cycle_count"].between(
            config["accepted_cycle_count_minimum"],
            config["accepted_cycle_count_maximum"],
        ),
        "experiment_key",
    ].tolist()
    detector_table = markdown_table(
        result.detector_summary.drop(columns="detector_order")
    )
    lot_table = markdown_table(result.lot_summary)
    return f"""# BOSCH Cycle Validation Results

## Decision

All {len(wafer)} process wafers were evaluated without using stepheight or any
other post-etch target. The target-free detector selected by the fixed
lexicographic diagnostic rule is `{selected}`.

The rule minimizes, in order: wafers outside the declared 95-105 cycle band,
median absolute deviation from the documented 100-cycle process, phase overlap,
uncovered active samples, and finally detector complexity/order.

## Detector comparison

{detector_table}

## Selected-detector result

- Median detected cycles: {wafer["detected_cycle_count"].median():.1f}
- Minimum / maximum: {wafer["detected_cycle_count"].min()} / {wafer["detected_cycle_count"].max()}
- Wafers outside 95-105: {len(outside)}
- Phase-overlap samples: {int(wafer["phase_overlap_samples"].sum())}
- Uncovered active samples: {int(wafer["uncovered_active_samples"].sum())}
- Suspicious wafers under the complete fixed rule: {int(wafer["suspicious"].sum())}
- Outside-band wafer keys: {outside if outside else "none"}

## Lot summary

{lot_table}

## Deterministic visual examples

The examples were selected before plotting:

- Median cycle-count wafer: `{examples["median"]}`
- Minimum cycle-count wafer: `{examples["minimum"]}`
- Maximum cycle-count wafer: `{examples["maximum"]}`
- Largest robust phase-duration anomaly: `{examples["phase_anomaly"]}`

## Interpretation boundary

This validates segmentation consistency with the released process description.
It does not validate plasma chemistry, endpoint detection, etch mechanism, or
post-etch target accuracy. A cycle count near 100 is a process-trace integrity
check, not a model-performance metric.
"""


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    traces = load_process_traces(
        args.data_dir / "Process_data.nc",
        args.data_dir / "Dictionary_process.nc",
    )
    dense = pd.read_csv(args.data_dir / "Si_Oxide_etch_89_points.csv")
    lot_by_key = _lot_mapping(dense, set(traces))
    result = validate_cycle_detection(
        traces,
        lot_by_key,
        detectors=tuple(config["detectors"]),
        minimum_phase_duration_seconds=config["minimum_phase_duration_seconds"],
        expected_cycle_period_seconds=config["expected_cycle_period_seconds"],
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result.wafer_diagnostics.to_csv(
        args.output_dir / "wafer_cycle_diagnostics.csv", index=False
    )
    result.lot_summary.to_csv(args.output_dir / "lot_cycle_summary.csv", index=False)
    result.detector_summary.to_csv(
        args.output_dir / "detector_comparison.csv", index=False
    )
    (args.output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "analysis": "actual_wafer_cycle_validation",
                "configuration": config,
                "selected_detector": result.selected_detector,
                "process_wafers": len(result.wafer_diagnostics),
                "pass_fail_gate": (
                    "PASS"
                    if result.wafer_diagnostics["cycle_index_monotonic"].all()
                    else "FAIL"
                ),
                "claim_boundaries": [
                    "target-free process segmentation only",
                    "no plasma-chemistry or endpoint claim",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    plot_cycle_count_by_lot(
        result.wafer_diagnostics, args.figure_dir / "cycle-count-by-lot.png"
    )
    plot_phase_duration_distribution(
        result.wafer_diagnostics,
        args.figure_dir / "phase-duration-distribution.png",
    )
    plot_anomalous_cycle_examples(
        traces,
        result.wafer_diagnostics,
        result.selected_detector,
        args.figure_dir / "anomalous-cycle-examples.png",
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(_report_text(result, config), encoding="utf-8")


if __name__ == "__main__":
    main()

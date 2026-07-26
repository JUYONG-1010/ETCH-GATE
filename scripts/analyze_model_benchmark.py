"""Summarize and visualize the Ridge/PLS/GPR benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from etch_gate.analysis.model_benchmark import summarize_model_benchmark
from etch_gate.visualization.model_benchmark import plot_model_benchmark_dashboard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--figure-path", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    wafers = pd.read_csv(args.result_dir / "wafer_metrics.csv")
    points = pd.read_csv(args.result_dir / "point_predictions.csv")
    model_summary, lot_metrics, audit = summarize_model_benchmark(wafers, points)
    model_summary.to_csv(args.result_dir / "model_summary.csv", index=False)
    lot_metrics.to_csv(args.result_dir / "model_lot_metrics.csv", index=False)
    (args.result_dir / "model_benchmark_audit.json").write_text(
        json.dumps(audit, indent=2),
        encoding="utf-8",
    )
    plot_model_benchmark_dashboard(
        points,
        wafers,
        model_summary,
        audit,
        args.figure_path,
    )


if __name__ == "__main__":
    main()

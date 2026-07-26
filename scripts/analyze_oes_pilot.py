"""Render the preregistered OES pilot decision dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from etch_gate.visualization.oes_pilot import plot_oes_pilot_dashboard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--figure-path", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = json.loads((args.result_dir / "summary.json").read_text(encoding="utf-8"))
    wafers = pd.read_csv(args.result_dir / "wafer_metrics.csv")
    plot_oes_pilot_dashboard(wafers, summary, args.figure_path)


if __name__ == "__main__":
    main()

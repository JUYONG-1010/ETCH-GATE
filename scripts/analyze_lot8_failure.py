"""Create the ETCH-GATE Lot 8 failure decomposition."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from etch_gate.analysis.failure import lot_feature_z_scores, summarize_lot_failure
from etch_gate.visualization.failure import plot_lot_failure_atlas


def main() -> None:
    results_dir = Path("results/milestone3_process_baseline")
    points = pd.read_csv(results_dir / "point_predictions.csv")
    features = pd.read_csv(
        results_dir / "process_features.csv",
        index_col="experiment_key",
    )
    summary = summarize_lot_failure(points, family="pls", lot_number=8)
    z_scores = lot_feature_z_scores(
        features,
        summary["experiment_key"].tolist(),
    )
    summary.to_csv(results_dir / "lot8_failure_summary.csv", index=False)
    z_scores.to_csv(results_dir / "lot8_feature_z_scores.csv")
    plot_lot_failure_atlas(
        summary,
        z_scores,
        Path("docs/figures/process_baseline/lot8-failure-atlas.png"),
        lot_number=8,
    )


if __name__ == "__main__":
    main()

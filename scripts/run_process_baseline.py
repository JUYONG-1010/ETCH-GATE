"""Run ETCH-GATE Milestone 3 process-feature virtual metrology."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from etch_gate.analysis.process_baseline import GPRSettings, evaluate_process_baselines
from etch_gate.data.process import build_process_feature_table, load_process_traces
from etch_gate.visualization.process_baseline import (
    plot_process_cycle_atlas,
    plot_process_model_dashboard,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--figure-dir", type=Path, required=True)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cluster_bootstrap_summary(
    wafers: pd.DataFrame,
    *,
    family: str,
    replicates: int,
    seed: int,
) -> dict[str, object]:
    selected = wafers[wafers["family"] == family]
    paired = selected.pivot(
        index=["experiment_key", "lot_number"],
        columns="stage",
        values="mae",
    ).reset_index()
    lot_pairs = {
        lot: group[["template", "mean_shift", "full_map"]].to_numpy()
        for lot, group in paired.groupby("lot_number")
    }
    lots = np.asarray(sorted(lot_pairs))
    generator = np.random.default_rng(seed)
    reductions = []
    for _ in range(replicates):
        sampled_lots = generator.choice(lots, size=len(lots), replace=True)
        sampled = np.vstack([lot_pairs[lot] for lot in sampled_lots])
        reductions.append(1 - sampled[:, 2].mean() / sampled[:, 0].mean())
    interval = np.quantile(reductions, [0.025, 0.975])
    lot_means = paired.groupby("lot_number")[
        ["template", "mean_shift", "full_map"]
    ].mean()
    return {
        "family": family,
        "relative_mae_reduction": float(
            1 - paired["full_map"].mean() / paired["template"].mean()
        ),
        "lot_cluster_bootstrap_95_interval": [
            float(interval[0]),
            float(interval[1]),
        ],
        "bootstrap_replicates": replicates,
        "random_seed": seed,
        "lots_full_better_than_template": int(
            (lot_means["full_map"] < lot_means["template"]).sum()
        ),
        "lots_full_better_than_mean_shift": int(
            (lot_means["full_map"] < lot_means["mean_shift"]).sum()
        ),
        "total_lots": len(lot_means),
    }


def main() -> None:
    started = time.perf_counter()
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    traces = load_process_traces(
        args.data_dir / "Process_data.nc",
        args.data_dir / "Dictionary_process.nc",
    )
    features, diagnostics = build_process_feature_table(traces)
    dense_path = args.data_dir / "Si_Oxide_etch_89_points.csv"
    dense = pd.read_csv(dense_path)
    points, wafers, folds = evaluate_process_baselines(
        features,
        dense,
        families=tuple(config["families"]),
        ridge_parameters=tuple(config["ridge_parameters"]),
        pls_parameters=tuple(config["pls_parameters"]),
        gpr_parameters=tuple(
            GPRSettings(**parameters)
            for parameters in config.get("gpr_parameters", [])
        ),
        residual_variance_target=config["residual_variance_target"],
        maximum_residual_components=config["maximum_residual_components"],
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.output_dir / "process_features.csv")
    diagnostics.to_csv(args.output_dir / "process_diagnostics.csv")
    points.to_csv(args.output_dir / "point_predictions.csv", index=False)
    wafers.to_csv(args.output_dir / "wafer_metrics.csv", index=False)
    folds.to_csv(args.output_dir / "fold_diagnostics.csv", index=False)

    stage_metrics = (
        wafers.groupby(["family", "stage"])
        .agg(
            wafer_mean_mae=("mae", "mean"),
            wafer_mean_rmse=("rmse", "mean"),
            wafer_median_mae=("mae", "median"),
        )
        .reset_index()
        .to_dict(orient="records")
    )
    lot_macro = (
        wafers.groupby(["family", "stage", "lot_number"])["mae"]
        .mean()
        .groupby(["family", "stage"])
        .mean()
        .rename("lot_macro_mae")
        .reset_index()
        .to_dict(orient="records")
    )
    manifest = {
        "milestone": config["milestone"],
        "analysis": "nested_lolo_process_virtual_metrology",
        "configuration": config,
        "source_sha256": {
            "process": _sha256(args.data_dir / "Process_data.nc"),
            "dictionary": _sha256(args.data_dir / "Dictionary_process.nc"),
            "dense_metrology": _sha256(dense_path),
        },
        "counts": {
            "process_wafers": len(features),
            "modeled_dense_wafers": wafers["experiment_key"].nunique(),
            "lots": wafers["lot_number"].nunique(),
            "raw_common_signals": len({name.split("__")[0] for name in features}),
            "engineered_features": features.shape[1],
        },
        "stage_metrics": stage_metrics,
        "lot_macro_metrics": lot_macro,
        "paired_improvement": [
            _cluster_bootstrap_summary(
                wafers,
                family=family,
                replicates=config["bootstrap_replicates"],
                seed=config["random_seed"],
            )
            for family in config["families"]
        ],
        "model_evaluation_runtime_seconds": time.perf_counter() - started,
        "claim_boundary": {
            "gas_channel_chemical_identity_known": False,
            "oes_used": False,
            "test_lot_used_for_preprocessing_or_tuning": False,
            "production_specification_available": False,
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    representative = traces[sorted(traces)[0]]
    plot_process_cycle_atlas(
        representative,
        args.figure_dir / "process-cycle-atlas.png",
    )
    plot_process_model_dashboard(
        points,
        wafers,
        args.figure_dir / "process-model-dashboard.png",
    )


if __name__ == "__main__":
    main()

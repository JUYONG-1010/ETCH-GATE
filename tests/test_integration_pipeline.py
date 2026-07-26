from pathlib import Path

import numpy as np
import pandas as pd

from etch_gate.analysis.causal_replay import evaluate_causal_replay
from etch_gate.analysis.chronological import evaluate_chronological_vm
from etch_gate.analysis.drift import evaluate_drift_risk
from etch_gate.analysis.process_baseline import evaluate_process_baselines
from etch_gate.data.process import (
    LONG_PHASE_GAS,
    SHORT_PHASE_GAS,
    SOURCE_RF,
    ProcessTrace,
    build_process_feature_table,
)
from etch_gate.manifests import build_manifest


def _synthetic_release() -> tuple[dict[str, ProcessTrace], pd.DataFrame]:
    traces = {}
    dense_rows = []
    times = np.arange(0.0, 60.0, 0.2)
    active = (times >= 2.0) & (times <= 58.0)
    phase = np.floor((times - 2.0) / 3.0).astype(int)
    long_phase = active & (phase % 2 == 0)
    short_phase = active & ~long_phase
    for lot in range(1, 5):
        for wafer in range(3):
            key = f"2025-01-{lot:02d}_{wafer:02d}"
            factor = lot + wafer / 3
            values = pd.DataFrame(
                {
                    SOURCE_RF: active * (100 + factor),
                    LONG_PHASE_GAS: long_phase * (20 + 0.2 * factor),
                    SHORT_PHASE_GAS: short_phase * (18 + 0.1 * factor),
                    "Stat3_Etch_MV_Pressure": active
                    * (5 + 0.05 * factor + 0.02 * np.sin(times)),
                }
            )
            traces[key] = ProcessTrace(
                experiment_key=key,
                group_name=f"lot{lot}_wafer{wafer}",
                times=times,
                values=values,
            )
            for point in range(3):
                dense_rows.append(
                    {
                        "experiment_key": key,
                        "lot_number": lot,
                        "X": float(point),
                        "Y": 0.0,
                        "stepheight": (
                            10
                            + point
                            + 0.2 * factor
                            + 0.01 * point * factor
                            + 0.002 * point * factor**2
                        ),
                    }
                )
    return traces, pd.DataFrame(dense_rows)


def test_miniature_end_to_end_pipeline_and_manifest(tmp_path: Path) -> None:
    traces, dense = _synthetic_release()
    features, diagnostics = build_process_feature_table(
        traces,
        detector="complementary",
    )
    points, wafers, folds = evaluate_process_baselines(
        features,
        dense,
        families=("ridge", "pls"),
        ridge_parameters=(1.0,),
        pls_parameters=(1.0,),
        maximum_residual_components=2,
    )
    chronological = evaluate_chronological_vm(
        features,
        dense,
        families=("ridge",),
        minimum_training_lots=2,
        ridge_parameters=(1.0,),
        maximum_residual_components=2,
    )
    risk = evaluate_drift_risk(
        features,
        dense,
        folds,
        pca_components=2,
        budgets=(0.5,),
        random_replicates=2,
        bootstrap_replicates=20,
        maximum_residual_components=2,
    )
    causal = evaluate_causal_replay(
        features,
        dense,
        minimum_training_lots=2,
        budgets=(0.5,),
        pls_parameters=(1.0,),
        ridge_parameters=(1.0,),
        random_replicates=2,
        bootstrap_replicates=20,
        maximum_residual_components=2,
    )

    source = tmp_path / "synthetic.csv"
    result = tmp_path / "metrics.csv"
    dense.to_csv(source, index=False)
    causal.policy_budget_summary.to_csv(result, index=False)
    manifest = build_manifest(
        analysis="miniature_end_to_end",
        input_files=[source],
        config={"detector": "complementary"},
        random_seed=20260721,
        split_identifiers=["lot-aware"],
        runtime_seconds=0.0,
        result_files=[result],
        claim_boundaries=["synthetic regression test"],
        gate="PASS",
    )

    assert len(features) == 12
    assert diagnostics["detected_cycles"].min() >= 2
    assert points["experiment_key"].nunique() == 12
    assert wafers["stage"].nunique() == 3
    assert not chronological.wafer_metrics.empty
    assert risk.wafer_scores["experiment_key"].nunique() == 12
    assert not causal.wafer_timeline.empty
    assert manifest["gate"] == "PASS"

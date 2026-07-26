import numpy as np
import pandas as pd

from etch_gate.analysis.oes_v2 import evaluate_physics_constrained_oes_v2


def test_oes_v2_retains_every_selected_wafer_and_returns_finite_metrics() -> None:
    dense_rows = []
    process_rows = []
    oes_rows = []
    coordinates = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    for lot in range(4):
        for wafer in range(3):
            key = f"lot{lot}_wafer{wafer}"
            value = 3 * lot + wafer
            process_rows.append({"experiment_key": key, "process": value})
            oes_rows.append(
                {
                    "experiment_key": key,
                    "shape_a": value / 10,
                    "shape_b": (value + 1) ** 2,
                }
            )
            for point, (x, y) in enumerate(coordinates):
                dense_rows.append(
                    {
                        "experiment_key": key,
                        "lot_number": lot,
                        "X": x,
                        "Y": y,
                        "stepheight": 10 + 0.2 * value + 0.03 * point * value,
                    }
                )

    points, wafers, folds, summary = evaluate_physics_constrained_oes_v2(
        pd.DataFrame(process_rows).set_index("experiment_key"),
        pd.DataFrame(oes_rows).set_index("experiment_key"),
        pd.DataFrame(dense_rows),
        selected_lots=(0, 1, 2, 3),
        oes_components=(1,),
        ridge_alphas=(1.0,),
        process_pls_parameters=(1.0,),
        maximum_residual_components=2,
    )

    assert points["experiment_key"].nunique() == 12
    assert wafers["experiment_key"].nunique() == 12
    assert len(folds) == 4
    assert summary["dense_wafers"] == 12
    assert np.isfinite(summary["physics_constrained_lot_macro_mae"])

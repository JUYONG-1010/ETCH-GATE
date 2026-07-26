import numpy as np
import pandas as pd

from etch_gate.analysis.oes_pilot import evaluate_oes_pilot


def test_oes_pilot_compares_same_dense_wafers_in_each_family() -> None:
    rows = []
    process_rows = []
    oes_rows = []
    coordinates = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    for lot in range(4):
        for wafer in range(3):
            key = f"lot{lot}_wafer{wafer}"
            value = lot * 3 + wafer
            process_rows.append({"experiment_key": key, "process": value})
            oes_rows.append({"experiment_key": key, "oes": value**2})
            for point, (x, y) in enumerate(coordinates):
                rows.append(
                    {
                        "experiment_key": key,
                        "lot_number": lot,
                        "X": x,
                        "Y": y,
                        "stepheight": 10.0 + point + 0.2 * value + 0.01 * point * value,
                    }
                )
    points, wafers, folds, summary = evaluate_oes_pilot(
        pd.DataFrame(process_rows).set_index("experiment_key"),
        pd.DataFrame(oes_rows).set_index("experiment_key"),
        pd.DataFrame(rows),
        selected_lots=(0, 1, 2, 3),
        pls_parameters=(1.0,),
        maximum_residual_components=2,
    )

    assert set(points["family"]) == {"process_only_pls", "process_oes_pls"}
    assert wafers.groupby("family")["experiment_key"].nunique().to_dict() == {
        "process_oes_pls": 12,
        "process_only_pls": 12,
    }
    assert len(folds) == 8
    assert summary["dense_wafers"] == 12
    assert summary["combined_features"] == 2
    assert np.isfinite(summary["lot_macro_relative_mae_reduction"])

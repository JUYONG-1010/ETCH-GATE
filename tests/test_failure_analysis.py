import pandas as pd

from etch_gate.analysis.failure import summarize_lot_failure


def test_lot_failure_summary_separates_mean_and_shape() -> None:
    rows = []
    for stage, predicted in [
        ("template", [10.0, 12.0]),
        ("mean_shift", [11.0, 13.0]),
        ("full_map", [10.5, 13.5]),
    ]:
        for point, value in enumerate(predicted):
            rows.append(
                {
                    "family": "pls",
                    "lot_number": 8,
                    "experiment_key": "2024-08-07_01",
                    "stage": stage,
                    "predicted": value,
                    "observed": [10.0, 14.0][point],
                    "error": value - [10.0, 14.0][point],
                }
            )

    result = summarize_lot_failure(pd.DataFrame(rows), family="pls", lot_number=8)

    assert result.loc[0, "true_mean_shift"] == 1.0
    assert result.loc[0, "predicted_mean_shift"] == 1.0
    assert result.loc[0, "full_map_mae"] < result.loc[0, "mean_shift_mae"]

import numpy as np
import pandas as pd

from etch_gate.analysis.template import (
    leave_one_lot_out_decompose,
    summarize_decomposition,
)


def _synthetic_dense() -> pd.DataFrame:
    rows = []
    for lot, lot_shift in ((1, 1.0), (2, -1.0), (3, 0.5)):
        for wafer in (1, 2):
            for x, spatial_value in ((-1.0, 10.0), (1.0, 20.0)):
                stepheight = spatial_value + lot_shift + wafer * 0.1
                rows.append(
                    {
                        "experiment_key": f"lot{lot}_wafer{wafer}",
                        "lot_number": lot,
                        "wafer_number": wafer,
                        "X": x,
                        "Y": 0.0,
                        "stepheight": stepheight,
                        "oxide_etch": stepheight / 10,
                        "si_etch": stepheight - stepheight / 10,
                        "postox_thickness": 1.0,
                        "postox_thickness_nan": 1.0,
                    }
                )
    return pd.DataFrame(rows)


def test_leave_one_lot_out_assigns_every_row_once() -> None:
    table = _synthetic_dense()

    result = leave_one_lot_out_decompose(table, "stepheight")

    assert len(result) == len(table)
    assert not result.duplicated(["experiment_key", "X", "Y"]).any()
    assert (result["lot_number"] == result["outer_test_lot"]).all()


def test_true_mean_shift_removes_pure_wafer_offset() -> None:
    result = leave_one_lot_out_decompose(_synthetic_dense(), "stepheight")

    np.testing.assert_allclose(result["residual"], 0.0, atol=1e-12)
    residual_means = result.groupby("experiment_key")["residual"].mean()
    np.testing.assert_allclose(residual_means, 0.0, atol=1e-12)


def test_held_out_values_do_not_change_their_template() -> None:
    original = _synthetic_dense()
    changed = original.copy()
    changed.loc[changed["lot_number"] == 1, "stepheight"] += 1000

    first = leave_one_lot_out_decompose(original, "stepheight")
    second = leave_one_lot_out_decompose(changed, "stepheight")
    first_lot = first[first["outer_test_lot"] == 1]["template_prediction"]
    second_lot = second[second["outer_test_lot"] == 1]["template_prediction"]

    np.testing.assert_allclose(first_lot, second_lot)


def test_summary_marks_high_template_r2_as_dominant() -> None:
    result = leave_one_lot_out_decompose(_synthetic_dense(), "stepheight")

    summary = summarize_decomposition(result, template_dominance_threshold=0.8)

    assert summary["template_r2"] > 0.8
    assert summary["template_dominant"] is True
    assert summary["true_mean_shift_oracle_r2"] == 1.0

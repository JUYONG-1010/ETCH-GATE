import numpy as np
import pandas as pd

from etch_gate.analysis.model_benchmark import summarize_model_benchmark


def test_model_benchmark_reports_paired_lot_comparison() -> None:
    wafer_rows = []
    point_rows = []
    for lot in range(3):
        for wafer in range(2):
            key = f"l{lot}w{wafer}"
            pls_mae = 0.1 + 0.01 * lot + 0.005 * wafer
            for family, mae, std in [
                ("pls", pls_mae, np.nan),
                ("gpr", 2 * pls_mae, 0.12 + 0.01 * lot + 0.005 * wafer),
            ]:
                wafer_rows.append(
                    {
                        "experiment_key": key,
                        "lot_number": lot,
                        "family": family,
                        "stage": "full_map",
                        "mae": mae,
                        "rmse": mae,
                        "mean_error": mae,
                        "mean_predicted_std": std,
                    }
                )
                point_rows.append(
                    {
                        "experiment_key": key,
                        "lot_number": lot,
                        "family": family,
                        "stage": "full_map",
                        "error": mae,
                        "predicted_std": std,
                    }
                )

    summary, lots, audit = summarize_model_benchmark(
        pd.DataFrame(wafer_rows),
        pd.DataFrame(point_rows),
        bootstrap_replicates=100,
    )

    assert set(summary["family"]) == {"pls", "gpr"}
    assert len(lots) == 6
    assert audit["primary_model"] == "pls"
    assert np.isclose(audit["gpr_relative_mae_change_vs_pls"], 1.0)
    assert audit["pls_lot_wins_over_gpr"] == 3

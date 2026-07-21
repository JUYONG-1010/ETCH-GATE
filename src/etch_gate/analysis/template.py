"""Leakage-resistant target and spatial-template analysis."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

TARGETS = ("stepheight", "oxide_etch", "si_etch")
KEY_COLUMNS = ("experiment_key", "lot_number", "wafer_number")
COORDINATE_COLUMNS = ("X", "Y")


def validate_dense_measurements(table: pd.DataFrame) -> None:
    """Validate the columns and one-value-per-wafer-coordinate structure."""

    required = {
        *KEY_COLUMNS,
        *COORDINATE_COLUMNS,
        *TARGETS,
        "postox_thickness",
        "postox_thickness_nan",
    }
    missing = sorted(required - set(table.columns))
    if missing:
        raise ValueError(f"dense measurement table is missing columns: {missing}")
    if table.empty:
        raise ValueError("dense measurement table is empty")
    if table[list(KEY_COLUMNS)].isna().any().any():
        raise ValueError("dense measurement table contains missing wafer identities")
    if table.duplicated([*KEY_COLUMNS, *COORDINATE_COLUMNS]).any():
        raise ValueError("dense measurement table contains duplicate wafer coordinates")
    if not np.isfinite(table[[*COORDINATE_COLUMNS, *TARGETS]].to_numpy(dtype=float)).all():
        raise ValueError("dense measurement coordinates or targets are non-finite")

    point_counts = table.groupby(list(KEY_COLUMNS), sort=False).size()
    if point_counts.nunique() != 1:
        raise ValueError("dense wafers do not have a consistent point count")
    coordinate_counts = table.groupby(list(KEY_COLUMNS), sort=False).apply(
        lambda group: len(group[list(COORDINATE_COLUMNS)].drop_duplicates()),
        include_groups=False,
    )
    if not point_counts.equals(coordinate_counts):
        raise ValueError("a dense wafer repeats one or more coordinates")


def _r2(observed: np.ndarray, predicted: np.ndarray) -> float:
    denominator = np.sum((observed - observed.mean()) ** 2)
    if denominator <= 0:
        return float("nan")
    return float(1 - np.sum((observed - predicted) ** 2) / denominator)


def leave_one_lot_out_decompose(table: pd.DataFrame, target: str) -> pd.DataFrame:
    """Decompose each held-out lot using a template fitted to other lots only."""

    validate_dense_measurements(table)
    if target not in TARGETS:
        raise ValueError(f"unknown target: {target}")

    parts = []
    coordinate_columns = list(COORDINATE_COLUMNS)
    for held_out_lot in sorted(table["lot_number"].unique()):
        training = table[table["lot_number"] != held_out_lot]
        test = table[table["lot_number"] == held_out_lot].copy()
        template = training.groupby(coordinate_columns, sort=False)[target].mean()
        coordinate_index = test.set_index(coordinate_columns).index
        template_prediction = coordinate_index.map(template).to_numpy(dtype=float)
        if not np.isfinite(template_prediction).all():
            raise ValueError(
                f"training lots do not cover all coordinates for held-out lot {held_out_lot}"
            )

        test["target"] = target
        test["outer_test_lot"] = held_out_lot
        test["global_prediction"] = float(training[target].mean())
        test["template_prediction"] = template_prediction
        test["_template_difference"] = test[target] - test["template_prediction"]
        test["mean_shift"] = test.groupby(
            "experiment_key", sort=False
        )["_template_difference"].transform("mean")
        test["template_plus_true_mean_shift"] = (
            test["template_prediction"] + test["mean_shift"]
        )
        test["residual"] = test[target] - test["template_plus_true_mean_shift"]
        test["postox_value_was_filled"] = test["postox_thickness_nan"].isna()
        parts.append(
            test[
                [
                    *KEY_COLUMNS,
                    *COORDINATE_COLUMNS,
                    "target",
                    target,
                    "outer_test_lot",
                    "global_prediction",
                    "template_prediction",
                    "mean_shift",
                    "template_plus_true_mean_shift",
                    "residual",
                    "postox_value_was_filled",
                ]
            ].rename(columns={target: "observed"})
        )

    result = pd.concat(parts, ignore_index=True)
    expected_rows = len(table)
    if len(result) != expected_rows:
        raise RuntimeError(
            f"leave-one-lot-out decomposition produced {len(result)} rows, "
            f"expected {expected_rows}"
        )
    return result


def summarize_decomposition(
    decomposed: pd.DataFrame,
    *,
    template_dominance_threshold: float = 0.95,
) -> dict[str, object]:
    """Summarize cross-validated template, mean-shift, and residual performance."""

    observed = decomposed["observed"].to_numpy(dtype=float)
    global_prediction = decomposed["global_prediction"].to_numpy(dtype=float)
    template_prediction = decomposed["template_prediction"].to_numpy(dtype=float)
    shifted_prediction = decomposed["template_plus_true_mean_shift"].to_numpy(
        dtype=float
    )

    row_template_error = np.abs(observed - template_prediction)
    row_shifted_error = np.abs(observed - shifted_prediction)
    lot_template_mae = decomposed.assign(error=row_template_error).groupby(
        "lot_number"
    )["error"].mean()
    lot_shifted_mae = decomposed.assign(error=row_shifted_error).groupby(
        "lot_number"
    )["error"].mean()
    wafer_residual_rmse = decomposed.groupby("experiment_key")["residual"].apply(
        lambda values: float(np.sqrt(np.mean(np.square(values))))
    )

    template_r2 = _r2(observed, template_prediction)
    return {
        "target": str(decomposed["target"].iat[0]),
        "rows": len(decomposed),
        "wafers": int(decomposed["experiment_key"].nunique()),
        "lots": int(decomposed["lot_number"].nunique()),
        "global_r2": _r2(observed, global_prediction),
        "template_r2": template_r2,
        "template_dominant": bool(template_r2 >= template_dominance_threshold),
        "template_dominance_threshold": template_dominance_threshold,
        "true_mean_shift_oracle_r2": _r2(observed, shifted_prediction),
        "template_mae": float(row_template_error.mean()),
        "template_lot_macro_mae": float(lot_template_mae.mean()),
        "true_mean_shift_oracle_mae": float(row_shifted_error.mean()),
        "true_mean_shift_oracle_lot_macro_mae": float(lot_shifted_mae.mean()),
        "wafer_residual_rmse_mean": float(wafer_residual_rmse.mean()),
        "wafer_residual_rmse_median": float(wafer_residual_rmse.median()),
        "mean_shift_standard_deviation": float(
            decomposed.groupby("experiment_key")["mean_shift"].first().std(ddof=1)
        ),
        "postoxide_filled_rows": int(decomposed["postox_value_was_filled"].sum()),
    }


def wafer_summaries(decomposed: pd.DataFrame) -> pd.DataFrame:
    """Return one row per wafer with mean shift and residual error summaries."""

    return (
        decomposed.groupby(
            ["target", *KEY_COLUMNS, "outer_test_lot"],
            as_index=False,
            sort=False,
        )
        .agg(
            observed_mean=("observed", "mean"),
            template_mean=("template_prediction", "mean"),
            mean_shift=("mean_shift", "first"),
            residual_mae=("residual", lambda values: float(np.mean(np.abs(values)))),
            residual_rmse=(
                "residual",
                lambda values: float(np.sqrt(np.mean(np.square(values)))),
            ),
            maximum_absolute_residual=(
                "residual",
                lambda values: float(np.max(np.abs(values))),
            ),
            postoxide_filled_points=("postox_value_was_filled", "sum"),
        )
    )


def lot_summaries(wafer_table: pd.DataFrame) -> pd.DataFrame:
    """Aggregate wafer-level mean shift and residual error by held-out lot."""

    return (
        wafer_table.groupby(["target", "lot_number"], as_index=False, sort=False)
        .agg(
            wafers=("experiment_key", "nunique"),
            mean_shift_mean=("mean_shift", "mean"),
            mean_shift_std=("mean_shift", "std"),
            residual_rmse_mean=("residual_rmse", "mean"),
            residual_rmse_std=("residual_rmse", "std"),
            maximum_absolute_residual=("maximum_absolute_residual", "max"),
            postoxide_filled_points=("postoxide_filled_points", "sum"),
        )
        .fillna({"mean_shift_std": 0.0, "residual_rmse_std": 0.0})
    )


def decompose_all_targets(
    table: pd.DataFrame,
    targets: Iterable[str] = TARGETS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, object]]]:
    """Run all target decompositions and return row, wafer, lot, and metric outputs."""

    decompositions = [
        leave_one_lot_out_decompose(table, target) for target in targets
    ]
    row_table = pd.concat(decompositions, ignore_index=True)
    wafer_table = wafer_summaries(row_table)
    lot_table = lot_summaries(wafer_table)
    metrics = [summarize_decomposition(part) for part in decompositions]
    return row_table, wafer_table, lot_table, metrics

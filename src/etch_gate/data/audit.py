"""Reproducible audit of the small BOSCH plasma-etching data release."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from netCDF4 import Dataset

GROUP_PATTERN = re.compile(r"Day_(\d{4})_(\d{2})_(\d{2})_Wafer_(\d{2})")
TARGETS = ("stepheight", "oxide_etch", "si_etch")


def process_group_to_key(group_name: str) -> str:
    """Convert a process NetCDF group name to the measurement experiment key."""

    match = GROUP_PATTERN.fullmatch(group_name)
    if match is None:
        raise ValueError(f"unexpected process group name: {group_name}")
    year, month, day, wafer = match.groups()
    return f"{year}-{month}-{day}_{wafer}"


def _r2(observed: np.ndarray, predicted: np.ndarray) -> float:
    denominator = np.sum((observed - observed.mean()) ** 2)
    if denominator == 0:
        return float("nan")
    return float(1 - np.sum((observed - predicted) ** 2) / denominator)


def _cross_tool_calibration_audit(paired: pd.DataFrame) -> dict[str, object]:
    """Evaluate train-lot-only coordinate bias correction between the two tools."""

    results = {}
    lots = sorted(paired["lot_number_9"].unique())
    for target in TARGETS:
        raw_lot_mae = []
        calibrated_lot_mae = []

        for held_out_lot in lots:
            training = paired[paired["lot_number_9"] != held_out_lot].copy()
            test = paired[paired["lot_number_9"] == held_out_lot].copy()
            training["tool_bias"] = training[f"{target}_9"] - training[f"{target}_89"]
            coordinate_bias = training.groupby(["X", "Y"])["tool_bias"].median()
            test_index = test.set_index(["X", "Y"]).index

            raw_error = test[f"{target}_9"] - test[f"{target}_89"]
            calibrated_prediction = (
                test[f"{target}_9"].to_numpy()
                - test_index.map(coordinate_bias).to_numpy(dtype=float)
            )
            calibrated_error = calibrated_prediction - test[f"{target}_89"].to_numpy()
            raw_lot_mae.append(float(raw_error.abs().mean()))
            calibrated_lot_mae.append(float(np.mean(np.abs(calibrated_error))))

        raw_macro = float(np.mean(raw_lot_mae))
        calibrated_macro = float(np.mean(calibrated_lot_mae))
        results[target] = {
            "held_out_lots": len(lots),
            "raw_lot_macro_mae": raw_macro,
            "calibrated_lot_macro_mae": calibrated_macro,
            "relative_mae_reduction": 1 - calibrated_macro / raw_macro,
            "lots_improved": sum(
                calibrated < raw
                for raw, calibrated in zip(
                    raw_lot_mae, calibrated_lot_mae, strict=True
                )
            ),
        }

    return results


def _measurement_audit(data_dir: Path) -> dict[str, object]:
    sparse = pd.read_csv(data_dir / "Si_Oxide_etch_9_points.csv")
    dense = pd.read_csv(data_dir / "Si_Oxide_etch_89_points.csv")
    sparse_keyed = sparse.dropna(subset=["experiment_key"]).copy()

    sparse_keys = set(sparse_keyed["experiment_key"])
    dense_keys = set(dense["experiment_key"])
    paired_keys = sparse_keys & dense_keys
    sparse_coordinates = set(
        sparse[["X", "Y"]].drop_duplicates().itertuples(index=False, name=None)
    )
    dense_coordinates = set(
        dense[["X", "Y"]].drop_duplicates().itertuples(index=False, name=None)
    )

    paired = sparse_keyed[sparse_keyed["experiment_key"].isin(paired_keys)].merge(
        dense[dense["experiment_key"].isin(paired_keys)],
        on=["experiment_key", "X", "Y"],
        suffixes=("_9", "_89"),
        validate="one_to_one",
    )

    cross_tool = {}
    for target in TARGETS:
        difference = paired[f"{target}_9"] - paired[f"{target}_89"]
        cross_tool[target] = {
            "bias_9_minus_89": float(difference.mean()),
            "mae": float(difference.abs().mean()),
            "correlation": float(
                paired[[f"{target}_9", f"{target}_89"]].corr().iloc[0, 1]
            ),
        }

    sparse_si_formula_error = (
        sparse["stepheight"] - sparse["oxide_etch"] - sparse["si_etch"]
    ).abs()
    dense_si_formula_error = (
        dense["stepheight"] - dense["postox_thickness"] - dense["si_etch"]
    ).abs()

    return {
        "sparse_rows": len(sparse),
        "sparse_wafers_total": len(sparse) // 9,
        "sparse_identified_wafers": sparse_keyed["experiment_key"].nunique(),
        "sparse_unidentified_rows": int(sparse["experiment_key"].isna().sum()),
        "dense_rows": len(dense),
        "dense_wafers": dense["experiment_key"].nunique(),
        "paired_wafers": len(paired_keys),
        "paired_rows": len(paired),
        "sparse_points": len(sparse_coordinates),
        "dense_points": len(dense_coordinates),
        "sparse_points_are_dense_subset": sparse_coordinates <= dense_coordinates,
        "postoxide_raw_nan": int(dense["postox_thickness_nan"].isna().sum()),
        "postoxide_filled_nan": int(dense["postox_thickness"].isna().sum()),
        "dense_wafers_by_lot": {
            str(key): int(value)
            for key, value in dense[
                ["experiment_key", "lot_number"]
            ].drop_duplicates().groupby("lot_number").size().items()
        },
        "paired_wafers_by_lot": {
            str(key): int(value)
            for key, value in paired[
                ["experiment_key", "lot_number_9"]
            ].drop_duplicates().groupby("lot_number_9").size().items()
        },
        "cross_tool_raw": cross_tool,
        "released_si_etch_formula": {
            "sparse": "stepheight - oxide_etch",
            "sparse_maximum_absolute_error": float(
                sparse_si_formula_error.max()
            ),
            "dense": "stepheight - postox_thickness",
            "dense_maximum_absolute_error": float(
                dense_si_formula_error.max()
            ),
            "formulas_are_different": True,
        },
        "cross_tool_leave_one_lot_out_calibration": _cross_tool_calibration_audit(
            paired
        ),
    }


def _process_audit(data_dir: Path) -> dict[str, object]:
    with Dataset(data_dir / "Dictionary_process.nc") as dictionary:
        decoder = np.asarray(dictionary["data"][:])

    group_rows = []
    feature_sets: Counter[tuple[str, ...]] = Counter()
    decoded_values_are_finite = True
    invalid_dictionary_codes = 0

    with Dataset(data_dir / "Process_data.nc") as dataset:
        for group_name, group in dataset.groups.items():
            features = tuple(str(value) for value in group["feature"][:])
            feature_sets[features] += 1
            encoded = np.asarray(group["data"][:])
            invalid_dictionary_codes += int((encoded >= len(decoder)).sum())
            decoded_values_are_finite &= bool(np.isfinite(decoder[encoded]).all())
            times = np.asarray(group["times"][:])
            time_steps = np.diff(times)
            group_rows.append(
                {
                    "group": group_name,
                    "key": process_group_to_key(group_name),
                    "date": group_name.split("_Wafer_")[0].removeprefix("Day_"),
                    "samples": len(times),
                    "features": len(features),
                    "median_step_seconds": float(np.median(time_steps)),
                    "maximum_step_seconds": float(time_steps.max()),
                }
            )

    all_feature_sets = list(feature_sets)
    common_features = set.intersection(*(set(values) for values in all_feature_sets))
    union_features = set.union(*(set(values) for values in all_feature_sets))
    date_counts = Counter(row["date"] for row in group_rows)

    return {
        "process_wafers": len(group_rows),
        "wafers_by_date": dict(sorted(date_counts.items())),
        "feature_set_sizes": {
            str(len(features)): count for features, count in feature_sets.items()
        },
        "common_features": len(common_features),
        "union_features": len(union_features),
        "first_day_extra_features": sorted(union_features - common_features),
        "minimum_samples": min(row["samples"] for row in group_rows),
        "median_samples": float(np.median([row["samples"] for row in group_rows])),
        "maximum_samples": max(row["samples"] for row in group_rows),
        "median_sample_step_seconds": float(
            np.median([row["median_step_seconds"] for row in group_rows])
        ),
        "maximum_timestamp_gap_seconds": max(
            row["maximum_step_seconds"] for row in group_rows
        ),
        "decoded_values_are_finite": decoded_values_are_finite,
        "invalid_dictionary_codes": invalid_dictionary_codes,
        "experiment_keys": sorted(row["key"] for row in group_rows),
    }


def _template_audit(data_dir: Path) -> dict[str, object]:
    dense = pd.read_csv(data_dir / "Si_Oxide_etch_89_points.csv")
    coordinates = ["X", "Y"]
    results = {}

    for target in TARGETS:
        observed_parts = []
        global_parts = []
        template_parts = []
        oracle_parts = []

        for lot in sorted(dense["lot_number"].unique()):
            training = dense[dense["lot_number"] != lot]
            test = dense[dense["lot_number"] == lot]
            template = training.groupby(coordinates)[target].mean()
            centered_template = template - template.mean()
            coordinate_index = test.set_index(coordinates).index

            observed_parts.append(test[target].to_numpy())
            global_parts.append(np.full(len(test), training[target].mean()))
            template_parts.append(coordinate_index.map(template).to_numpy(dtype=float))
            oracle_parts.append(
                test.groupby("experiment_key")[target].transform("mean").to_numpy()
                + coordinate_index.map(centered_template).to_numpy(dtype=float)
            )

        observed = np.concatenate(observed_parts)
        global_prediction = np.concatenate(global_parts)
        template_prediction = np.concatenate(template_parts)
        oracle_prediction = np.concatenate(oracle_parts)
        results[target] = {
            "global_r2": _r2(observed, global_prediction),
            "template_r2": _r2(observed, template_prediction),
            "oracle_true_mean_shift_r2": _r2(observed, oracle_prediction),
            "template_mae": float(np.mean(np.abs(observed - template_prediction))),
        }

    return results


def audit_bosch_data(data_dir: Path) -> dict[str, object]:
    """Return source, measurement, process, and template audit results."""

    return {
        "source": "https://doi.org/10.5281/zenodo.17122442",
        "measurement": _measurement_audit(data_dir),
        "process": _process_audit(data_dir),
        "template": _template_audit(data_dir),
        "full_oes_downloaded": bool(list(data_dir.glob("Day_*.nc"))),
    }

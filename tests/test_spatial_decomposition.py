import numpy as np
import pandas as pd

from etch_gate.analysis.spatial_decomposition import (
    coordinate_zones,
    evaluate_spatial_decomposition,
)


def _problem() -> tuple[pd.DataFrame, pd.DataFrame]:
    coordinates = [
        (0.0, 0.0),
        (1.0, 0.0),
        (-1.0, 0.0),
        (0.0, 1.0),
        (0.0, -1.0),
    ]
    features = []
    rows = []
    for lot in range(1, 4):
        for wafer in range(3):
            key = f"2025-01-0{lot}_{wafer:02d}"
            value = lot + wafer / 3
            features.append({"experiment_key": key, "signal": value})
            for point, (x, y) in enumerate(coordinates):
                rows.append(
                    {
                        "experiment_key": key,
                        "lot_number": lot,
                        "X": x,
                        "Y": y,
                        "stepheight": 10 + point + 0.2 * value,
                    }
                )
    return pd.DataFrame(features).set_index("experiment_key"), pd.DataFrame(rows)


def test_coordinate_zones_are_radius_deterministic() -> None:
    zones = coordinate_zones(
        np.array([[0.0, 0.0], [0.5, 0.0], [1.0, 0.0]])
    )

    assert zones.tolist() == ["center", "middle", "edge"]


def test_spatial_decomposition_includes_five_stages_and_oracle_bounds() -> None:
    features, dense = _problem()
    result = evaluate_spatial_decomposition(
        features,
        dense,
        pls_parameters=(1.0,),
        maximum_residual_components=2,
        bootstrap_replicates=100,
    )

    assert result.point_predictions["stage"].nunique() == 5
    assert set(result.gate) >= {
        "status",
        "relative_residual_stage_gain",
        "lot_cluster_bootstrap_95_interval",
    }
    assert len(result.coordinate_metrics) == 5 * 5

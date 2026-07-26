import numpy as np
import pandas as pd
from sklearn.cross_decomposition import PLSRegression

from etch_gate.analysis.feature_ablation import (
    FEATURE_GROUPS,
    feature_group,
    pls_vip,
    select_feature_groups,
    sensor_family,
)


def test_feature_group_selection_is_complete_and_exact() -> None:
    columns = [
        f"Signal__{statistic}"
        for statistics in FEATURE_GROUPS.values()
        for statistic in statistics
    ]
    table = pd.DataFrame(np.ones((2, len(columns))), columns=columns)

    selected = select_feature_groups(table, ("G1_level", "G4_cycle_behavior"))

    assert all(
        feature_group(column) in {"G1_level", "G4_cycle_behavior"}
        for column in selected
    )
    assert selected.shape[1] == 5


def test_pls_vip_identifies_dominant_synthetic_feature() -> None:
    rng = np.random.default_rng(4)
    x = rng.normal(size=(80, 4))
    y = 4.0 * x[:, 0] + 0.05 * rng.normal(size=80)
    model = PLSRegression(n_components=2, scale=True).fit(x, y)

    vip = pls_vip(model)

    assert vip.shape == (4,)
    assert int(np.argmax(vip)) == 0
    assert vip[0] > 1.0


def test_sensor_family_uses_only_released_label_text() -> None:
    assert sensor_family("Stat3_Etch_MV_Gas4Flow__active_mean") == "gas_or_backside_flow"
    assert sensor_family("Stat3_Etch_MV_Pressure__active_mean") == "pressure"
    assert (
        sensor_family("Stat3_Etch_MV_SourceRFLoadPower__active_mean")
        == "rf_power_matching_electrical"
    )

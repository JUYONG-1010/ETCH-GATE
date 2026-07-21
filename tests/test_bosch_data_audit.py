import numpy as np
import pytest

from etch_gate.data.audit import _r2, process_group_to_key


def test_process_group_to_key() -> None:
    assert (
        process_group_to_key("Day_2024_08_21_Wafer_09")
        == "2024-08-21_09"
    )


def test_process_group_to_key_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="unexpected process group"):
        process_group_to_key("Wafer_09")


def test_r2_reference_cases() -> None:
    observed = np.array([1.0, 2.0, 3.0])
    assert _r2(observed, observed) == 1.0
    assert _r2(observed, np.full(3, 2.0)) == 0.0

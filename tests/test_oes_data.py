from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from netCDF4 import Dataset

from etch_gate.data.oes import (
    OES_STATISTICS,
    audit_oes_day,
    extract_oes_feature_table,
    load_oes_preview,
    oes_group_to_key,
)
from etch_gate.data.process import ProcessTrace


def _write_oes_fixture(directory: Path) -> tuple[Path, Path]:
    dictionary_path = directory / "Dictionary_OES.nc"
    with Dataset(dictionary_path, "w") as dataset:
        dataset.createDimension("x", 100)
        dataset.createVariable("data", "f4", ("x",))[:] = np.arange(100)

    oes_path = directory / "Day_2024_07_05.nc"
    with Dataset(oes_path, "w") as dataset:
        group = dataset.createGroup("Wafer_01")
        group.createDimension("time", 246)
        group.createDimension("wavelength", 4)
        group.createVariable("times", "f8", ("time",))[:] = 1_000 + np.arange(246) * 0.04
        group.createVariable("wavelengths", "f8", ("wavelength",))[:] = [200, 300, 400, 500]
        values = np.arange(246 * 4, dtype=np.uint16).reshape(246, 4) % 100
        group.createVariable("data", "u2", ("time", "wavelength"))[:] = values
    return oes_path, dictionary_path


def _process_fixture() -> dict[str, ProcessTrace]:
    times = np.arange(50) * 0.2
    source = np.zeros(50)
    source[5:46] = 1
    long_phase = np.zeros(50)
    long_phase[6:10] = 1
    long_phase[26:30] = 1
    short_phase = 1 - long_phase
    values = {
        "Stat3_Etch_MV_SourceRFLoadPower": source,
        "Stat3_Etch_MV_Gas5Flow": long_phase,
        "Stat3_Etch_MV_Gas4Flow": short_phase,
    }
    import pandas as pd

    trace = ProcessTrace(
        experiment_key="2024-07-05_01",
        group_name="fixture",
        times=times,
        values=pd.DataFrame(values),
    )
    return {trace.experiment_key: trace}


def test_oes_group_to_key_uses_file_date_and_group_wafer() -> None:
    assert oes_group_to_key(Path("Day_2024_07_05.nc"), "Wafer_03") == "2024-07-05_03"


def test_oes_audit_and_preview_decode_without_loading_targets() -> None:
    # Keep netCDF fixture paths relative (Windows HDF5 Unicode-path limitation).
    Path("tmp").mkdir(exist_ok=True)
    with TemporaryDirectory(dir=Path("tmp")) as temporary_directory:
        oes_path, dictionary_path = _write_oes_fixture(Path(temporary_directory))
        audit, wavelengths, manifest = audit_oes_day(
            oes_path,
            dictionary_path,
            _process_fixture(),
            expected_wavelength_count=4,
            chunk_rows=17,
        )
        preview = load_oes_preview(
            oes_path,
            dictionary_path,
            "Wafer_01",
            maximum_time_rows=20,
        )
        features, diagnostics = extract_oes_feature_table(
            [oes_path],
            dictionary_path,
            _process_fixture(),
            chunk_rows=17,
        )

        assert manifest["all_groups_pass"]
        assert audit.loc[0, "passes_integrity_gate"]
        assert wavelengths.tolist() == [200, 300, 400, 500]
        assert preview.decoded_intensity.shape[0] <= 20
        assert preview.decoded_intensity.shape[1] == 4
        assert features.shape == (1, 4 * len(OES_STATISTICS))
        assert diagnostics.loc["2024-07-05_01", "aligned_cycles"] == 2
        assert np.isfinite(features.to_numpy()).all()

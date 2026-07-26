"""Run the one-day OES integrity and process-alignment gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from etch_gate.data.oes import audit_oes_day, load_oes_preview
from etch_gate.data.process import load_process_traces
from etch_gate.visualization.oes import plot_oes_integrity_dashboard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--oes-file", type=str, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--figure-path", type=Path, required=True)
    return parser.parse_args()


def _file_hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    oes_path = args.data_dir / args.oes_file
    dictionary_path = args.data_dir / "Dictionary_OES.nc"
    process_traces = load_process_traces(
        args.data_dir / "Process_data.nc",
        args.data_dir / "Dictionary_process.nc",
    )
    audit, wavelengths, manifest = audit_oes_day(
        oes_path,
        dictionary_path,
        process_traces,
    )
    dense = pd.read_csv(args.data_dir / "Si_Oxide_etch_89_points.csv")
    dense_keys = set(dense["experiment_key"])
    audit["has_direct_89_point_target"] = audit["experiment_key"].isin(dense_keys)
    manifest["direct_target_wafers"] = int(audit["has_direct_89_point_target"].sum())
    manifest["wavelength_spacing_nm"] = {
        "median": float(pd.Series(wavelengths).diff().median()),
        "minimum": float(pd.Series(wavelengths).diff().min()),
        "maximum": float(pd.Series(wavelengths).diff().max()),
    }
    manifest["source_hashes"] = {
        "oes_md5": _file_hash(oes_path, "md5"),
        "oes_sha256": _file_hash(oes_path, "sha256"),
        "dictionary_sha256": _file_hash(dictionary_path, "sha256"),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit.to_csv(args.output_dir / "oes_day_audit.csv", index=False)
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    representative_group = audit.iloc[0]["group_name"]
    preview = load_oes_preview(oes_path, dictionary_path, representative_group)
    plot_oes_integrity_dashboard(
        preview,
        process_traces[preview.experiment_key],
        audit,
        args.figure_path,
    )


if __name__ == "__main__":
    main()

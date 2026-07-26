"""Extract target-free cycle/phase OES summaries from available daily files."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from etch_gate.data.oes import OES_STATISTICS, extract_oes_feature_table
from etch_gate.data.process import load_process_traces


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--oes-files", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    traces = load_process_traces(
        args.data_dir / "Process_data.nc",
        args.data_dir / "Dictionary_process.nc",
    )
    paths = [args.data_dir / name for name in args.oes_files]
    features, diagnostics = extract_oes_feature_table(
        paths,
        args.data_dir / "Dictionary_OES.nc",
        traces,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.output_dir / "oes_features.csv")
    diagnostics.to_csv(args.output_dir / "oes_feature_diagnostics.csv")
    manifest = {
        "source_files": args.oes_files,
        "wafers": len(features),
        "wavelength_statistics": list(OES_STATISTICS),
        "features_per_wafer": features.shape[1],
        "target_used_during_extraction": False,
        "elapsed_seconds": time.perf_counter() - started,
        "claim_boundary": "target-free feature feasibility; one lot cannot test generalization",
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

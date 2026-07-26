"""Extract broadband-normalized OES spectral-shape features for V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from etch_gate.data.oes import extract_normalized_oes_shape_table
from etch_gate.data.process import load_process_traces


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--oes-files", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    traces = load_process_traces(
        args.data_dir / "Process_data.nc", args.data_dir / "Dictionary_process.nc"
    )
    features, diagnostics = extract_normalized_oes_shape_table(
        [args.data_dir / name for name in args.oes_files],
        args.data_dir / "Dictionary_OES.nc",
        traces,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.output_dir / "normalized_oes_shape_features.csv")
    diagnostics.to_csv(args.output_dir / "diagnostics.csv")
    (args.output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "wafer_count": len(features),
                "feature_count": features.shape[1],
                "normalization": "each OES row divided by broadband intensity",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

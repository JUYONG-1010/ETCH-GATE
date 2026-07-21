"""Run ETCH-GATE Milestone 2 target and spatial-template analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from etch_gate.analysis.template import decompose_all_targets
from etch_gate.visualization.template import (
    plot_decomposition_atlas,
    plot_measurement_provenance,
)


def parse_args() -> argparse.Namespace:
    """Parse data, configuration, result, and figure paths."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--figure-dir", type=Path, required=True)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    """Run leakage-resistant decomposition and persist all result layers."""

    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    dense = pd.read_csv(args.data)
    rows, wafers, lots, metrics = decompose_all_targets(
        dense,
        targets=config["targets"],
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows.to_csv(args.output_dir / "point_decomposition.csv", index=False)
    wafers.to_csv(args.output_dir / "wafer_summary.csv", index=False)
    lots.to_csv(args.output_dir / "lot_summary.csv", index=False)
    manifest = {
        "milestone": config["milestone"],
        "analysis": "lot_aware_target_template_decomposition",
        "source_file": args.data.as_posix(),
        "source_sha256": _sha256(args.data),
        "configuration": config,
        "metrics": metrics,
        "provenance": {
            "stepheight": "direct 89-point profilometer measurement",
            "oxide_etch": (
                "derived from pre/post oxide; pre-etch dense values are mostly IDW "
                "from 15 points and 157 failed post-etch fits are released with IDW fills"
            ),
            "si_etch": (
                "released dense CSV equals stepheight minus postox_thickness; "
                "the sparse CSV instead equals stepheight minus oxide_etch"
            ),
        },
        "claim_boundary": {
            "template_plus_true_mean_shift_is_oracle": True,
            "raw_map_r2_excluded_when_template_r2_at_least": config[
                "template_dominance_threshold"
            ],
            "production_specification_available": False,
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    plot_decomposition_atlas(
        rows,
        wafers,
        lots,
        metrics,
        args.figure_dir / "target-decomposition-atlas.png",
        representative_wafer=config["representative_wafer"],
        primary_target=config["primary_target"],
    )
    plot_measurement_provenance(
        dense,
        args.figure_dir / "measurement-provenance.png",
    )


if __name__ == "__main__":
    main()

"""Run the complete ETCH-GATE analysis from immutable released inputs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from etch_gate.manifests import build_manifest, sha256_file, write_manifest


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]
    result_dir: Path
    expected_results: list[Path]
    config: Path | None
    gate: str
    claim_boundaries: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--figure-root", type=Path, required=True)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore matching step cache metadata and rerun every step.",
    )
    return parser.parse_args()


def _cache_key(step: Step, raw_inputs: list[Path]) -> dict[str, object]:
    files = [Path(step.command[1]), *raw_inputs]
    if step.config is not None:
        files.append(step.config)
    return {
        "command": step.command,
        "sha256": {str(path): sha256_file(path) for path in files},
    }


def _run_step(step: Step, raw_inputs: list[Path], *, force: bool) -> str:
    step.result_dir.mkdir(parents=True, exist_ok=True)
    cache_path = step.result_dir / f".reproduction_cache_{step.name}.json"
    key = _cache_key(step, raw_inputs)
    if (
        not force
        and cache_path.is_file()
        and json.loads(cache_path.read_text(encoding="utf-8")) == key
        and all(path.is_file() for path in step.expected_results)
    ):
        return "REUSED"
    started = perf_counter()
    subprocess.run(step.command, check=True)
    runtime = perf_counter() - started
    config = (
        json.loads(step.config.read_text(encoding="utf-8"))
        if step.config is not None
        else {}
    )
    manifest = build_manifest(
        analysis=step.name,
        input_files=raw_inputs,
        config=config,
        random_seed=config.get("random_seed"),
        split_identifiers=[
            str(config.get("outer_split", config.get("split", "descriptive")))
        ],
        runtime_seconds=runtime,
        result_files=step.expected_results,
        claim_boundaries=step.claim_boundaries,
        gate=step.gate,
    )
    write_manifest(
        step.result_dir / f"reproduction_manifest_{step.name}.json",
        manifest,
    )
    cache_path.write_text(json.dumps(key, indent=2), encoding="utf-8")
    return "RAN"


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    # netCDF4/HDF5 on Windows can fail on a Unicode-containing absolute path.
    # Preserve caller-relative data paths while subprocesses inherit the repo cwd.
    data_dir = args.data_dir
    output_root = args.output_root
    figure_root = args.figure_root / "reproduction"
    output_root.mkdir(parents=True, exist_ok=True)
    figure_root.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    raw_inputs = [
        data_dir / "Process_data.nc",
        data_dir / "Dictionary_process.nc",
        data_dir / "Si_Oxide_etch_89_points.csv",
    ]
    missing = [str(path) for path in raw_inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"required released inputs are missing: {missing}")

    def script(name: str) -> str:
        return str(root / "scripts" / name)

    def config(name: str) -> Path:
        return root / "configs" / "analysis" / name

    steps = [
        Step(
            "data_audit",
            [
                python,
                script("audit_bosch_data.py"),
                "--data-dir",
                str(data_dir),
                "--output",
                str(output_root / "data_audit/bosch_audit.json"),
            ],
            output_root / "data_audit",
            [output_root / "data_audit/bosch_audit.json"],
            None,
            "PASS",
            ["released-file integrity and provenance only"],
        ),
        Step(
            "cycle_validation",
            [
                python,
                script("run_cycle_validation.py"),
                "--data-dir",
                str(data_dir),
                "--config",
                str(config("cycle_validation.json")),
                "--output-dir",
                str(output_root / "cycle_validation"),
                "--figure-dir",
                str(figure_root / "cycle_validation"),
                "--report",
                str(output_root / "cycle_validation/report.md"),
            ],
            output_root / "cycle_validation",
            [output_root / "cycle_validation/manifest.json"],
            config("cycle_validation.json"),
            "PASS",
            ["segmentation consistency, not plasma chemistry"],
        ),
        Step(
            "target_template",
            [
                python,
                script("analyze_etch_targets.py"),
                "--data",
                str(data_dir / "Si_Oxide_etch_89_points.csv"),
                "--config",
                str(config("etch_target_template.json")),
                "--output-dir",
                str(output_root / "target_template"),
                "--figure-dir",
                str(figure_root / "target_template"),
            ],
            output_root / "target_template",
            [output_root / "target_template/manifest.json"],
            config("etch_target_template.json"),
            "DESCRIPTIVE",
            ["true mean-shift rows are oracle diagnostics"],
        ),
        Step(
            "process_baseline",
            [
                python,
                script("run_process_baseline.py"),
                "--data-dir",
                str(data_dir),
                "--config",
                str(config("process_baseline.json")),
                "--output-dir",
                str(output_root / "process_baseline"),
                "--figure-dir",
                str(figure_root / "process_baseline"),
            ],
            output_root / "process_baseline",
            [output_root / "process_baseline/manifest.json"],
            config("process_baseline.json"),
            "PASS",
            ["LOLO is domain generalization, not forward deployment"],
        ),
        Step(
            "model_benchmark",
            [
                python,
                script("analyze_model_benchmark.py"),
                "--result-dir",
                str(output_root / "process_baseline"),
                "--figure-path",
                str(figure_root / "process_baseline/model-benchmark-dashboard.png"),
            ],
            output_root / "process_baseline",
            [output_root / "process_baseline/model_benchmark_audit.json"],
            config("process_baseline.json"),
            "PASS",
            ["GPR raw variance is not calibrated uncertainty"],
        ),
        Step(
            "feature_ablation",
            [
                python,
                script("run_feature_ablation.py"),
                "--data-dir",
                str(data_dir),
                "--config",
                str(config("feature_ablation.json")),
                "--output-dir",
                str(output_root / "feature_ablation"),
                "--figure-dir",
                str(figure_root / "feature_ablation"),
                "--report",
                str(output_root / "feature_ablation/report.md"),
            ],
            output_root / "feature_ablation",
            [output_root / "feature_ablation/manifest.json"],
            config("feature_ablation.json"),
            "DESCRIPTIVE",
            ["feature association is not causal mechanism identification"],
        ),
        Step(
            "spatial_decomposition",
            [
                python,
                script("run_spatial_decomposition.py"),
                "--data-dir",
                str(data_dir),
                "--config",
                str(config("spatial_decomposition.json")),
                "--output-dir",
                str(output_root / "spatial_decomposition"),
                "--figure-dir",
                str(figure_root / "spatial_decomposition"),
                "--report",
                str(output_root / "spatial_decomposition/report.md"),
            ],
            output_root / "spatial_decomposition",
            [output_root / "spatial_decomposition/summary.json"],
            config("spatial_decomposition.json"),
            "PASS",
            ["oracle stages are not deployable"],
        ),
        Step(
            "chronological_vm",
            [
                python,
                script("run_chronological_vm.py"),
                "--data-dir",
                str(data_dir),
                "--config",
                str(config("chronological_vm.json")),
                "--output-dir",
                str(output_root / "chronological_vm"),
                "--figure-dir",
                str(figure_root / "chronological_vm"),
                "--report",
                str(output_root / "chronological_vm/report.md"),
            ],
            output_root / "chronological_vm",
            [output_root / "chronological_vm/summary.json"],
            config("chronological_vm.json"),
            "PASS",
            ["forward performance is reported separately from LOLO"],
        ),
        Step(
            "uncertainty_calibration",
            [
                python,
                script("run_uncertainty_calibration.py"),
                "--data-dir",
                str(data_dir),
                "--config",
                str(config("uncertainty_calibration.json")),
                "--output-dir",
                str(output_root / "uncertainty_calibration"),
                "--figure-dir",
                str(figure_root / "uncertainty_calibration"),
                "--report",
                str(output_root / "uncertainty_calibration/report.md"),
            ],
            output_root / "uncertainty_calibration",
            [output_root / "uncertainty_calibration/manifest.json"],
            config("uncertainty_calibration.json"),
            "FAIL",
            ["failed intervals are excluded from routing"],
        ),
        Step(
            "risk_audit",
            [
                python,
                script("run_drift_risk.py"),
                "--data-dir",
                str(data_dir),
                "--baseline-dir",
                str(output_root / "process_baseline"),
                "--config",
                str(config("drift_risk.json")),
                "--output-dir",
                str(output_root / "risk_audit"),
                "--figure-dir",
                str(figure_root / "risk_audit"),
            ],
            output_root / "risk_audit",
            [output_root / "risk_audit/manifest.json"],
            config("drift_risk.json"),
            "FAIL",
            ["static ranking audit is not an online adaptive policy"],
        ),
        Step(
            "causal_replay",
            [
                python,
                script("run_causal_selective_metrology.py"),
                "--data-dir",
                str(data_dir),
                "--config",
                str(config("causal_replay.json")),
                "--output-dir",
                str(output_root / "causal_replay"),
                "--figure-dir",
                str(figure_root / "causal_replay"),
                "--report",
                str(output_root / "causal_replay/report.md"),
            ],
            output_root / "causal_replay",
            [output_root / "causal_replay/manifest.json"],
            config("causal_replay.json"),
            "FAIL",
            ["oracle is not deployable; direct measurement is treated as exact"],
        ),
    ]

    statuses = {}
    for step in steps:
        statuses[step.name] = _run_step(step, raw_inputs, force=args.force)

    subprocess.run(
        [
            python,
            script("verify_claims.py"),
            "--repo-root",
            str(root),
            "--output-dir",
            str(output_root / "claim_audit"),
        ],
        check=True,
    )
    summary = {
        "steps": statuses,
        "raw_input_sha256": {str(path): sha256_file(path) for path in raw_inputs},
        "claim_audit": "PASS",
    }
    (output_root / "reproduction_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

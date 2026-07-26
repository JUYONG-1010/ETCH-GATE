"""Reproducible result-manifest construction and validation."""

from __future__ import annotations

import hashlib
import json
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

PACKAGE_NAMES = (
    "etch-gate",
    "numpy",
    "pandas",
    "scipy",
    "scikit-learn",
    "matplotlib",
    "netCDF4",
)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file without loading large raw inputs into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def package_versions() -> dict[str, str]:
    """Return versions of the runtime packages relevant to this project."""

    versions = {}
    for package in PACKAGE_NAMES:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def build_manifest(
    *,
    analysis: str,
    input_files: list[Path],
    config: dict[str, Any],
    random_seed: int | None,
    split_identifiers: list[str],
    runtime_seconds: float,
    result_files: list[Path],
    claim_boundaries: list[str],
    gate: str,
) -> dict[str, Any]:
    """Build a validated, machine-readable reproduction manifest."""

    missing_inputs = [str(path) for path in input_files if not path.is_file()]
    missing_results = [str(path) for path in result_files if not path.is_file()]
    if missing_inputs or missing_results:
        raise FileNotFoundError(
            f"manifest files missing: inputs={missing_inputs}, results={missing_results}"
        )
    if gate not in {"PASS", "QUALIFIED", "FAIL", "DESCRIPTIVE"}:
        raise ValueError(f"unsupported gate status: {gate}")
    return {
        "analysis": analysis,
        "input_files": {
            str(path): {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in input_files
        },
        "config": config,
        "python_version": platform.python_version(),
        "package_versions": package_versions(),
        "random_seed": random_seed,
        "split_identifiers": split_identifiers,
        "runtime_seconds": runtime_seconds,
        "result_files": [str(path) for path in result_files],
        "claim_boundaries": claim_boundaries,
        "gate": gate,
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Write a manifest atomically enough for a single-process reproduction run."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

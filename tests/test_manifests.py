from pathlib import Path

from etch_gate.manifests import build_manifest


def test_manifest_contains_reproduction_contract(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    result = tmp_path / "result.csv"
    source.write_text("x\n1\n", encoding="utf-8")
    result.write_text("metric\n0.1\n", encoding="utf-8")

    manifest = build_manifest(
        analysis="synthetic",
        input_files=[source],
        config={"alpha": 1},
        random_seed=7,
        split_identifiers=["train=lot1", "test=lot2"],
        runtime_seconds=0.1,
        result_files=[result],
        claim_boundaries=["synthetic only"],
        gate="PASS",
    )

    required = {
        "input_files",
        "config",
        "python_version",
        "package_versions",
        "random_seed",
        "split_identifiers",
        "runtime_seconds",
        "result_files",
        "claim_boundaries",
        "gate",
    }
    assert required <= set(manifest)
    assert manifest["input_files"][str(source)]["sha256"]

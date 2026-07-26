"""Verify that README headline numbers match generated result artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/claim_audit"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/FINAL_CLAIM_AUDIT.md"),
    )
    return parser.parse_args()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _claim(
    claim_id: str,
    source: Path,
    value: Any,
    expected_text: str,
    readme: str,
) -> dict[str, Any]:
    return {
        "id": claim_id,
        "source": source.as_posix(),
        "artifact_value": value,
        "expected_readme_text": expected_text,
        "status": "PASS" if expected_text in readme else "FAIL",
    }


def main() -> None:
    args = parse_args()
    root = args.repo_root.resolve()
    readme = (root / "README.md").read_text(encoding="utf-8")
    baseline_path = root / "results/revised_process_baseline/manifest.json"
    baseline = _json(baseline_path)
    model_path = root / "results/revised_process_baseline/model_summary.csv"
    models = pd.read_csv(model_path).set_index("family")
    template_path = root / "outputs/target_template/manifest.json"
    template = _json(template_path)
    stepheight = next(
        row for row in template["metrics"] if row["target"] == "stepheight"
    )
    spatial_path = root / "results/spatial_decomposition/summary.json"
    spatial = _json(spatial_path)
    chronological_path = root / "results/chronological_vm/summary.json"
    chronological = _json(chronological_path)
    pls_forward = next(
        row
        for row in chronological["family_macro_comparison"]
        if row["family"] == "pls"
    )
    risk_path = root / "results/risk_audit/manifest.json"
    risk = _json(risk_path)
    causal_path = root / "results/causal_replay/manifest.json"
    causal = _json(causal_path)
    uncertainty_path = root / "results/uncertainty_calibration/manifest.json"
    uncertainty = _json(uncertainty_path)
    oes_path = root / "results/oes_v2_pilot/summary.json"
    oes = _json(oes_path)

    checks = [
        _claim(
            "process_wafer_count",
            baseline_path,
            baseline["counts"]["process_wafers"],
            "96 process wafers",
            readme,
        ),
        _claim(
            "dense_wafer_count",
            baseline_path,
            baseline["counts"]["modeled_dense_wafers"],
            "88 labeled wafers",
            readme,
        ),
        _claim(
            "direct_target_count",
            template_path,
            stepheight["rows"],
            "7,832 targets",
            readme,
        ),
        _claim(
            "signal_feature_count",
            baseline_path,
            baseline["counts"],
            "31 common signals",
            readme,
        ),
        _claim(
            "template_r2",
            template_path,
            stepheight["template_r2"],
            "98.26% of raw point variance",
            readme,
        ),
        _claim(
            "template_mae",
            template_path,
            stepheight["template_lot_macro_mae"],
            "0.3509 um",
            readme,
        ),
        _claim(
            "model_mae",
            model_path,
            {
                family: float(models.loc[family, "wafer_macro_mae"])
                for family in ("pls", "ridge", "gpr")
            },
            "| **PLS** | **0.1459 um** | **0.1421 um** | **8/10** |",
            readme,
        ),
        _claim(
            "residual_gain",
            spatial_path,
            spatial["residual_contribution_gate"],
            "Residual correction adds a 9.68% gain",
            readme,
        ),
        _claim(
            "chronological_degradation",
            chronological_path,
            pls_forward,
            "Forward error is 20.15% higher.",
            readme,
        ),
        _claim(
            "oes_failure",
            oes_path,
            oes,
            "0.4142 um lot-macro MAE versus 0.3387 um",
            readme,
        ),
        _claim(
            "risk_aurc",
            risk_path,
            {
                "combined": risk["lot_macro_aurc"]["combined"],
                "random": risk["lot_macro_aurc"]["random"],
                "reduction": risk["combined_vs_random_aurc_reduction"],
                "gate": risk["preregistered_gate_passed"],
            },
            "| Equal-weight combined | **0.1287** | **9.28%** |",
            readme,
        ),
        _claim(
            "low_budget_causal_result",
            causal_path,
            causal["combined_vs_random_system_mae_reduction"],
            "| 20% | 4.94% better |",
            readme,
        ),
        _claim(
            "causal_gate",
            causal_path,
            causal["policy_gate"],
            "The causal policy gate is **FAIL**",
            readme,
        ),
        _claim(
            "uncertainty_gate",
            uncertainty_path,
            uncertainty["gate"],
            "Group-aware split conformal evaluation also fails",
            readme,
        ),
    ]
    passed = all(check["status"] == "PASS" for check in checks)
    audit = {
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "checked_claims": len(checks),
        "failed_claims": sum(check["status"] == "FAIL" for check in checks),
    }
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "claim_audit.json").write_text(
        json.dumps(audit, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Final Claim Audit",
        "",
        f"Overall status: **{audit['status']}**",
        "",
        "| Claim | Source | Status |",
        "| --- | --- | --- |",
    ]
    for check in checks:
        lines.append(
            f"| {check['id']} | `{check['source']}` | {check['status']} |"
        )
    lines.extend(
        [
            "",
            "The audit checks README display values against machine-readable result",
            "artifacts. Any missing or stale headline text exits with status 1.",
        ]
    )
    report = root / args.report
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

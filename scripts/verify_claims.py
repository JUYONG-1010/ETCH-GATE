"""Check README display values against the actual numeric result artifacts.

This is a consistency check, not an independent replication of model fitting.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify(root: Path, result_root: Path, *, skip_oes: bool = False) -> dict:
    root, result_root = root.resolve(), result_root.resolve()
    readme = (root / "README.md").read_text(encoding="utf-8")
    baseline_dir = result_root / "revised_process_baseline"
    if not baseline_dir.is_dir():
        baseline_dir = result_root / "process_baseline"
    baseline_path = baseline_dir / "manifest.json"
    counts = read_json(baseline_path)["counts"]
    template_path = result_root / "target_template/manifest.json"
    target = next(x for x in read_json(template_path)["metrics"] if x["target"] == "stepheight")
    model_path = baseline_dir / "model_summary.csv"
    models = pd.read_csv(model_path).set_index("family")
    lot_path = baseline_dir / "model_lot_metrics.csv"
    lot_mae = pd.read_csv(lot_path).groupby("family")["lot_mae"].mean()
    spatial_path = result_root / "spatial_decomposition/summary.json"
    spatial = read_json(spatial_path)["residual_contribution_gate"]
    chrono_path = result_root / "chronological_vm/summary.json"
    forward = next(x for x in read_json(chrono_path)["family_macro_comparison"]
                   if x["family"] == "pls")
    risk_path = result_root / "risk_audit/manifest.json"
    risk = read_json(risk_path)
    causal_path = result_root / "causal_replay/manifest.json"
    causal = read_json(causal_path)
    uncertainty_path = result_root / "uncertainty_calibration/manifest.json"
    uncertainty = read_json(uncertainty_path)
    checks = []

    def add(name, source, value, display, *, condition=True):
        # Numeric displays are derived from artifacts, never hard-coded expected numbers.
        finite = not isinstance(value, (float, int)) or math.isfinite(value)
        try:
            source_name = source.relative_to(root).as_posix()
        except ValueError:
            source_name = source.relative_to(result_root).as_posix()
        checks.append({
            "id": name, "source": source_name, "artifact_value": value,
            "expected_readme_text": display,
            "status": "PASS" if finite and condition and display in readme else "FAIL",
        })

    add("process_wafers", baseline_path, counts["process_wafers"],
        f'{counts["process_wafers"]} wafers')
    add("labeled_wafers", baseline_path, counts["modeled_dense_wafers"],
        f'{counts["modeled_dense_wafers"]} labeled wafers')
    add("target_points", template_path, target["rows"], f'{target["rows"]:,} targets')
    add("template_r2", template_path, target["template_r2"],
        f'{target["template_r2"]:.2%} of raw point variance')
    add("template_mae", template_path, target["template_lot_macro_mae"],
        f'| Other-lot template | {target["template_lot_macro_mae"]:.4f} um |')
    for family, label in (("pls", "**PLS**"), ("ridge", "Ridge"), ("gpr", "GPR")):
        row = models.loc[family]
        emphasis = "**" if family == "pls" else ""
        display = (f'| {label} | {emphasis}{row["wafer_macro_mae"]:.4f} um{emphasis} | '
                   f'{emphasis}{lot_mae[family]:.4f} um{emphasis} | '
                   f'{emphasis}{int(row["best_lots"])}/10{emphasis} |')
        add(f"{family}_mae", model_path, float(lot_mae[family]), display)
    gain = spatial["relative_residual_stage_gain"]
    add("residual_gain", spatial_path, gain, f"Residual correction adds a {gain:.2%} gain")
    degradation = forward["relative_degradation"]
    add("chronological_degradation", chrono_path, degradation,
        f"Forward error is {degradation:.2%} higher.")
    add("chronological_mae", chrono_path, forward["chronological_mae"],
        f'| Strict chronological | {forward["chronological_mae"]:.4f} um |')
    add("risk_aurc", risk_path, risk["lot_macro_aurc"]["combined"],
        f'| Equal-weight combined | **{risk["lot_macro_aurc"]["combined"]:.4f}** | '
        f'**{risk["combined_vs_random_aurc_reduction"]:.2%}** |',
        condition=risk["preregistered_gate_passed"] is False)
    for budget, gain in causal["combined_vs_random_system_mae_reduction"].items():
        direction = "better" if gain >= 0 else "worse"
        add(f"causal_budget_{budget}", causal_path, gain,
            f"| {float(budget):.0%} | {abs(gain):.2%} {direction} |")
    add("causal_gate", causal_path, causal["policy_gate"],
        f'The causal policy gate is **{causal["policy_gate"]}**')
    add("uncertainty_gate", uncertainty_path, uncertainty["gate"],
        "Group-aware split conformal evaluation also fails",
        condition=uncertainty["gate"] == "FAIL")
    if not skip_oes:
        oes_path = result_root / "oes_v2_pilot/summary.json"
        oes = read_json(oes_path)
        add("oes_negative_pilot", oes_path, oes["physics_constrained_lot_macro_mae"],
            f'{oes["physics_constrained_lot_macro_mae"]:.4f} um lot-macro MAE versus '
            f'{oes["process_only_lot_macro_mae"]:.4f} um',
            condition=oes["passes_retain_gate"] is False)
    failures = sum(c["status"] == "FAIL" for c in checks)
    return {"status": "FAIL" if failures else "PASS", "checked_claims": len(checks),
            "failed_claims": failures, "checks": checks,
            "scope": "README/result consistency, not a new model-training replication",
            "oes": "SKIPPED: separate historical pilot" if skip_oes else "CHECKED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--result-root", type=Path, default=Path("results"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/claim_audit"))
    parser.add_argument("--report", type=Path, default=Path("docs/FINAL_CLAIM_AUDIT.md"))
    parser.add_argument("--skip-oes", action="store_true")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    audit = verify(root, root / args.result_root, skip_oes=args.skip_oes)
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "claim_audit.json").write_text(
        json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Result Consistency Audit", "", f'Overall status: **{audit["status"]}**', "",
             audit["scope"] + ".", "", "| Claim | Source | Status |",
             "| --- | --- | --- |"]
    lines += [f'| {c["id"]} | `{c["source"]}` | {c["status"]} |' for c in audit["checks"]]
    lines += ["", "Display strings are calculated from artifact values.",
              "Missing files, non-finite values, or stale display values fail the check.",
              f'OES: {audit["oes"]}.', ""]
    report = root / args.report
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f'{audit["status"]}: {audit["checked_claims"]} claims, {audit["failed_claims"]} failures')
    if audit["failed_claims"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

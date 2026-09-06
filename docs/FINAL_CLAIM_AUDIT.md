# Result Consistency Audit

Overall status: **PASS**

README/result consistency, not a new model-training replication.

| Claim | Source | Status |
| --- | --- | --- |
| process_wafers | `results/revised_process_baseline/manifest.json` | PASS |
| labeled_wafers | `results/revised_process_baseline/manifest.json` | PASS |
| target_points | `results/target_template/manifest.json` | PASS |
| template_r2 | `results/target_template/manifest.json` | PASS |
| template_mae | `results/target_template/manifest.json` | PASS |
| pls_mae | `results/revised_process_baseline/model_summary.csv` | PASS |
| ridge_mae | `results/revised_process_baseline/model_summary.csv` | PASS |
| gpr_mae | `results/revised_process_baseline/model_summary.csv` | PASS |
| residual_gain | `results/spatial_decomposition/summary.json` | PASS |
| chronological_degradation | `results/chronological_vm/summary.json` | PASS |
| chronological_mae | `results/chronological_vm/summary.json` | PASS |
| risk_aurc | `results/risk_audit/manifest.json` | PASS |
| causal_budget_0.1 | `results/causal_replay/manifest.json` | PASS |
| causal_budget_0.2 | `results/causal_replay/manifest.json` | PASS |
| causal_budget_0.3 | `results/causal_replay/manifest.json` | PASS |
| causal_gate | `results/causal_replay/manifest.json` | PASS |
| uncertainty_gate | `results/uncertainty_calibration/manifest.json` | PASS |
| oes_negative_pilot | `results/oes_v2_pilot/summary.json` | PASS |

Display strings are calculated from artifact values.
Missing files, non-finite values, or stale display values fail the check.
OES: CHECKED.

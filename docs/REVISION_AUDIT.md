# ETCH-GATE Revision Audit

Audit date: 2026-07-26

Scope: historical repository state before the July 2026 validation revision.
The findings below describe that earlier snapshot, not current open issues.

## Resolution

All in-scope audit items were implemented and re-evaluated. Their final
scientific gate outcomes, including retained failures, are recorded in
`docs/FINAL_VALIDATION_REPORT.md`. The final `NOT RUN` audit contains no
in-scope items.

## Repository state

- Branch: `main`
- Baseline commit: `c9a2ed6`
- Raw process data: present (`Process_data.nc`, `Dictionary_process.nc`)
- Direct dense target: present (`Si_Oxide_etch_89_points.csv`)
- Downloaded OES days: four; existing negative OES results are retained
- Process wafers: 96
- Dense P-17 target wafers: 88 across 10 lots
- Common process channels: 31
- Existing tests before revision: 22 tests in 10 files
- Existing primary evaluations: nested LOLO process VM, model benchmark,
  retrospective risk-ranking audit, and two failed OES incrementality pilots

No raw input, existing result, negative experiment, commit, or remote branch is
modified by this audit.

## Findings

| ID | Problem | Severity | Evidence | Revision | Verification |
|---|---|---:|---|---|---|
| A01 | Actual-wafer cycle detection is not validated across all 96 traces. | High | `src/etch_gate/data/process.py`, synthetic-only tests | Add process-only cycle diagnostics and deterministic anomaly figures. | Actual-data finite/invariant tests and cycle result tables. |
| A02 | The current detector uses one quantile threshold and a fixed 3 s edge filter without reporting phase overlap, uncovered samples, or duration distributions. | High | `detect_process_regions` | Expose phase boundaries and complete diagnostics; compare complementary and duration/spacing rules without targets. | Cycle validation report and tests. |
| A03 | All 310 process features are evaluated together, so phase/cycle contribution is unproven. | High | `evaluate_process_baselines` inputs | Add fixed cumulative feature-group ablation on identical nested splits. | Ablation tables, fold metrics, VIP/stability analysis. |
| A04 | Full-map improvement is not fully decomposed into deployable mean-shift gain, residual correction, and oracle upper bounds. | High | process benchmark artifacts | Add stage metrics, spatial-zone metrics, per-coordinate errors, and lot-cluster residual-gain interval. | Decomposition result and frozen gate. |
| A05 | Nested LOLO uses future lots and therefore does not represent strict forward deployment. | Critical | `evaluate_process_baselines` | Add expanding-window chronological evaluation with all transforms fitted on history only. | Split invariants and held-out-target perturbation tests. |
| A06 | Raw GPR variance is not calibrated uncertainty. | High | model benchmark and README boundary | Evaluate group-aware conformal pointwise and simultaneous intervals or withdraw the claim. | Coverage-width artifacts and gate. |
| A07 | First-wafer delta/EWMA scores are distances from a zero vector and EWMA alpha is hard-coded. | Critical | `src/etch_gate/analysis/drift.py` | Separate initial-state distance, undefined first delta/EWMA, and use the configured alpha. | Unit tests and rerun risk audit. |
| A08 | The ranking result may be dominated by Lot 8 and has no matched lot-cluster interval. | High | drift-risk artifacts | Add leave-one-lot influence, Lot 8 exclusion, bootstrap, and small-lot resolution. | Robustness artifacts. |
| A09 | Selected wafers are only removed from retained-risk scoring; no direct-result substitution or causal feedback exists. | Critical | drift implementation and README | Implement frozen, bias-update, and mean-refit online replay with causal budget control. | Future-target perturbation test and policy gate. |
| A10 | Common model/decomposition helpers are imported as private functions. | Medium | `drift.py` imports `_fit_regressor`, `_decompose_maps` | Promote stable public APIs while preserving regression outputs. | Unit/regression tests. |
| A11 | No CI workflow, single-command reproduction runner, or complete result manifest contract exists. | High | repository tree | Add synthetic CI, resumable reproduction entrypoint, and manifest utilities. | Ruff, pytest, and miniature integration run. |
| A12 | README headline metrics are manually maintained and not artifact-audited. | High | `README.md` | Generate/verify a claim source after all experiments and reduce unsupported language. | `verify_claims.py` exits nonzero on mismatch. |
| A13 | README currently gives the failed OES work more prominence than its final role warrants. | Medium | `README.md` | Retain negative result but reduce it to an incrementality summary. | Final claim audit. |
| A14 | Public claims do not yet distinguish LOLO generalization, chronological deployment, ranking-only audit, and causal replay gates. | High | `README.md`, protocols | Reframe title and claims only after gates are evaluated. | Final 10/10 table and claim audit. |

## Reproducibility blockers

- Several required analyses and their configs do not yet exist.
- Existing manifests do not share one complete schema.
- Raw data are intentionally absent from CI, but there is no synthetic
  end-to-end replacement.
- The public README has no automated connection to result artifacts.

## Claim boundaries during revision

Until the new gates run, the repository may claim only:

1. nested lot-aware process-trace VM performance already supported by artifacts;
2. a retrospective target-free failure-risk ranking audit;
3. negative OES incremental-value results.

It must not yet claim chronological deployment validity, calibrated
uncertainty, adaptive metrology, closed-loop sampling, or causal feedback
benefit.

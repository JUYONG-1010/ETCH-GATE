# ETCH-GATE Final Validation Report

## 1. Existing State

The original repository reported a strong nested LOLO PLS result and a static
risk-ranking gain. The revision audit found four high-impact claim risks:

- the selected cycle detector was not used by the baseline runner;
- LOLO performance was presented more prominently than strict forward
  deployment performance;
- the first wafer of every lot was compared with a zero vector for delta/EWMA;
- static ranking removal was not a causal online measurement replay.

OES pilots already failed their unseen-lot gates and were correctly retained
as negative results.

## 2. Changed Files

| Path | Reason and key change |
| --- | --- |
| `README.md`, `PROJECT_LOG.md` | Replaced unsupported narrative with artifact-backed results, limitations, figures, and a complete revision log. |
| `docs/REVISION_AUDIT.md` | Recorded the pre-revision repository, critical findings, scope, and final resolution link. |
| `docs/*_RESULTS.md`, `docs/FINAL_CLAIM_AUDIT.md` | Added experiment-specific methods, metrics, gates, and negative-result records. |
| `docs/figures/{cycle_validation,feature_ablation,spatial_decomposition,chronological_vm,risk_audit,causal_replay,uncertainty_calibration,revised_process_baseline,reproduction}/` | Added the publication/README figures generated from result artifacts. |
| `src/etch_gate/data/process.py` | Added validated cycle-detector modes, region diagnostics, and boundary checks. |
| `src/etch_gate/analysis/{cycle_validation,feature_ablation,spatial_decomposition,chronological,uncertainty_calibration,causal_replay}.py` | Added the six required validation and replay analyses. |
| `src/etch_gate/analysis/drift.py` | Corrected first-wafer handling and EWMA; added proxy correlation, inner-lot weighting, influence, bootstrap, and exact small-lot audits. |
| `src/etch_gate/analysis/process_baseline.py` | Promoted reusable model APIs and added table/map validation. |
| `src/etch_gate/analysis/oes_v2.py` | Replaced cross-module private imports with validated public APIs. |
| `src/etch_gate/statistics.py`, `src/etch_gate/manifests.py` | Centralized deterministic lot bootstrap and reproducibility manifests with SHA256/package metadata. |
| `src/etch_gate/visualization/*.py` | Added or revised experiment figures, including wafer maps in major result panels. |
| `configs/analysis/*.json` | Added fixed experiment configurations and made the complementary cycle detector explicit. |
| `scripts/run_{cycle_validation,feature_ablation,spatial_decomposition,chronological_vm,uncertainty_calibration,causal_selective_metrology}.py` | Added reproducible experiment entry points. |
| `scripts/run_{process_baseline,drift_risk}.py` | Applied corrected configuration and expanded artifact output. |
| `scripts/run_full_reproduction.py`, `scripts/verify_claims.py` | Added raw-input one-command execution, caching, manifests, and README claim verification. |
| `tests/test_*.py` | Added unit, leakage, regression, bootstrap, manifest, and miniature end-to-end tests. |
| `.github/workflows/ci.yml`, `pyproject.toml` | Added Python 3.10/3.11 Ruff and pytest CI. |
| `.gitignore` | Excluded duplicated local full-reproduction output while retaining canonical result artifacts. |
| `results/{cycle_validation,feature_ablation,spatial_decomposition,chronological_vm,uncertainty_calibration,risk_audit,causal_replay,revised_process_baseline,claim_audit,final_validation}/` | Stored canonical machine-readable experiment outputs. |

Section 17 employment/interview artifacts were explicitly excluded by the
user. The preexisting untracked `scripts/create_final_paper.py` was preserved
unchanged and excluded from Ruff because it is in that scope.

## 3. Executed Commands

```text
python scripts/run_full_reproduction.py --data-dir data/bosch_raw \
  --output-root results/reproduction --figure-root docs/figures
python scripts/run_full_reproduction.py --data-dir data/bosch_raw \
  --output-root results/reproduction --figure-root docs/figures
python -m ruff check .
python -m pytest -q
python scripts/verify_claims.py
git diff --check
git status --short
```

The first reproduction executed every stage from raw inputs in about 7 minutes
56 seconds. The second reused all 11 stages after input, configuration, script,
and artifact checks matched.

## 4. Verification Results

| Check | Status | Evidence |
| --- | --- | --- |
| Ruff | PASS | all checks passed |
| Pytest | PASS | 41/41 tests |
| Data audit | PASS | 96 process wafers; 88 direct-map wafers; provenance recorded |
| Cycle validation | PASS | 96/96 wafers; 99-100 cycles; no overlap/uncovered active samples |
| Nested LOLO | PASS | all transforms, templates, PCA, and tuning fitted inside training lots |
| Chronological | PASS | expanding-window Lots 4-10; no future-lot access |
| Feature ablation | PASS | four cumulative feature groups plus fold-wise stability |
| Spatial decomposition | PASS | five required stages and residual contribution gate |
| Uncertainty audit | PASS | calibration tested; deployment claim withdrawn after failed gate |
| Risk audit | PASS | bugs, redundancy, weighting, Lot 8, bootstrap, and resolution audited |
| Causal replay | PASS | ranking, substitution, F0-F3 feedback, and future-target leakage test |
| Claim audit | PASS | 14/14 README claims match artifacts |
| Clean reproduction | PASS | 11/11 stages executed, then 11/11 reused |

The 24 pytest warnings come from intentionally degenerate synthetic fixtures
with zero PCA variance or constant PLS target residuals. No actual-data stage,
leakage assertion, or regression test failed.

## 5. Key Metrics

| Experiment | Result |
| --- | --- |
| PLS LOLO full-map | 0.1421 um lot-macro MAE |
| Ridge / GPR LOLO | 0.1551 / 0.1666 um lot-macro MAE |
| Residual correction | 9.68% gain, 95% CI 7.03%-12.66%, 10/10 lots |
| Strict-forward PLS | 0.1737 um vs eligible LOLO 0.1446 um, 20.15% degradation |
| Feature ablation | level-only 0.1328; all-feature 0.1421 um |
| Static combined risk | AURC 0.1287 vs Random 0.1419, 9.28% reduction |
| Risk bootstrap | policy-minus-Random CI [-0.0310, 0.0017] |
| Causal 10/20/30% | +1.89%, +4.94%, -2.12% vs Random |
| Bias feedback F1 | mean 0.97% gain vs frozen F0 |
| Conformal 95% | point 88.87%, map 98.57%, 0/7 lots attain requested rank |
| Compact OES V2 | 0.4142 vs process-only 0.3387 um; 1/4 lots improved |

## 6. Failed Experiments

| Gate | Status | Reason |
| --- | --- | --- |
| Static risk ranking | FAIL | 9.28% is below 10%; bootstrap interval crosses zero |
| Causal selective metrology | FAIL | low lot-win rate, interval crosses zero, and Lot 8 dependence |
| Uncertainty calibration | FAIL | undercoverage, excessive width, unstable lots, and insufficient resolution |
| OES incremental value | FAIL | both fusion designs worsen matched unseen-lot performance |

These failures are retained as results; they are not hidden, retuned, or
promoted into deployment claims.

## 7. Final Supported Claim

On this 88-wafer direct-map dataset, training-lot-only PLS predicts unseen-lot
stepheight maps substantially better than a coordinate template, and spatial
residual correction adds a statistically stable 9.68% improvement after mean
shift prediction. Strict-forward performance is 20.15% worse than LOLO, while
static risk ranking, causal routing, uncertainty calibration, and OES
incremental value do not pass their final gates.

## 8. Forbidden Claims

- production-ready VM, wafer disposition, yield gain, or cost saving;
- calibrated GPR uncertainty or validated OOC control limits;
- adaptive selective-metrology superiority;
- OES endpoint detection, chemical mechanism, or improved VM;
- specific hardware-fault diagnosis or causal chamber explanation;
- traceable P-17/Dektak physical calibration.

## 9. Remaining Limitations

- Only 88 dense-target wafers and 10 lots are available.
- Calibration lots contain only 6-10 wafers.
- No specification, yield, maintenance, delay, cost, or gauge R&R record is
  released.
- Date, lot, conditioning, and unobserved maintenance may be confounded.
- Direct metrology is treated as exact and immediate in replay.
- GPR optimization repeatedly reaches the configured noise lower bound.

## 10. Git Status And NOT RUN Audit

The worktree contains the intended modified and new research files. Nothing is
staged, committed, or pushed. Generated `results/reproduction/` duplicates are
locally retained but ignored; canonical results remain visible to Git.

All 21 evaluation areas in master-prompt Section 18 were assessed. Scientific
gates that failed are recorded above rather than marked incomplete.

| Evaluation area | Completion assessment |
| --- | --- |
| Problem definition | PASS |
| Data provenance | PASS |
| Cycle detection | PASS |
| Feature engineering | PASS |
| Model comparison | PASS |
| Spatial prediction | PASS |
| Leakage prevention | PASS |
| Chronological evaluation | PASS |
| Uncertainty | QUALIFIED: gate failed and claim withdrawn |
| Risk ranking | PASS: defects corrected; policy gate failed |
| Selective metrology | QUALIFIED: causal replay complete; policy gate failed |
| Low-budget value | PASS: 10-30% separately reported |
| Robustness | PASS |
| Statistics | PASS |
| OES | QUALIFIED: negative result retained |
| Code | PASS |
| Tests | PASS |
| CI | PASS |
| Reproduction | PASS |
| Claim audit | PASS |
| Communication | QUALIFIED: Section 17 excluded by request |

`NOT RUN` items: **none**.

Explicitly excluded, not NOT RUN: Section 17 employment/interview deliverables.

# Validation Record

## Historical model evaluation

The July 2026 analysis produced the committed experiment results. These are
offline research results, not production qualification.

| Evaluation | Outcome |
| --- | --- |
| Nested LOLO PLS | Lot-macro MAE 0.1421 um, template baseline 0.3509 um |
| Residual shape after mean prediction | 9.68% relative gain |
| Strict chronological PLS | MAE 0.1737 um; 20.15% worse than eligible-lot LOLO |
| Static risk ranking | 9.28% AURC reduction; preregistered gate failed |
| Causal selective metrology | Policy gate failed |
| Conformal uncertainty | Calibration gate failed |
| Compact OES pilot | Incremental-value gate failed |

The historical full reproduction record is separate from the September repository
audit. The September audit checks code, synthetic tests and committed numerical
consistency; it does not claim a fresh full-data rerun of all model fits.

## Public reproducibility corrections

The initial claim checker only searched hard-coded README strings and required
an uncommitted template manifest. That was insufficient numeric verification.
The manifest is now included and display values are computed from result files.

Full reproduction now points the checker at its newly generated output directory.
OES is explicitly skipped in that process-only run, rather than mixing a
historical OES result into a fresh verification. Cached steps check source and
result hashes. Missing temporary fixture directories are created by tests.

See [current consistency audit](FINAL_CLAIM_AUDIT.md) for executable checks.

## Interpretation boundaries

There are only 88 labeled wafers and 10 lots. Spatial points are not independent
wafers. LOLO can train on later lots, whereas chronological evaluation cannot.
Direct metrology is treated as exact and immediate in replay. No production
specification, yield, maintenance or gauge R&R record is released.

Failed scientific gates are retained. The project does not establish
production-ready VM, calibrated routing uncertainty, selective-metrology
superiority, OES endpoint detection, fault causality or manufacturing savings.

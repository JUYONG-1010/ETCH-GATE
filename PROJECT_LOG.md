# Experiment History

This log records the ETCH-GATE research sequence. Detailed numerical results
remain in the linked reports and machine-readable result files.

## Dataset and target audit
- Audited the released BOSCH process traces and measurement provenance.
- Identified 96 process wafers and 88 wafers with direct 89-point stepheight.
- Distinguished direct stepheight from interpolated or derived oxide targets.
- Established an other-lot coordinate-template baseline.

## Process virtual metrology
- Compared Ridge, PLS and GPR under nested leave-one-lot-out evaluation.
- Retained PLS; separated template, wafer mean shift and residual-shape gains.
- Tested process feature groups rather than assuming phase features add value.

## Negative OES pilots
- Tested process/OES fusion and compact normalized OES features.
- Neither pilot passed the incremental-value gate. OES is not in the final VM.

## July 2026 validation revision
- Validated cycle segmentation on all process wafers.
- Added strict chronological evaluation and documented degradation versus LOLO.
- Corrected first-wafer drift handling and audited Lot 8 sensitivity.
- Evaluated conformal intervals and chronological selective-metrology replay.
- Retained failed uncertainty, risk-ranking and causal-policy gates.

See [historical revision audit](docs/REVISION_AUDIT.md) and
[validation report](docs/FINAL_VALIDATION_REPORT.md).

## September 2026 repository audit
- Removed unrelated project notes and workstation-specific instructions.
- Restored the original target-template manifest needed by the public audit.
- Made README consistency checks derive display values from numeric artifacts.
- Made reproduction audit newly generated results, not the canonical snapshot.
- Added source/result cache checks and fixed fresh-checkout fixture creation.
- Corrected a reversed metric key: values are random MAE minus combined MAE
  without Lot 8. Negative values mean combined is worse; values did not change.

These changes do not turn failed scientific gates into successful experiments.

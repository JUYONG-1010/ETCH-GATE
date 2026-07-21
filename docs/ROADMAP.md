# ETCH-GATE Roadmap

## Milestone 0 - Specification and Migration

Freeze claims, RQs, target decomposition, leakage rules, gates, prior-work
table, and migration plan. No model code. Pass when all protocol documents are
internally consistent and sources resolve.

## Milestone 1 - Source Data Audit

Parse the eight small files, reproduce counts/keys/coordinates/missingness,
validate 9/89 pairing as a measurement-system audit, and produce lineage
visuals. Do not download full OES.

## Milestone 2 - Target and Template Audit

Quantify `T`, `M`, and `R` inside leave-one-lot-out folds. Separate direct,
filled, and interpolated measurements. Exclude raw map R2 from headlines when
template R2 is at least 0.95.

## Milestone 3 - Process-Only Baselines

Implement lot-aware simple baselines before complex models. Freeze metrics and
splits. No OES yet. **Completed:** nested LOLO PLS reduced wafer-mean MAE from
0.3520 to 0.1435 um, improved nine of ten lots over the template, and improved
all ten lots over the mean-shift-only stage.

## Milestone 4 - Drift and Failure-Aware VM

Use only information available by each wafer's process end to test
wafer-order deltas, change-point scores, model uncertainty, and
out-of-training-distribution indicators. Conditioning is used for stratified
reporting, not as a primary predictor, because conditions are confounded with
only ten date/lots. The goal is to flag Lot 8 type failures without using
dense test outcomes.

**Preregistered evaluation:** compare target-free risk scores with repeated
Random at identical full-metrology fractions. The equal-weight combined score
must reduce lot-macro retained-risk AUC by at least 10% and improve at least
seven of ten held-out lots. EWMA is a relative score only, not an OOC limit;
Ridge/PLS disagreement is not calibrated uncertainty.

**Completed with qualification:** the combined score reduced lot-macro AURC
by 11.7% and improved nine of ten lots, passing the frozen aggregate gate.
At 10%-30% requested metrology, however, improvement was only 2.6%-6.3% and
OOD alone was stronger. This is evidence of ranking signal, not a finished
low-budget policy.

## Milestone 5 - One-Day OES Gate

Download one daily OES file, validate dictionary decoding and cycle alignment,
then test fold-local OES features. Download all OES only after a credible
process-only improvement signal; retain OES as secondary if gain is below 5%.

## Milestone 6 - Calibrated Uncertainty

Evaluate point-wise and simultaneous intervals with a separate calibration
lot. Withdraw the claim if coverage or width gates fail.

## Milestone 7 - Same-Tool Sparse and Selective Metrology

First simulate sparse sampling by exposing only the nine matching coordinates
from the same P-17 dense session, clearly labeled as retrospective. Then
compare target-free full-metrology policies against repeated Random and
oracle. Separate ranking-only removal from direct-result substitution and a
causal feedback model that can use only previously measured wafers. Reject any
policy that misses its 10% AURC-improvement gate. Actual
Dektak/P-17 fusion remains out of scope.

## Milestone 8 - Reproduction and Portfolio

Run clean-environment tests, Ruff, checksum and claim audits, create final
publication-quality figures, then commit and push once after user approval.

## Global Rule

Advance one milestone at a time. Failed experiments remain documented.
No milestone or claim changes until `INDUSTRY_ALIGNMENT.md` records a primary
source, dataset support, leakage-safe comparison, numerical gate, and allowed
claim.

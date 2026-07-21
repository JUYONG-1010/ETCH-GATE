# ETCH-GATE Project Specification

## Scope

ETCH-GATE is an offline, lot-aware study of template-residual virtual
metrology, chamber-drift failure detection, and selective full-metrology
simulation for BOSCH plasma etching.

The required decomposition is:

\[
Y(w,p)=T(p)+M(w)+R(w,p)
\]

- `T(p)`: fixed spatial template estimated from training lots only.
- `M(w)`: wafer-level global mean shift.
- `R(w,p)`: wafer-specific residual spatial profile.

## Confirmed Facts

The official dataset provides OES, process traces, lot metadata, 9-point and
89-point wafer measurements, and a wafer-layout document. OES has 3,648
channels at 25 Hz; process variables are sampled at 5 Hz. The source is a
research facility and is licensed CC BY 4.0.

## Verified Structure

The audit reproduced 96 process wafers, 88 dense wafers, 73 identified paired
9/89-point wafers, 10 lots, 89 dense coordinates, 31 common process variables,
and 157 released post-etch IDW replacements. Stepheight and silicon-etch maps
are template-dominant under leave-one-lot-out evaluation; oxide etch is not.

## Hypotheses

- H1: a fixed template explains much of raw map variance.
- H2: process/OES signals add unseen-lot information for `M` or `R`.
- H3: wafer-order change and calibrated uncertainty identify high-error VM
  predictions without observing their dense outcomes.
- H4: calibrated uncertainty plus profile risk improves high-error capture.

## Leakage Risks

All points from one wafer must remain together. Lots, interpolated pre-etch
values, filled post-etch values, PCA/FPCA, scaling, feature selection,
wavelength selection, change thresholds, and uncertainty calibration can all
leak test information if fitted before splitting.

## Gates

Success requires traceable lot-aware results, not a new algorithm. Actual
Dektak/P-17 fusion is prohibited without same-time repeatability,
reproducibility, coordinate-registration, and reference-tool evidence.
Complex models are removed when they do not reliably beat simple baselines.
OES remains secondary unless it reduces process-only macro-lot error by at
least 5%.

Every scope or method change must first satisfy the source, data-support,
experiment, numerical-gate, and claim-boundary fields in
`INDUSTRY_ALIGNMENT.md`. User suggestions and model suggestions are hypotheses,
not evidence by themselves.

## Visual Evidence

Required outputs include physical wafer layouts, template/mean/residual maps,
actual-predicted-error-uncertainty maps, lot drift, cycle traces, OES heatmaps,
measurement-system discrepancy, coverage-width, and risk-coverage views.

Visualization quality is the second project priority after evidential
validity. Each milestone must produce a polished README candidate when its
result is visualizable. Default isolated plots are insufficient: figures must
combine the physical object, comparison, error, lot context, and claim boundary
needed to interpret the result without relying on hidden narrative.

## Sources

- [Official dataset and license](https://doi.org/10.5281/zenodo.17122442)
- [NIST 2025 virtual metrology and dynamic sampling study](https://doi.org/10.1109/TSM.2025.3531920)
- [2026 Time-LLM BOSCH spatial-profile study](https://arxiv.org/abs/2603.23576)
- [Industry alignment and decision register](INDUSTRY_ALIGNMENT.md)

## Non-Goals

No closed-loop APC, recipe optimization, conditioning causal proof, production
OOS, fab yield/cost claim, or claim that this research dataset is a production
fab dataset.

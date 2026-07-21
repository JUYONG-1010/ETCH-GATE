# Selective Metrology Protocol

## Offline Policies

Compare Random, wafer-order drift, distance to training distribution,
uncertainty width, predicted profile risk, uncertainty plus profile risk, and
an unattainable true-error oracle.

The current Milestone 4 implementation is ranking-only: selected wafers are
removed from retained-risk scoring and their measurements do not update the
model. The later closed-loop experiment must compare (1) ranking only, (2)
direct-result substitution, and (3) causal model/calibration update using only
previously selected measurements.

## Evaluation

At each full-metrology budget, rank test wafers without test outcomes. Report
high-error capture, retained selective risk, risk-coverage curves, AURC, and
paired improvement over repeated Random.

## Unknown

No real measurement cost, production specification, or OOS label is public.
Budgets are measurement fractions, not currency or fab savings.

## Leakage Risks

High-error thresholds and combined-policy weights come from training
out-of-fold residuals only. The oracle is displayed solely as an upper bound.

For closed-loop evaluation, a selected wafer may affect only later wafers in
the released chronological order. Same-wafer predictions are frozen before its
metrology is revealed; future selected measurements cannot modify past scores.

## Success, Failure, Stop

A policy remains a project contribution only when risk-coverage AUC improves
over Random by at least 10%. Otherwise it is rejected and retained as a
negative experiment.

## Visuals

Risk-coverage curve, metrology-budget versus high-error capture, retained
worst-point risk, and policy reliability by uncertainty/distance bin.

## Sources

- [NIST VM and dynamic sampling](https://doi.org/10.1109/TSM.2025.3531920)
- [BOSCH data](https://doi.org/10.5281/zenodo.17122442)

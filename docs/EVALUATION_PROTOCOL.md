# Evaluation Protocol

## Baselines

Global mean, coordinate template, wafer-order drift, process-feature deltas,
change-point scores, Ridge, PLS, GPR, output-PCA regression, and an oracle
true-mean-shift upper bound. Same-tool sparse simulation may later use
9-point IDW, RBF, or a spatial GP.

## Metrics

Report wafer-macro and lot-macro MAE/RMSE, wafer-mean error,
residual-profile MAE/RMSE, worst-point error, standard-deviation and range
error, point-wise maps, per-lot performance, coverage/width, high-error capture,
selective risk, risk-coverage AUC, runtime, memory, and seed instability.

## Comparisons

Always separate process-only prediction, drift/failure scores, ideal
same-tool sparse simulation, and the actual cross-tool discrepancy audit.
Actual Dektak measurements are not fused into P-17 targets.

## Leakage Risk

Metric aggregation must not hide a failing lot. Model selection uses grouped
inner CV only. Oracle values never become deployable features. Test results
cannot change models, metrics, thresholds, or selected visual examples.

## Success, Failure, Stop

Drift/failure scoring is retained only if it improves high-error capture or
selective risk over matched-budget Random. Same-tool sparse simulation is
retained only if it improves the process baseline on the 80 hidden points.
Complex models are removed when improvement is unstable or isolated.

## Visuals

Per-lot intervals, metric decomposition, point-error maps, change-point views,
complexity versus error/runtime, and risk-coverage differences.

## Sources

- [BOSCH dataset](https://doi.org/10.5281/zenodo.17122442)
- [NIST VM benchmark](https://doi.org/10.1109/TSM.2025.3531920)

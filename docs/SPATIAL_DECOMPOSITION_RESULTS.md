# Mean-Shift and Spatial-Residual Decomposition

## Deployable stages

- Training-lot coordinate template MAE: 0.3509 um
- Template + predicted mean shift: 0.1574 um
- Template + predicted mean + predicted residual: 0.1421 um

## Oracle diagnostics

- True mean shift + zero residual: 0.0981 um
- True mean shift + training-PCA residual reconstruction: 0.0527 um

Oracle rows use test targets and are upper-bound diagnostics, not deployable
models.

## Residual contribution gate

- Status: **PASS**
- Relative residual-stage gain: 9.68%
- Lot-cluster bootstrap 95% interval: [7.03%, 12.66%]
- Lots improved: 10/10

Zones are defined deterministically by normalized wafer radius: center <= 1/3,
middle <= 2/3, and edge > 2/3. Per-wafer zone, range, standard-deviation,
worst-point, p95-point, and mean-centered spatial errors are stored in
`wafer_metrics.csv`.

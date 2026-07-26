# Chronological Virtual-Metrology Results

Every forward fold fits filtering, scaling, template, residual PCA,
hyperparameter selection, and regression using earlier lots only.

| Model | Eligible-lot LOLO MAE | Forward MAE | Relative degradation |
| --- | ---: | ---: | ---: |
| GPR | 0.1908 | 0.2102 | 10.14% |
| PLS | 0.1446 | 0.1737 | 20.15% |
| RIDGE | 0.1567 | 0.1937 | 23.67% |

LOLO tests whether a complete lot can be generalized from the other
lots, including chronologically later ones. The forward evaluation tests
the harder condition in which future process regimes do not exist at fit
time. A degradation is therefore reported as temporal-regime sensitivity,
not hidden by the domain-generalization average.

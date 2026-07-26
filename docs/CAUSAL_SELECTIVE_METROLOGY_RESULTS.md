# Causal Selective-Metrology Results

This replay processes Lots 4-10 in order. Each decision uses earlier lots,
the current process trace, and only previously selected direct measurements.
It never sorts future test-lot risk scores.

## Direct-result substitution

| Budget | Combined MAE reduction vs Random |
| ---: | ---: |
| 10% | 1.89% |
| 20% | 4.94% |
| 30% | -2.12% |

## Feedback update

| Update | Mean relative gain vs frozen F0 |
| --- | ---: |
| F1 | 0.97% |
| F2 | -2.02% |
| F3 | -0.10% |

F0 is frozen VM. F1 updates one scalar mean bias. F2 refits only the
mean-shift PLS model with measured wafers. F3 also refits the residual
shape-score model while keeping preprocessing, template, PCA basis, and
hyperparameters fixed from past lots.

## Policy gate

Overall gate: **FAIL**

| Check | Result |
| --- | --- |
| at least two low budgets improve random | PASS |
| bootstrap improvement interval not cross zero | FAIL |
| at least 70 percent lots equal or better | FAIL |
| lot8 excluded direction remains better | FAIL |
| worst lot not degraded more than 10 percent | PASS |

A failed gate means the online adaptive policy is not retained as a
headline contribution. Static ranking evidence remains a separate result.

# Prior Work and Research Gap

## Confirmed Prior Work

The 2025 Infineon study predicts 17-point PVD thickness and compares XGBoost,
Random Forest, Decision Tree, and ProjSe feature selection. It does not provide
our BOSCH spatial target, chamber-drift failure analysis, or lot-aware escalation
evaluation.

The 2025 NIST study evaluates online Gaussian-process virtual metrology,
uncertainty, drift, and dynamic sampling on CMP data. Its public GitHub
repository currently states that data and code will be uploaded, so it cannot
serve as our executable data source.

The March 2026 Time-LLM preprint uses the same BOSCH release, 88 wafers,
process and OES time series, lot-wise 10-fold cross-validation, and direct
89-point spatial-profile prediction. It separates global mean and shape losses,
selects 25 process channels plus OES bands, and reports experiments on two
NVIDIA A100 80 GB GPUs. Its stated baseline is a single training-set global
mean, not a coordinate-wise other-lot spatial template.

The 2025 Fraunhofer/TU Chemnitz conference work also uses this BOSCH OES source
for DWT, PCA, and functional-PCA compression below 0.001% of raw volume and
etch-depth prediction. OES compression alone is therefore not a novel
contribution.

Consequently, direct process/OES-to-89-point regression, mean/shape
decomposition by itself, Time-LLM adaptation, or OES PCA/fPCA compression
cannot be claimed as this project's novelty.

## ETCH-GATE Gap

The defensible contribution is an evaluation and decision framework:

- compare every learned model against a coordinate-wise, training-lot-only
  template that already reaches `R2 = 0.9826` for stepheight;
- judge incremental process and OES information on wafer mean shift and local
  residual, rather than reward recovery of the repeated template;
- characterize actual Dektak/P-17 discrepancy without treating either
  unmatched measurement session as physical ground truth;
- add drift-aware calibrated uncertainty and matched-budget full-metrology
  escalation;
- preserve measurement provenance, including released IDW replacements;
- publish negative gates when process signals, OES, drift scoring, or escalation do
  not improve unseen-lot decisions.

The coordinate-template audit and process-only VM are completed. Cross-tool
fusion was withdrawn after the measurement-lineage review. Drift scoring,
uncertainty, OES gating, and escalation remain unimplemented. The final
project is not differentiated unless those experiments are completed.

## Unknown

We have not yet completed a systematic benchmark search for every model used
on Zenodo 17122442. No novelty claim is permitted until Milestone 0 literature
tables record task, split, target, metric, code, and data access.

## Leakage Risk

Prior results using point-wise or random-row splits are not comparable to
leave-one-lot-out results. Metric names alone do not establish comparability.

## Success, Failure, Stop

Success means every baseline and claimed gap has a primary citation. Failure
means describing a method as new without evidence. Stop any novelty statement
when an equivalent lot-aware drift and escalation experiment is found.

## Visual

Prior-work matrix: data, target, split, uncertainty, drift handling, escalation,
code availability, and claim boundary.

## Sources

- [Infineon multi-output PVD study](https://doi.org/10.3233/FAIA251482)
- [NIST VM and dynamic sampling](https://doi.org/10.1109/TSM.2025.3531920)
- [BOSCH dataset](https://doi.org/10.5281/zenodo.17122442)
- [2026 BOSCH spatial Time-LLM study](https://arxiv.org/abs/2603.23576)
- [2025 hybrid BOSCH OES compression study](https://doi.org/10.1109/PPPS56198.2025.11248727)

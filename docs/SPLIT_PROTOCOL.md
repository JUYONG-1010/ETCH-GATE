# Lot-Aware Split Protocol

## Primary Evaluation

Use leave-one-lot-out outer evaluation. Every point and every modality from one
wafer stays in the same fold. Hyperparameters use grouped inner CV over only
the outer-training lots.

## Data Roles

For each outer test lot, training lots fit preprocessing and models. A distinct
training-side lot calibrates uncertainty. The held-out outer lot is final test
and never calibrates models, intervals, change thresholds, or policies.

## Non-Negotiable Rules

- prohibit random point and random row splits;
- split before target-derived preprocessing;
- fit scaling, feature selection, PCA/FPCA, wavelength selection,
  interpolation parameters, change thresholds, and uncertainty calibration
  inside the applicable training fold;
- join modalities only by verified keys and coordinates;
- never use test outcomes to choose thresholds, policy weights, or figures.

## Unknown

The exact number and size of lots, chronological order, and feasibility of a
separate calibration lot must be reproduced in Milestone 1.

## Success, Failure, Stop

Pass when every row is assigned once, no wafer or lot crosses prohibited
roles, and hashes make splits reproducible. Fail on any overlap or test-tuned
choice. Stop calibrated claims if the available calibration groups are too
small; report attainable conformal coverage resolution explicitly.

## Visuals

Lot-by-role matrix, wafer availability matrix, chronological drift view, and
split-specific target distributions shown only after roles are frozen.

## Source

[Official BOSCH dataset](https://doi.org/10.5281/zenodo.17122442)

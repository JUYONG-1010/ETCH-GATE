# Uncertainty Protocol

## Construction

Separate model training, uncertainty calibration, and final test lots.
Evaluate point-wise intervals and wafer-wise simultaneous intervals. The first
simultaneous candidate uses the maximum normalized residual across 89 points.

## Required Reporting

Compare nominal and empirical coverage, interval width, interval score,
per-lot coverage, and unconditional intervals. State the finite calibration
sample's achievable coverage resolution.

## Confirmed and Unknown

The project requires calibrated uncertainty; no uncertainty model is selected
yet. Lot sizes and calibration feasibility remain pending the data audit.

## Leakage Risks

GPR or ensemble variance alone is not calibrated uncertainty. Scale models and
normalization are training-only; conformal quantiles are calibration-only;
test residuals never alter either.

## Success, Failure, Stop

Success requires reasonable nominal coverage with intervals materially
narrower than unconditional intervals. Withdraw calibrated-uncertainty claims
when coverage fails or width is non-informative.

## Visuals

Coverage-width frontier, nominal-versus-empirical plot, per-lot coverage,
interval-width map, and actual/predicted/error/uncertainty wafer quartet.

## Source

[NIST 2025 uncertainty-enabled dynamic sampling](https://doi.org/10.1109/TSM.2025.3531920)

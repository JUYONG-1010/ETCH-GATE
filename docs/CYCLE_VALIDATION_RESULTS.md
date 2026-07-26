# BOSCH Cycle Validation Results

## Decision

All 96 process wafers were evaluated without using stepheight or any
other post-etch target. The target-free detector selected by the fixed
lexicographic diagnostic rule is `complementary`.

The rule minimizes, in order: wafers outside the declared 95-105 cycle band,
median absolute deviation from the documented 100-cycle process, phase overlap,
uncovered active samples, and finally detector complexity/order.

## Detector comparison

| detector | wafer_count | median_cycle_count | minimum_cycle_count | maximum_cycle_count | outside_95_105 | median_absolute_cycle_deviation | mean_phase_overlap_fraction | mean_uncovered_active_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quantile | 96 | 100.0000 | 99 | 100 | 0 | 0.0000 | 0.0000 | 0.0663 |
| complementary | 96 | 100.0000 | 99 | 100 | 0 | 0.0000 | 0.0000 | 0.0000 |
| duration_filtered | 96 | 100.0000 | 99 | 100 | 0 | 0.0000 | 0.0000 | 0.0000 |
| period_constrained | 96 | 100.0000 | 99 | 100 | 0 | 0.0000 | 0.0000 | 0.0000 |

## Selected-detector result

- Median detected cycles: 100.0
- Minimum / maximum: 99 / 100
- Wafers outside 95-105: 0
- Phase-overlap samples: 0
- Uncovered active samples: 0
- Suspicious wafers under the complete fixed rule: 0
- Outside-band wafer keys: none

## Lot summary

| lot_number | wafer_count | median_cycle_count | minimum_cycle_count | maximum_cycle_count | median_long_phase_seconds | median_short_phase_seconds | median_cycle_period_seconds | suspicious_wafers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 10 | 100.0000 | 99 | 100 | 4.4000 | 1.6000 | 6.0000 | 0 |
| 2 | 10 | 100.0000 | 99 | 100 | 4.4000 | 1.6000 | 6.0000 | 0 |
| 3 | 10 | 100.0000 | 99 | 100 | 4.4000 | 1.6000 | 6.0000 | 0 |
| 4 | 10 | 100.0000 | 99 | 100 | 4.4000 | 1.6000 | 6.0000 | 0 |
| 5 | 10 | 100.0000 | 99 | 100 | 4.4000 | 1.6000 | 6.0000 | 0 |
| 6 | 10 | 100.0000 | 99 | 100 | 4.4000 | 1.6000 | 6.0000 | 0 |
| 7 | 6 | 100.0000 | 99 | 100 | 4.4000 | 1.6000 | 6.0000 | 0 |
| 8 | 10 | 100.0000 | 99 | 100 | 4.4000 | 1.6000 | 6.0000 | 0 |
| 9 | 10 | 100.0000 | 99 | 100 | 4.4000 | 1.6000 | 6.0000 | 0 |
| 10 | 10 | 100.0000 | 99 | 100 | 4.4000 | 1.6000 | 6.0000 | 0 |

## Deterministic visual examples

The examples were selected before plotting:

- Median cycle-count wafer: `2024-07-02_01`
- Minimum cycle-count wafer: `2024-07-02_02`
- Maximum cycle-count wafer: `2024-07-02_01`
- Largest robust phase-duration anomaly: `2024-07-02_01`

## Interpretation boundary

This validates segmentation consistency with the released process description.
It does not validate plasma chemistry, endpoint detection, etch mechanism, or
post-etch target accuracy. A cycle count near 100 is a process-trace integrity
check, not a model-performance metric.

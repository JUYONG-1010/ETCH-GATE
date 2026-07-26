# Process Feature Ablation Results

All rows use the same nested leave-one-lot-out PLS evaluation. Only the
declared feature group changes.

| ablation | retained_feature_count | lot_macro_full_map_mae | wafer_mean_shift_mae | residual_profile_mae | worst_lot_mae | lots_improved_over_previous |
| --- | --- | --- | --- | --- | --- | --- |
| A_G1 | 93 | 0.1328 | 0.1096 | 0.0776 | 0.1757 | nan |
| B_G1_G2 | 155 | 0.1430 | 0.1203 | 0.0787 | 0.2503 | 4.0000 |
| C_G1_G2_G3 | 248 | 0.1355 | 0.1127 | 0.0790 | 0.2081 | 6.0000 |
| D_all | 310 | 0.1421 | 0.1220 | 0.0788 | 0.2470 | 3.0000 |

## Incremental findings

- Level-only lot-macro MAE: 0.1328 um
- All-feature lot-macro MAE: 0.1421 um
- Phase-group incremental gain: 5.29%
- Cycle-group incremental gain: -4.91%

The family-only comparison is an over-dependence audit, not a claim that the
released anonymous/partial channel names identify a causal chamber mechanism.
PLS VIP is computed inside each outer-training fold from the standard weighted
sum of response variance represented by each latent component. Coefficient
signs and ranks are reported per fold rather than averaged before inspection.

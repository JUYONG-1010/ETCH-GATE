# Milestone 2 - Target and Template Protocol

## Targets

- `stepheight`: primary clean target because the 89-point map is directly measured.
- `oxide_etch`: secondary process-sensitive target; interpolation effects are separate.
- `si_etch`: template sanity target; raw map R2 is never the headline.

## Analysis

For each outer training-lot set, estimate `T(p)`, then calculate wafer mean
shift `M(w)` and residual map `R(w,p)`. Report variance and error separately
for raw map, mean shift, and residual profile.

## Confirmed Provenance

The release provides 89 documented coordinates in micrometers on a 200 mm
wafer. Stepheight is directly measured. Dense pre-etch oxide is mostly IDW
reconstruction from 15 points. Failed post-etch fits are preserved as 157 NaNs
and have separate released IDW replacements. The two CSVs use different exact
`si_etch` formulas: all sparse rows satisfy
`si_etch = stepheight - oxide_etch`, while all dense rows satisfy
`si_etch = stepheight - postox_thickness`. Therefore `si_etch` is retained
only as a released-data sanity target and must not be described with one
shared physical formula across both tools.

## Leakage Risks

`T`, target PCA, imputation, interpolation-derived filters, normalization, and
coordinate exclusion must be learned inside training lots. Whole-data template
subtraction would directly leak the held-out lot.

## Gates

If template-only R2 is at least 0.95, raw map R2 is excluded from headlines.
Target analysis fails if direct and interpolated values cannot be separated.
Fusion stops under the sample-count gates in `DATA_AUDIT_PLAN.md`.

## Visuals

Fixed template, wafer mean-shift distribution, residual maps, PCA component
maps, lot drift, and direct-versus-interpolated measurement overlays.

## Source

[BOSCH dataset](https://doi.org/10.5281/zenodo.17122442)

## Result

[Milestone 2 target and template results](TARGET_TEMPLATE_RESULTS.md)

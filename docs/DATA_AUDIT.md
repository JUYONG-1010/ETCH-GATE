# Milestone 1 - Verified BOSCH Data Audit

Source: [Zenodo 17122442](https://doi.org/10.5281/zenodo.17122442)

## Verified Sample Structure

| Item | Verified result |
|---|---:|
| Process wafer groups | 96 |
| Lots / process dates | 10 |
| Dense 89-point wafers | 88 |
| Sparse 9-point wafer blocks | 76 |
| Sparse wafers with identity | 75 |
| Identified 9/89 paired wafers | 73 |
| Dense coordinates | 89 |
| Sparse coordinates | 9, all present in dense grid |
| Original post-etch NaNs | 157 |
| Filled post-etch NaNs | 0 |

Dense wafers by lot are `9,10,10,10,10,10,6,10,9,4`. Paired wafers exist in
eight lots as `9,10,10,10,10,10,5,9`. This passes the preregistered gates of at
least 70 dense and 60 paired wafers.

## Process Trace

`Process_data.nc` contains exactly 96 groups. All groups decode through
`Dictionary_process.nc` without invalid codes or non-finite values. Ten first-day
wafers have 44 variables; the remaining 86 have 31. Their intersection is
exactly 31 variables and the difference is 13.

The median timestamp interval is 0.2 seconds, consistent with 5 Hz. Some groups
contain gaps up to 45.2 seconds, so loaders must use timestamps and may not
assume a perfectly regular row index.

## Measurement Provenance

All thickness and etch values are in micrometers. The 9-point and 89-point
measurements use different instruments. Pre-etch dense oxide values are mostly
IDW reconstructions from 15 measurements. Failed post-etch interferometer fits
are retained as 157 NaNs in `postox_thickness_nan` and filled by IDW in
`postox_thickness`.

The released `si_etch` formula differs by file. All 684 sparse rows satisfy
`stepheight - oxide_etch`; all 7,832 dense rows satisfy
`stepheight - postox_thickness`. This is verified numerically rather than
silently harmonized. Stepheight remains the primary direct target.

One 9-point block has no experiment, lot, or wafer key and is excluded from
paired analysis. It must not be assigned by similarity without authoritative
metadata.

## Template Gate

Leave-one-lot-out coordinate templates produce:

| Target | Template R2 | Oracle true-mean-shift R2 |
|---|---:|---:|
| stepheight | 0.9826 | 0.9948 |
| oxide_etch | 0.0221 | 0.4053 |
| si_etch | 0.9820 | 0.9945 |

Therefore raw-map R2 is prohibited as a headline for stepheight and si_etch.
The process model must be judged on wafer mean shift and residual profile.
Oxide etch remains the more process-sensitive spatial target.

## Cross-Tool Gate

The 73 paired wafers yield 657 exact key-and-coordinate matches. Raw 9-point
and 89-point stepheight differ systematically. A preliminary leave-one-lot-out
coordinate-median mapping reduces discrepancy relative to the later P-17
values, but this is not evidence of physical calibration: the measurements
use different tools and dates, and no golden reference, same-time repeats,
gauge R&R, or coordinate-registration study is supplied. Actual cross-tool
fusion is therefore excluded. The paired values remain a measurement-system
discrepancy audit.

## Full OES Decision

Do **not** download all 7.9 GB yet. Full OES does not add independent wafers and
would add 3,648 channels at 25 Hz before a process-only baseline exists.

The next gate is:

1. freeze process-only baselines using the verified 31 common traces;
2. download one representative 10-wafer daily OES file;
3. verify decoding, timestamps, wafer keys, and BOSCH cycle alignment;
4. retain full OES only if fold-local OES features reduce unseen-lot
   process-only macro error by at least 5%.

## Reproduce

```powershell
python scripts/audit_bosch_data.py `
  --data-dir data/bosch_raw `
  --output outputs/data_audit/bosch_audit.json
```

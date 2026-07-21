# Process and Measurement Lineage

## What One Result Row Represents

The current virtual-metrology input and target are not measured at the same
time:

```text
July/August 2024 in-situ process trace
        |
        |  wafer undergoes the complete BOSCH recipe
        v
post-etch wafer
        |
        +-- same experiment day: 9-point ex-situ measurements
        |
        +-- February 2025: 89-point ex-situ measurements
                              |
                              +-- current ML target: 89-point stepheight
```

The current model predicts a final post-etch map from signals recorded while
the wafer was being processed. It does not predict a thickness that was
measured continuously during etching.

## Lot Preparation

The official source describes this sequence for each experimental lot:

1. two minutes of O2 plasma cleaning;
2. two minutes of combined O2/SF6 plasma cleaning;
3. one-minute break;
4. 30-minute dummy BOSCH process;
5. O2/SF6 endpoint-controlled final cleaning;
6. 30-minute break;
7. conditioning with the same two-stage O2 and O2/SF6 sequence;
8. conditioning repeated one, three, or nine times on the chuck, a blank Si
   wafer, or a SiO2 wafer, with four-minute breaks between repetitions;
9. ten wafers processed sequentially with a one-minute break and no
   intermediate cleaning.

This design deliberately creates different chamber states and within-lot
drift. The source reports that the conditioning effect itself was
inconclusive, so these labels are experimental context rather than proven
causal factors.

## Starting Wafer

Each lot uses 200 mm, <100>-orientation silicon wafers. The documented design
has more than 99.5% exposed silicon and 89 one-square-millimeter measurement
sites associated with a nominally 1 um SiO2 mask reference.

## One-Wafer BOSCH Recipe

The wafer is processed in an SPTS Omega i2L DSi Rapier system:

1. one-second ignition;
2. 100 repeated cycles;
3. each cycle contains 4.5 seconds of SF6 silicon etching;
4. each cycle contains 1.5 seconds of C4F8 passivation.

The nominal cyclic duration is therefore `100 x 6 = 600 seconds`, plus the
one-second ignition and transitions. The local process files confirm an
RF-active duration of 591.8-602.2 seconds. Recorded traces include variable
pre/post acquisition margins: total group durations are 638.4-766.8 seconds.

For Lot 8 wafer 8 specifically:

```text
record starts:             0.0 s
RF-active window starts: 143.8 s
RF-active window ends:   745.8 s
record ends:             766.8 s
detected long phases:      100
```

The NetCDF `times` variable declares Unix-epoch units but contains values
starting at zero, so the implementation treats it as elapsed seconds within
the wafer group.

## Measurements During Processing

### Process parameters

- 31 common machine channels;
- 5 Hz, one row every 0.2 seconds;
- gas flow, pressure, temperature, RF power and related equipment signals;
- stored per wafer in `Process_data.nc`;
- these are the inputs currently used by the PLS/Ridge models.

The active-process features include the RF window. Long- and short-pulse
summaries use detected alternating gas phases. The public documentation gives
the SF6/C4F8 recipe but does not explicitly map anonymous `Gas4` and `Gas5`
channel names to chemical identities.

### OES

- plasma-emitted light measured in situ;
- 3,648 wavelengths from 185.89 to 883.97 nm;
- 25 Hz;
- exact timestamps supplied because samples can be irregular or missing;
- not yet downloaded locally, so its exact per-wafer start/end coverage has
  not been independently verified in this repository.

## Measurements After Processing

### Same-day 9-point measurements

The source says these measurements were performed on the experiment day:

- pre- and post-etch oxide thickness: MPROBE 40-MSP reflectometer;
- stepheight: Dektak 8 stylus profilometer;
- nine locations per identified wafer;
- manual operation introduces expected operator error.

For the sparse CSV:

```text
oxide_etch = preox_thickness - postox_thickness
si_etch    = stepheight - oxide_etch
```

### February 2025 89-point measurements

The already-etched wafers were measured again months after the process:

- post-etch oxide thickness: FRT MicroProf 300 interferometer;
- stepheight: KLA/Tencor P-17 profilometer;
- 89 documented coordinates;
- pre-etch oxide support has only 15 points and is expanded by IDW;
- 157 failed post-etch oxide fits have released IDW replacements.

The 89-point table contains 7,832 rows (`88 wafers x 89 points`). All 7,832
stepheight values are present and are treated as direct profilometer
measurements. For post-etch oxide, 7,675 successful raw values are unchanged
between `postox_thickness_nan` and `postox_thickness`; only the 157 failed fits
(2.0%) are replaced in the latter column. The CSV does not provide a mask that
identifies which pre-etch oxide positions were among the original 15, so the
IDW provenance of individual filled pre-etch rows cannot be reconstructed
from the CSV alone.

For the dense CSV:

```text
oxide_etch = preox_thickness - postox_thickness
si_etch    = stepheight - postox_thickness
```

The formula difference is present in every released row. It is not corrected
or silently merged. The current primary target is direct 89-point
`stepheight`, so this inconsistency does not enter the Milestone 3 label.

The smooth color fields in repository figures are display interpolation
between the 89 coordinates. Model metrics are calculated on the 89 tabulated
values, not on interpolated image pixels.

## Current ML Alignment

```text
Input:
  in-situ 31-channel process trace during the 2024 BOSCH run

Target:
  final post-etch 89-point stepheight measured in February 2025

Not currently used:
  OES, 9-point measurements, oxide-derived labels, production specifications
```

## Source

- [Official Zenodo dataset](https://doi.org/10.5281/zenodo.17122442)
- Local official documentation: `data/bosch_raw/Readme.pdf`
- Local lot mapping: `data/bosch_raw/Lot_status.xlsx`

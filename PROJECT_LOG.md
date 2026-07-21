# Project Log

## 2026-07-20 - Clean Restart

The previous MulSen-AD routing project and all associated code, reports,
documents, model artifacts, environments, and poster copies were removed at
the user's request.

Preserved:

- Git repository metadata;
- four official PVD CSV files under `data/pvd_raw/`;
- the system-managed read-only `.agents/` directory.

The new project is VALID-VM: validity-aware virtual metrology with adaptive
physical verification for PVD thickness.

## Initial Data Facts

Direct inspection of the downloaded CSVs found:

```text
AlCu: 4,848 aligned records, 97 inputs, 17 targets
WTi:  1,740 aligned records, 108 inputs, 17 targets
Total: 6,588 aligned records
Missing values: 0
Exact duplicate complete X+Y records: 0
```

The public project page's summary of 3,598 procedures and 104 features does not
match the released files. The CSVs contain no record identifiers, grouping
keys, timestamps, sensor meanings or units, measurement coordinates, or
production specification.

Decision: continue only as an anonymized virtual-metrology benchmark unless
authoritative metadata is obtained. Do not describe 6,588 records as 6,588
unique wafers.

## First Gate

Before model development:

1. reproduce file-level counts and integrity checks in code;
2. inspect target distributions and repeated target profiles;
3. define leakage-safe random/repeated validation that is honest about the
   unavailable grouping information;
4. review recent virtual-metrology and adaptive-sampling literature;
5. preregister baselines, uncertainty method, tolerance sweep, and failure
   criteria.

## 2026-07-20 - Milestone 0 Specification Decision

The research scope was changed from a tolerance-based validity gate to:

```text
VALID-VM: Validation-Aware, Leakage-Resistant, Interval-Calibrated,
Decision-Oriented Virtual Metrology for Multi-Point PVD Thickness Prediction
```

Resolved specification conflicts:

- removed production-tolerance and OOS framing because no specification is
  released;
- defined selective metrology as retrospective high-error record capture at
  matched offline budgets;
- separated calibration from model tuning and locked testing;
- restricted all similarity analysis to X-only evidence without assigning
  chamber, recipe, lot, or wafer identities;
- excluded coordinate-dependent wafer, radial, and center-edge figures;
- kept AlCu and WTi as separate problems.

Milestone 0 creates protocol documents only. No target analysis, similarity
analysis, split artifact, model, interval, or selection policy is implemented.

Milestone 0 verification reproduced the data audit and SHA-256 checks. The
existing test suite passed 3 tests, Ruff passed, all relative Markdown links
resolved, and `git diff --check` reported no whitespace error.

## Standing Presentation and GitHub Requirements

The user considers visualization quality a primary project deliverable.
Intermediate milestones and the final README must use polished, immediately
understandable visuals rather than relying on plain default plots.

Visualization quality does not override evidential validity:

- no wafer map, radial map, or center-edge geometry without official point
  coordinates;
- no physical units or dimensional scale without a documented inverse
  transform;
- schematic or embedded views must be labeled as diagnostic, not physical;
- every figure must state the data role, metric, uncertainty, and comparison
  needed to interpret it;
- final figures must be reproducible from machine-readable result artifacts.

Preferred high-impact alternatives include interactive 17-index profile views,
clustered dependence maps, PCA structure views, X-similarity networks,
split-diagnostic embeddings, point-wise residual matrices, conformal interval
views, and risk-coverage or error-capture decision dashboards.

Git policy: do not push intermediate work. Commit and push only when the user
declares the project ready for final publication, after reproducibility and
claim-boundary checks.

## 2026-07-20 - Milestone 1 Target Structure

Implemented target-only summaries, correlation/covariance analysis,
deterministic PCA, clustered target ordering, and four figure families per
material.

An unexpected exact all-zero 17-value target profile was found once in AlCu and
once in WTi. The corresponding X rows are not all zero. Because the public
metadata do not explain these records, the primary analysis retains them and a
separate exclusion sensitivity is reported.

The profile increases median absolute Pearson correlation from 0.793 to 0.847
for AlCu and from 0.898 to 0.962 for WTi. Both retained and exclusion-sensitivity
correlation matrices are persisted.

At a disclosed 95% cumulative-variance threshold:

```text
AlCu: 3 PCA components retained; 4 excluding the all-zero profile
WTi:  1 PCA component retained; 3 excluding the all-zero profile
```

This supports latent-output models as candidates but is not evidence that X can
predict Y. No physical target geometry is inferred.

## 2026-07-20 - ETCH-GATE Migration Started

The active project changed to:

```text
ETCH-GATE: Lot-Aware Template-Residual Virtual Metrology and
Adaptive Metrology Escalation for BOSCH Plasma Etching
```

At the user's explicit request, all previous Infineon files under `data/` were
deleted. Existing source code, tests, figures, and Git history were retained
temporarily so tested work is not destroyed before ETCH-GATE replacements
exist.

Downloaded only the eight small audit files from official Zenodo record
`10.5281/zenodo.17122442`. All eight official MD5 values matched. A local
SHA-256 manifest is stored at `data/bosch_raw/checksums.sha256`.

The ten daily OES files totaling about 7.9 GB were not downloaded. Available
C-drive space after the small download was approximately 39.9 GiB.

The governing research rules are now the ETCH-GATE protocol documents. No
model code was written. Git commit and push remain deferred until the user
declares the final project ready.

## 2026-07-20 - BOSCH Data Audit and OES Download Gate

Reproduced the measurement and process structure from the downloaded CSV and
NetCDF files. The audit verified 96 process wafers, 88 dense 89-point wafers,
75 identified sparse 9-point wafers, and 73 identified paired wafers. All 96
process groups decode without invalid dictionary indices or non-finite values.

Leave-one-lot-out coordinate templates explain 98.26% of raw stepheight map
variance and 98.20% of raw silicon-etch map variance, but only 2.21% of oxide
etch variance. Raw-map R2 is therefore excluded as a headline metric for
stepheight and silicon etch.

The 9-point and 89-point systems are different instruments. Using only the
other seven paired lots to estimate coordinate-wise tool bias reduces
held-out-lot stepheight macro MAE from approximately 1.520 to 0.076
micrometers. This is a preliminary calibration audit, not a final model result.

Decision: do not download all ten daily OES files (about 7.9 GB) yet. Build and
freeze the process-only baseline from the 31 common process traces first. Then
download one representative 10-wafer OES day (planned: 2024-07-05, about
0.83 GB) to validate decoding and cycle alignment. Full OES remains gated on
at least a 5% unseen-lot macro-error reduction over the process-only baseline.

## 2026-07-20 - README Wafer Metrology Visual

Created a README candidate using dense measurements from wafer
`2024-07-02_01`. The visual compares stepheight, silicon etch, and oxide etch
without a vertically exaggerated 3D surface. Black markers identify the 89 real
measurement locations; the continuous color field is explicitly labeled as IDW
interpolation and must not be presented as independently measured pixels.

The static publication asset is:

`docs/figures/data_audit/wafer-2024-07-02-01-metrology-atlas.png`

The final README should use this visual, or a reproducible refined version,
alongside the target-definition and measurement-provenance explanation.

## 2026-07-20 - Milestone 2 Target and Template Analysis

Implemented leave-one-lot-out decomposition of every dense target map:

```text
measurement = other-lot coordinate template
            + observed wafer mean shift
            + local residual
```

Every lot is evaluated using a template fitted to the other nine lots. All
points from a wafer stay together. A leakage test changes one held-out lot's
stepheight by `+1000` and verifies that the template applied to that lot is
unchanged.

Primary numerical results:

| Target | Template R2 | Template MAE | True-mean-shift oracle R2 |
|---|---:|---:|---:|
| stepheight | 0.9826 | 0.3520 µm | 0.9948 |
| silicon etch | 0.9820 | 0.3589 µm | 0.9945 |
| oxide etch | 0.0221 | 0.0529 µm | 0.4053 |

The true-mean-shift result is an oracle diagnostic because it uses the held-out
wafer's measurements to calculate its mean shift. It is not a deployable model.
Stepheight and silicon-etch raw-map R2 values are excluded from future headline
claims under the preregistered `Template R2 >= 0.95` gate.

Generated reproducible figures:

- `docs/figures/target_template/target-decomposition-atlas.png`;
- `docs/figures/target_template/measurement-provenance.png`.

The next milestone is the 31-variable process-only baseline. It must predict
wafer mean shift and residual behavior from process traces without using OES or
held-out metrology.

## Standing Milestone Handoff Rule

At the end of every future project step, the user-facing handoff must separate:

1. **What the user needs to know**: terminology, important functions, leakage
   controls, metrics, results, limitations, and what the result does not mean.
2. **What the user needs to decide**: research priorities, acceptance criteria,
   claim boundaries, target choices, and whether the project advances through
   the next data or model gate.

Each decision must include the recommended choice and its reason in language
appropriate for a physics student without a computer-science background.

Visualization quality is the project's second-highest priority after
evidential validity. Every milestone must create at least one polished,
README-candidate visual when the result has a meaningful visual form. Figures
must favor physical wafer maps, process-cycle views, per-lot comparisons,
measured/predicted/error panels, and decision curves over default standalone
plots. Real measurements, visual interpolation, oracle diagnostics, and
deployable predictions must remain visibly distinguishable.

## 2026-07-20 - Novelty Boundary Updated

A March 2026 Time-LLM preprint was found using the same BOSCH dataset, 88
wafers, process plus OES time series, lot-wise 10-fold evaluation, and
mean/shape 89-point profile prediction. A 2025 Fraunhofer/TU Chemnitz conference
paper already studies aggressive DWT/PCA/fPCA compression of this OES source.

Therefore direct spatial VM, mean/shape decomposition alone, use of Time-LLM,
or OES PCA compression are not defensible novelty claims. ETCH-GATE must be
judged on incremental information beyond a training-lot coordinate template,
drift-regime failure detection, calibrated uncertainty, and matched-budget
full-metrology escalation. Actual cross-tool fusion was later withdrawn after
the measurement-lineage review. If the remaining stages are not completed or
do not pass their gates, the final project is a careful reproduction and audit
rather than a differentiated research result.

## 2026-07-20 - Milestone 3 Process-Only Baseline

Decoded all 96 process traces and retained the 31 signals shared by every
wafer. Detected a roughly 600-second source-RF active window and 99 or 100
long-pulse cycles per wafer. Gas4/Gas5 are kept as anonymous short/long phase
channels; no unsupported chemical identity is assigned.

Created ten active-window, phase-aware, drift, and cycle summaries per signal,
for 310 candidate process features. Sixty-four are globally constant, while
each outer training split retains 241 after training-only constant removal.
Recorded timestamps are used for slopes and early/late windows; rows are not
resampled. The full traces contain a maximum 45.2-second gap outside the active
process window, while the maximum gap inside an active window is 0.21 seconds.

Implemented nested leave-one-lot-out validation. The outer loop withholds one
complete lot. Inner LOLO selects Ridge alpha or PLS components. The coordinate
template, standardization, residual PCA basis, and every model parameter are
fitted using training lots only.

Primary stepheight results:

| Model/stage | Wafer mean MAE (um) | Lot-macro MAE (um) |
|---|---:|---:|
| other-lot template | 0.3520 | 0.3509 |
| PLS + predicted mean shift | 0.1591 | 0.1559 |
| PLS + mean and residual shape | 0.1435 | 0.1399 |
| Ridge + mean and residual shape | 0.1533 | 0.1528 |

The full PLS model reduces wafer-mean MAE by 59.2% versus the strict template;
the lot-cluster bootstrap 95% interval is 43.8%-68.3%. It improves nine of ten
lots over the template and all ten over the mean-shift-only stage. Lot 8
worsens from 0.1899 to 0.2393 um versus the template. Three residual PCA
components are retained in every outer fold. This is predictive evidence on
the released research dataset, not causal process-control or production-yield
evidence.

Generated README-candidate figures:

- `docs/figures/process_baseline/process-cycle-atlas.png`;
- `docs/figures/process_baseline/process-model-dashboard.png`.

Decision at this point was to proceed to 9-point/89-point cross-tool fusion,
but this was later withdrawn after the measurement-time and tool-traceability
review documented below.

## 2026-07-20 - Lot 8 Failure Decomposition

Decomposed the only PLS-held-out lot that worsened against the coordinate
template. Lot 8 wafers 1-7 show close agreement between measured and predicted
mean-shift direction. For wafers 8-10, measured shifts are -0.009, -0.230, and
-0.484 um, but PLS predicts +0.393, +0.395, and +0.335 um. This reversal drives
the lot failure; residual-shape prediction cannot repair a wrong global mean.

The final three wafers contain large individual standardized changes in
Source-RF peak-to-peak slope, Heater2 temperature drift, Gas1 mean, Gas7 drift,
and related summaries. Their global training-PCA nearest-neighbor distances
remain below the training 95th percentile, so a single global distance gate is
insufficient.

The official source README states that sequential wafers were intentionally
processed without intermediate cleaning to create chamber-state drift. Lot 7
and Lot 8 share the 3C-SiO2 condition, which was repeated after etching-tool
problems. The source does not identify a specific physical fault for Lot 8
wafers 8-10. The claim is therefore limited to an observed late-lot regime
change.

Generated `docs/figures/process_baseline/lot8-failure-atlas.png`. The next
modeling work must test wafer-order change-point features, uncertainty, and
escalation rather than merely increasing PLS complexity.

## 2026-07-20 - Process and Measurement Time Lineage

Verified the official experiment chronology against local NetCDF timestamps
and both measurement CSVs. Each lot receives cleaning, a dummy run, and one,
three, or nine conditioning repetitions before wafers are processed
sequentially without intermediate cleaning. Each wafer receives a one-second
ignition followed by 100 nominal six-second SF6/C4F8 BOSCH cycles.

The 31-channel process inputs are recorded in situ at 5 Hz during the 2024
wafer run. The current target is not an in-process thickness: it is the final
89-point post-etch stepheight measured with a KLA/Tencor P-17 in February
2025. Same-day 9-point measurements used different instruments.

Also found and verified a released-label inconsistency. Every sparse row
satisfies `si_etch = stepheight - oxide_etch`, while every dense row satisfies
`si_etch = stepheight - postox_thickness`. Stepheight remains the clean direct
primary target, so Milestone 3 predictions are unaffected. Future work must
not harmonize or physically interpret `si_etch` across tools without resolving
this provenance difference.

## 2026-07-20 - Dense IDW Scope Rechecked

Confirmed that the 89-point table is not entirely IDW-estimated. All 7,832
stepheight values (88 wafers x 89 coordinates) are present direct P-17
profilometer measurements and form the current ML target. Pre-etch oxide has
only 15 measured support points before IDW expansion. Post-etch oxide was
attempted at 89 points; 157 of 7,832 FRT fits failed and were replaced by IDW
in `postox_thickness`, while the raw failures remain NaN in
`postox_thickness_nan`. Nonfailed raw and filled post-oxide values are exactly
equal.

Continuous wafer-map colors in figures are visualization interpolation only.
All reported model errors are evaluated at the 89 released coordinates.

## 2026-07-20 - Cross-Tool Fusion Withdrawn

Rejected actual Dektak 9-point to P-17 89-point fusion as a primary method.
The measurements were acquired with different instruments at different dates,
and the release provides no golden reference, same-time repeated parts,
repeatability/reproducibility study, coordinate-registration uncertainty, or
traceable calibration standard. Mapping Dektak values to P-17 would optimize
agreement with P-17, not establish physical truth.

The 657 overlapping paired coordinates remain useful only to document
measurement-system discrepancy. A later sparse-metrology experiment may mask
the same nine coordinates from the P-17 89-point session, explicitly labeled
as an idealized same-tool retrospective simulation.

Milestone 4 is revised to drift and failure-aware VM: wafer-order process
deltas, conditioning-stratified reporting, change-point scores, OOD indicators, and
uncertainty must be evaluated without using held-out dense outcomes. This
directly addresses the observed Lot 8 regime failure.

## 2026-07-21 - Industry Evidence Re-Audit

Re-audited the reactive decision to withdraw cross-tool work. Primary sources
show that tool/fleet matching, hybrid metrology, virtual metrology, guided
sampling, and drift-aware dynamic sampling are real semiconductor-industry
problems. The correct conclusion is not that cross-tool comparison is
meaningless. It is that this release lacks the reference chain and uncertainty
evidence needed to claim physical calibration.

Final status: Dektak/P-17 pairing remains a secondary empirical comparability
audit; physical truth correction and production fusion remain prohibited.
Drift-aware uncertainty and matched-budget dynamic sampling remain the next
core milestone, supported directly by the 2025 NIST VM study and by equipment
company descriptions of sensor-based VM, computational metrology, and guided
inspection.

Created `docs/INDUSTRY_ALIGNMENT.md` as a mandatory change-control register.
Future changes require a primary source, verified dataset support,
leakage-safe experiment, numerical gate, and explicit claim boundary before
implementation.

## 2026-07-21 - Milestone 4 Drift and Failure-Risk Ranking

Preregistered the experiment before seeing results. The equal-weight candidate
combines outer-training empirical percentiles for PCA nearest-neighbor OOD,
previous-wafer process delta, causal EWMA change, and Ridge/PLS 89-point map
disagreement. The frozen gate required at least 10% lot-macro retained-risk
AUC reduction versus 10,000-repeat Random and improvement in at least seven of
ten held-out lots.

The candidate passed: AURC decreased from 0.13968 to 0.12340, an 11.7%
reduction, and nine of ten lots improved. Lot 8 improved by 38.8%; its wafers
8-9 received high risk, while the highest-error final wafer received only a
moderate combined score. Lot 10, with four dense wafers, was 24.2% worse than
Random.

The aggregate pass does not resolve low-budget sampling. At requested 10%,
20%, and 30% full-metrology fractions, combined retained-MAE reductions were
5.1%, 2.6%, and 6.3%. OOD alone achieved 5.6%, 6.9%, and 9.2%, respectively.
No post-hoc weighting was performed. The allowed conclusion is target-free
failure-ranking signal on this dataset, not calibrated uncertainty or a
production-ready dynamic sampling policy.

Added `src/etch_gate/analysis/drift.py`, the reproducible runner, two leakage
tests, result tables, `docs/DRIFT_RISK_RESULTS.md`, and the README-candidate
`docs/figures/drift_risk/failure-risk-dashboard.png`.

## 2026-07-21 - Post-Selection Limitation and README Audit

User review identified that Milestone 4 simply removed selected wafers from the
retained-risk denominator. Confirmed that no direct-result substitution,
PLS/risk recalibration, or online update occurs. This makes Milestone 4 a
ranking audit rather than a complete dynamic-sampling workflow. The low-budget
gain is therefore supporting evidence, not a standalone contribution.

Compared the workflow with NIST's 2025 online Gaussian-process dynamic sampling,
which uses newly measured samples to update the model and track drift. Added a
future causal comparison of ranking only, direct-result substitution, and
past-measurement model update to the decision register, roadmap, and selective
metrology protocol.

Updated the README with a project decision-flow figure, explicit post-selection
handling, and the OES reduction rationale. OES compression is documented as a
necessary but lossy operation: raw data are retained, all reduction is
training-fold-only, and cycle-aware statistics, PCA, and a regularized compact
time-wavelength representation must be compared rather than accepted from PCA
explained variance alone.

## 2026-07-21 - README Research Narrative Redesign

Reworked the public README after comparison with the user's prior Wafer Defect
Follow-Up Sampling repository. Removed development-stage headings and deleted
the generic project flow graphic and its rendering code. Reorganized the page
around the research problem, headline result, data and target meaning, model,
leakage controls, observed failure, risk-ranking limitation, OES rationale,
reproduction, and claim boundaries.

Changed all README figures to centered GitHub-compatible HTML image tags and
verified that all six referenced PNG files exist. The opening visual is now a
real measured-wafer metrology atlas rather than a generated workflow diagram.
The README remains unpushed under the agreed final-only Git policy, so the new
local figures cannot appear in the remote GitHub repository until that final
push occurs.

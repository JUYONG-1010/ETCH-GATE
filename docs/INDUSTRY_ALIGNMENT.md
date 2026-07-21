# Industry Alignment and Decision Register

## Purpose

No project direction may be added, removed, or promoted solely because it
sounds plausible or because a user or model suggests it. Every material change
must record:

1. the observed data problem;
2. a primary industry, standards, or peer-reviewed source;
3. what the public BOSCH data can and cannot support;
4. a leakage-safe experiment and comparison;
5. a numerical pass/fail gate;
6. the exact claim that is allowed if the gate passes.

When one item is missing, the idea remains exploratory and cannot become a
headline contribution.

## Active Decision Matrix

| Project element | Industry evidence | Dataset support | Decision | Allowed claim |
|---|---|---|---|---|
| Process-signal virtual metrology | Applied Materials describes chamber sensors and ML used to predict on-wafer results; SEMI ASMC includes ML-based VM in APC | 31 common 5 Hz signals and direct 89-point stepheight on 88 wafers | **Keep** | Offline unseen-lot VM on this research dataset |
| Coordinate-template baseline | Computational metrology products combine process/mapping data with measured metrology; high-density map prediction is an industry objective | Repeated 89-coordinate geometry makes memorized spatial structure a major confounder | **Keep as research control** | Incremental information beyond an other-lot spatial template |
| Drift-aware VM and uncertainty | NIST 2025 studies online GP, drift/shift tracking, uncertainty, and dynamic sampling | Sequential wafer order and chamber-conditioning experiments exist, but only 10 lots | **Promote to next core milestone** | Retrospective lot-aware failure-risk and sampling study, not deployed online control |
| Post-metrology feedback | NIST 2025 updates an online VM model as new selected measurements become available | Released wafer order and dense outcomes support a retrospective causal replay, but not production latency or APC actuation | **Require before adaptive-sampling claim** | Offline benefit of past-only measurement feedback versus ranking-only and Random |
| EWMA/CUSUM process monitoring | NIST documents these as SPC tools for detecting small or gradual shifts | No certified in-control baseline, OOS label, or specification limit is released | **Use only as score baselines** | Relative change score, never a production out-of-control decision |
| Direct metrology as verification | Applied states that direct measurement remains necessary and is used with sampling to catch deviations | Direct P-17 stepheight is available after processing | **Keep as ground measurement for evaluation** | VM augments rather than replaces direct metrology |
| Inter-tool matching / hybrid metrology | NIST identifies tool matching and hybrid metrology as real semiconductor problems; Applied and TEL advertise fleet/tool matching | 657 same-wafer/same-coordinate Dektak/P-17 pairs exist | **Keep as secondary comparability audit** | Empirical agreement to later P-17 values under LOLO |
| Physical Dektak-to-P-17 calibration | NIST requires a documented reference chain and uncertainty for traceable calibration | No golden reference, same-time repeats, uncertainty budget, or coordinate-registration study | **Reject as a physical claim** | Do not call the empirical mapping truth correction, traceable calibration, or production tool matching |
| Same-tool sparse sampling | ASML uses computational metrology to form dense maps and multi-source data to guide scan locations | Nine matching P-17 coordinates can be exposed while 80 are hidden | **Retain as later simulation** | Same-session retrospective sparse reconstruction only |
| OES process diagnostics | Fraunhofer describes OES as a fast in-situ method for tracking plasma-condition changes | 3,648 channels at 25 Hz exist; full files are not local | **Retain behind one-day gate** | Incremental OES value after process-only and drift baselines |
| Conditioning causality | The official BOSCH release was designed around conditioning but reports no clear conditioning trend | Conditions are highly confounded with date/lot and have few repeats | **Audit/stratify only** | Association or regime context, never causal conditioning effect |
| Yield, OOS, and monetary savings | Industrial systems optimize yield, process windows, and metrology capacity | No production specification, OOS label, actual cycle time, or cost data | **Reject** | Report normalized measurement fractions and offline error only |

## Primary Industry Comparisons

### Virtual metrology and direct measurement

Applied Materials describes the use of chamber sensor data and machine
learning to predict on-wafer results as virtual metrology, while also stating
that direct measurements remain necessary and are commonly sampled to catch
process deviations. This supports the project sequence `process VM -> risk
assessment -> selected direct metrology`; it does not support claiming that VM
replaces measurement.

- [Applied Materials: sensors, virtual metrology, and direct measurement](https://www.appliedmaterials.com/us/en/blog/blog-posts/designing-eyes-into-process-equipment-to-improve-chip-performance-and-yield.html)
- [SEMI ASMC 2024: ML-based virtual metrology in APC](https://www.semi.org/en/advanced-semiconductor-manufacturing-conference-asmc/2024-session-15-advanced-process-control-2)

### Drift, uncertainty, and dynamic sampling

The NIST 2025 VM study explicitly connects process drift/shift, uncertainty
quantification, and adaptive metrology sampling. ETCH-GATE's Lot 8 failure is
therefore industry-relevant only if a risk score is produced without using the
held-out dense result and is compared with matched-budget Random sampling.

NIST's EWMA guidance also requires historical data representative of an
in-control process. The BOSCH experiment intentionally varies chamber state
and publishes no certified normal lot or process specification. EWMA/CUSUM
may therefore be compared as change scores, but their limits cannot be called
fab control limits or OOS thresholds.

### Milestone 4 preregistered gate

The held-out lot's dense stepheight is used only after ranking to score the
offline experiment. OOD, previous-wafer delta, EWMA change, and Ridge/PLS
disagreement are scaled against outer-training data. Their first combined
candidate is an equal-weight mean with no target-fitted coefficient. It passes
only if it lowers lot-macro area under the retained-risk curve by at least 10%
relative to repeated Random and improves at least seven of ten held-out lots.
Failure does not permit post-hoc Lot 8 tuning. Model disagreement is called a
risk proxy, not calibrated uncertainty.

- [NIST 2025 VM and dynamic sampling study](https://www.nist.gov/publications/comparative-study-semiconductor-virtual-metrology-methods-and-novel-algorithmic)
- [NIST EWMA control-chart assumptions](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm)

### Tool matching and traceability

Tool matching is a real equipment problem, not an invalid concept. Applied
Materials reports fleet-matching capability, and TEL lists automated
calibration for tool matching alongside sensor monitoring and AI analysis.
However, NIST defines traceability through a documented calibration chain and
measurement uncertainty. The BOSCH release cannot establish that chain.

- [Applied Materials VeritySEM fleet matching](https://www.appliedmaterials.com/us/en/product-library/veritysem-6c-cd-metrology.html)
- [Tokyo Electron equipment, sensors, AI, and tool matching](https://www.tel.com/ir/library/ar/nkdco100000008mf-att/product_catalog.pdf)
- [NIST metrological traceability requirements](https://www.nist.gov/metrology/metrological-traceability)
- [NIST semiconductor inter-tool and hybrid-metrology standards](https://www.nist.gov/programs-projects/universal-microscopy-standards)

### Dense maps and guided measurement

ASML describes computational metrology that combines mapping and measured data
to produce dense wafer maps, and e-beam systems that combine multiple data
sources to guide scan strategies. The project can test analogous information
flows, but cannot claim equivalent hardware throughput or deployment.

- [ASML YieldStar computational dense metrology](https://www.asml.com/en/products/metrology-and-inspection-systems/yieldstar-375f)
- [ASML HMI eP5 data-guided scan strategy](https://www.asml.com/en/products/metrology-and-inspection-systems/hmi-ep5)

### Inspection, metrology, and job relevance

Samsung's official description of Evaluation and Analysis emphasizes product
and process evaluation plus data-science quality control. Applied describes
metrology, inspection, review, analysis, and classification as mechanisms for
monitoring and controlling individual process steps. These support failure
analysis, measurement provenance, uncertainty, and statistical process-control
comparisons more directly than adding an unvalidated large neural network.

- [Samsung Electronics DS Evaluation and Analysis role](https://www.samsungcareers.com/subsid/detail/C10CAH)
- [Applied Materials metrology and inspection](https://www.appliedmaterials.com/in/en/semiconductor/semiconductor-technologies/metrology-and-inspection.html)
- [Tokyo Electron etch equipment and data-driven control](https://www.tel.com/corporatesummary/)

## Milestone 4 Gate

Milestone 4 is not allowed to change the VM model merely because Lot 8 is
known to fail. It must use nested training-lot validation to select features,
thresholds, and risk weights. Candidate signals include current-versus-previous
wafer feature deltas, EWMA/CUSUM-style change scores, distance to the training
distribution, and model disagreement.

The milestone passes only when a target-free score:

- improves high-error capture or risk-coverage AUC over repeated Random at the
  same full-metrology fraction;
- remains beneficial across held-out lots rather than only Lot 8;
- does not use future wafers or dense outcomes available after the decision;
- reports Lot 8 as one test case, not a hand-tuned target.

## Change-Control Rule

Before future implementation, append a row to this register with the source,
data support, gate, and claim boundary. A failed gate is logged and retained;
it is not silently replaced by a new project direction. Company-fit statements
must link to the company's own site. Technical claims must use official
documentation, standards bodies, or primary papers.

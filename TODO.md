# Deferred Work

## OES Mini Project: Cycle-Aware Process-State Monitoring

**Status:** Deferred. This is not part of the stepheight virtual-metrology
claim and must not be used to obscure the failed OES incremental-value pilots.

### Research question

Can in-situ OES distinguish Bosch long/short plasma phases and identify
wafer/lot-level spectral-state shifts under a leakage-safe lot split?

### Fixed scope

- Use the four already downloaded OES days only; do not download the remaining
  raw OES data for this mini project.
- Build labels for long/short phase from aligned process traces, not from
  stepheight targets.
- Split by wafer or lot, never by individual OES time row, so adjacent spectra
  from the same wafer cannot appear in both training and testing.
- Compare a compact phase-aware linear baseline before any deep model.

### Numerical evidence required

- held-out-lot macro-F1 and AUROC for long/short phase recognition;
- phase-boundary timing error in seconds;
- cycle-to-cycle normalized spectral stability per wafer;
- lot-level spectral-distance ranking.

### Required visual evidence

- measured time-wavelength OES heatmap with Bosch phase boundaries;
- long-versus-short normalized spectrum and selected discriminative bands;
- cycle/lot spectral-state atlas;
- contextual 89-point wafer map for each showcased wafer, with a stated
  deterministic selection rule.

### Claim boundary

Success establishes OES process-state observability only. It does not establish
stepheight prediction, endpoint detection, chemical-species quantification, or
production deployment.

## Main Project Closure

- [ ] Review all numerical claims and wording in README against result tables.
- [ ] Run a clean reproducibility pass from raw verified inputs.
- [ ] Curate final README figures and remove intermediate-only outputs.
- [ ] Prepare a concise technical report or poster.
- [ ] Commit and push once after the final claim audit.

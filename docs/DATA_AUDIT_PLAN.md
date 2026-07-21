# Milestone 1 - Data Audit Plan

## Confirmed

Eight official small files are downloaded and match Zenodo MD5:
`Readme.pdf`, `Wafer_layout.pdf`, `Lot_status.xlsx`, both measurement CSVs,
`Process_data.nc`, and both NetCDF dictionaries. Local SHA-256 values are in
`data/bosch_raw/checksums.sha256`. Full daily OES is absent by design.

## Questions to Resolve

- exact wafer, experiment, lot, date, and order keys;
- 96/88/76/75/73/10 count reproduction;
- units and coordinate definitions;
- 31 common versus 13 first-day-only process variables;
- raw versus filled values and the 157 reported post-etch NaNs;
- whether 9-point and 89-point coordinates match exactly;
- which pre-etch values are measured versus IDW-filled.

## Audit Procedure

1. Parse the two PDFs visually and textually.
2. Inventory every sheet, dimension, variable, dtype, unit, coordinate, and attribute.
3. Build a key lineage table without changing source files.
4. Reproduce wafer and pairing counts by explicit set intersections.
5. Audit missingness, duplicates, impossible ranges, interpolation flags, and chronology.
6. Verify all checksums again before every downstream milestone.

## Leakage and Integrity Risks

Target-derived filtering before lot assignment, using filled values as raw
measurements, pairing on row order, or treating cross-tool values as identical
would invalidate the project.

## Pass, Fail, Stop

Pass: counts, keys, coordinates, provenance, and missingness are reproducible.
Fail: any discrepancy remains visible and narrows the claim. Actual cross-tool
fusion is prohibited without traceability evidence; stop the project if lots
or wafer identities cannot support group evaluation.

## Visuals

File lineage diagram, lot-by-wafer availability matrix, missingness map,
9/89-point layouts, coordinate overlay, and raw-versus-filled provenance map.

## Source

[Official Zenodo record](https://doi.org/10.5281/zenodo.17122442)

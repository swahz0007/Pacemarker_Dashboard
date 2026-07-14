# Private Files Do Not Upload

Project: Pacemaker Dashboard CIED 程控真实世界数据库  
Updated: 2026-06-30

This file defines the privacy boundary for manuscript work, demos, GitHub, journal submission supplements, and public sharing.

## Absolute Do-Not-Upload Paths

Do not upload, publish, email externally, or place in public supplement:

- `../01_data_repository/`
- `../patient_records/`
- `../dashboard_ui/data/`
- `../doc/audit_result.json`
- `../2026年自筹课题申报/`
- Any file containing patient name, registration number, source Excel path, signature image, raw report screenshot, internal review note, ethics original, or signed administrative document.

## Private Case-Level Data

These are private even if de-identified in filenames:

- Raw Excel programming reports.
- Patient-level JSON files.
- Dashboard data bundle.
- Matching reports with full paths or filenames.
- Field-level audit records that can trace back to a source report.
- Any table with small-cell risk or identifiable timing/path combinations.

## Allowed for Manuscript Only After Review

Allowed only after aggregate-only review:

- De-identified aggregate counts.
- Field availability percentages.
- Brand/device/mode distributions.
- Audit summary tables.
- Workflow diagrams without patient identifiers.
- Dashboard screenshots using simulated data or fully anonymized mock records.

## Public/Demo Website Rule

If a website or demo is attached to a manuscript:

- Use simulated data only.
- Do not include true names, registration numbers, exact source paths, source filenames, or original report images.
- State clearly that the demo dataset is synthetic or de-identified aggregate-only.

## Data Availability Draft Boundary

Recommended manuscript wording:

> Due to patient privacy and institutional restrictions, individual-level programming reports and structured patient records are not publicly available. De-identified aggregate results, variable definitions, and analysis code may be made available from the corresponding author upon reasonable request and institutional approval.

Final wording requires human approval before submission.


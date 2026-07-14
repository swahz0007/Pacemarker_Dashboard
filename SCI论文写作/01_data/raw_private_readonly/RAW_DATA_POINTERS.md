# Raw Data Pointers

Updated: 2026-06-30

This folder intentionally does not contain copied raw patient data.

## Authoritative Raw and Private Sources

| Source | Path | Privacy level | Handling |
|---|---|---|---|
| Raw programming Excel reports | `../../../01_data_repository/` | Private, identifiable | Read-only; do not copy into public outputs |
| Patient-level structured JSON | `../../../patient_records/` | Private, case-level | Use only to generate aggregate/frozen analysis tables |
| Dashboard data bundle | `../../../dashboard_ui/data/` | Private, case-level | Do not upload or expose |
| Field-level audit source | `../../../doc/audit_result.json` | Private, source-traceable | Summarize only into aggregate audit tables |
| Self-funded grant materials | `../../../2026年自筹课题申报/` | Private administrative | Do not upload or reuse publicly |

## Rule

Raw and case-level data remain in their existing project locations. This SCI workspace should store only pointers, dictionaries, aggregate outputs, and reproducible analysis artifacts unless the user explicitly requests a controlled private copy.


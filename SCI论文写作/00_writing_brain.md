# Writing Brain

Project: Pacemaker Dashboard CIED 程控真实世界数据库  
Updated: 2026-06-30

Use this file to keep manuscript logic outside chat history. Update it in place.

## 1. Active Research Question

多品牌、多模板、多设备类型的 CIED 程控报告，能否被可靠地转化为患者级纵向结构化数据库，并通过字段级审计形成可复核、可追踪、可持续增长的真实世界研究底座？

## 2. Central Narrative

This is not a paper about a dashboard.

It is a paper about converting fragmented, multi-brand, semi-structured CIED programming reports into a traceable, auditable, patient-level real-world database. The dashboard is only the review and navigation interface.

## 3. Evidence That Can Anchor Paper 1

| Evidence | Current source | Status |
|---|---|---|
| Cohort scale | `json/project_snapshot_20260517.json` and `04_数据冻结与质控/数据冻结_20260517.md` | Startup snapshot only; not a final manuscript snapshot |
| Patient-level longitudinal structure | `patient_records/*.json` | Needs formal analysis-ready export |
| Template matching coverage | `patient_records/matching_report.csv` | Needs source-data extraction |
| Field-level audit | `doc/audit_result.json` | Needs manuscript-ready summary tables |
| Field availability | Derived from patient JSON | Needs script-generated table |
| Privacy boundary | `.gitignore` and `PRIVATE_FILES_DO_NOT_UPLOAD.md` | Scaffolded |

## 4. Can Say / Cannot Say

Can say:

- This project has built a structured CIED programming report database from multi-brand real-world reports.
- The current evidence supports database construction, field availability, auditability, and follow-up structure.
- The dashboard can be described as a local review and data-navigation interface.
- The current project deliberately avoids manual clinical-outcome collection.

Cannot say:

- Do not claim clinical outcome prediction.
- Do not claim prognosis, mortality, hospitalization, reoperation, infection, or lead-revision findings.
- Do not claim national representativeness.
- Do not claim that the dashboard provides diagnosis or treatment recommendations.
- Do not treat the 2026-05-17 snapshot as final submission numbers without locking a manuscript-specific analysis snapshot.

## 5. Display Architecture for Paper 1

| Display | Role | Source data | Status |
|---|---|---|---|
| Figure 1 | Data pipeline workflow | Method diagram | Planned |
| Figure 2 | Database scale and coverage | Analysis-ready summary | Pending |
| Figure 3 | Field-level audit status and categories | `doc/audit_result.json` summary | Pending |
| Figure 4 | Longitudinal visit-count structure | Patient JSON summary | Pending |
| Figure 5 | De-identified dashboard review interface | Simulated or anonymized screenshot | Pending |
| Table 1 | Cohort/database characteristics | Analysis-ready summary | Pending |
| Table 2 | Key variable dictionary and availability | Data dictionary + availability output | Pending |
| Table 3 | Audit performance and issue categories | Audit output | Pending |

## 6. Writing Order

Follow the qinchao workflow:

1. Results
2. Methods
3. Discussion
4. Introduction
5. Abstract
6. Title and keywords
7. Figure legends, table notes, and supplementary narrative
8. Declarations and journal adaptation

## 7. Current Stop Point

Formal manuscript writing has not started. Next step is Paper 1 analysis-snapshot locking and source-data generation. The live database can continue weekly updates.

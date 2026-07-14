# Master Project State

Project: Pacemaker Dashboard CIED 程控真实世界数据库  
Updated: 2026-06-30

This file is the authoritative cross-session project state. Update it in place after substantive work.

## 1. Current Stage

Stage 0: project initialization and scaffold setup.

Status: ready for human review.

## 2. Active Manuscript Policy

Only one active manuscript is allowed.

Current active manuscript:

- Paper 1: 多品牌起搏器/ICD/CRT 程控报告结构化数据库的构建与字段级审计。
- Active manuscript location: `06_manuscript/current_manuscript/`
- Status: not yet drafted; blueprint and writing progress are initialized.

Reserved but not active:

- Paper 2: 中国三甲医院 CIED 程控报告真实世界特征及随访模式的回顾性分析。
- Reserve location: `02_论文二_三甲医院程控报告回顾性分析/`

## 3. Data Chain

Raw data source:

- Existing raw data location: `../01_data_repository/`
- Handling rule: read-only, private, do not copy to public folders.

Structured source data:

- Patient-level JSON records: `../patient_records/*.json`
- Matching report: `../patient_records/matching_report.csv`
- Field audit source: `../doc/audit_result.json`
- Dashboard bundle: `../dashboard_ui/data/data_bundle.js`

Startup fact layer:

- `json/project_snapshot_20260517.json`
- `json/research_roadmap_20260517.json`
- `json/paper_portfolio_20260517.json`

Current snapshot policy:

- `04_数据冻结与质控/数据冻结_20260517.md` is a research-start snapshot, not a final submission analysis snapshot.
- The operational database remains dynamic and may be updated weekly.
- Formal writing requires a dated, locked analysis-ready snapshot for the manuscript, but this does not freeze or stop the live database.

## 4. Rolling Update Rule

The live CIED programming report database should continue to grow with weekly programming-report updates.

For each manuscript, lock only the analysis snapshot used by that manuscript:

- Name snapshots by date, for example `paper1_analysis_snapshot_YYYYMMDD`.
- Keep the extraction/cleaning/statistical code reproducible from the live source data.
- Do not silently change manuscript numbers after a snapshot is accepted.
- New weekly data enter the next snapshot, revision analysis, or future papers.

## 5. Accepted Startup Facts

From the 2026-05-17 startup snapshot:

| Fact | Value |
|---|---:|
| Patient JSON files | 917 |
| Standard-registration patients | 885 |
| Non-standard/proxy-named patients | 32 |
| Programming records | 1,363 |
| Patients with at least 2 visits | 295 |
| Patients with at least 3 visits | 113 |
| Maximum records per patient | 6 |
| Record month range | 2025-02 to 2026-05 |
| Audit records | 1,064 |
| Audited fields | 51,047 |
| Actionable issues after classification | 0 |

These facts can support planning and grant framing. They must be regenerated from structured sources before final manuscript submission.

## 6. Research Question

Primary active question:

> Can multi-brand, multi-template CIED programming reports be reliably converted into a patient-level longitudinal structured database with field-level auditability?

## 7. Analysis Plan

Not yet accepted.

Planned next analysis layer:

- Define formal analysis population.
- Normalize brand, device type, mode, and date fields.
- Export analysis-ready tables from structured JSON/CSV.
- Produce field availability tables.
- Produce field-level audit summary tables.
- Create figure source data for workflow, coverage, audit, and longitudinal structure displays.

## 8. Accepted Results

None yet for manuscript use.

The existing 2026-05-17 snapshot is accepted only as project planning evidence.

## 9. Human Decisions

| Decision | Status |
|---|---|
| Do not manually collect clinical outcomes | Accepted |
| Treat dashboard as review/navigation interface, not manuscript subject | Accepted |
| Use Paper 1 as the only active manuscript | Accepted by workflow scaffold; awaiting user confirmation |
| Keep Paper 2 as reserve | Accepted by workflow scaffold; awaiting user confirmation |
| Live database keeps weekly updates | Accepted |
| Lock manuscript-specific analysis snapshot before exact Results writing | Required |
| Target journal | Pending |
| Formal analysis plan | Pending |

## 10. Unresolved Questions

- Whether to split Paper 1 into a pure database/methods paper or include limited real-world descriptive results.
- Whether to create a simulated/demo dashboard for public supplement.
- How much manual key-field verification is needed before journal submission.
- Which journal family should be targeted first.

## 11. Stop Boundary

Do not write final manuscript numbers or claims until Stage 2 and Stage 3 gates are accepted:

- Stage 2: locked manuscript-specific analysis-ready snapshot and dictionary.
- Stage 3: accepted analysis plan.

## 12. Change and Deviation Log

| Date | Stage | Change or deviation | Rationale | Human approval |
|---|---|---|---|---|
| 2026-05-17 | Planning | Created Chinese SCI writing workspace and startup JSON facts | Transform dashboard project into paper/grant roadmap | Accepted in prior work |
| 2026-06-30 | Stage 0 | Added qinchao-sci-workflow standard scaffold | Prepare reproducible SCI workflow | Requested by user |
| 2026-06-30 | Stage 0 | Clarified rolling-update policy | Live database updates weekly; only manuscript analysis snapshots are locked | Requested by user |

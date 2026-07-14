# Writing Strategy

Project: Pacemaker Dashboard CIED 程控真实世界数据库  
Active manuscript: Paper 1, 数据库构建与字段级审计  
Updated: 2026-06-30

## Manuscript Positioning

Article type:

- Original Research Article.
- Methods / Validation / Digital Health Database Study.

Not article type:

- Not a review.
- Not a pure dashboard/software note.
- Not a clinical outcome study.
- Not a prediction model paper.

## Working Title

中文：

> 多品牌起搏器/ICD/CRT 程控报告结构化数据库的构建与字段级审计：一项单中心真实世界数字化队列研究

English:

> Construction and Field-Level Audit of a Multi-Brand CIED Programming Report Database: A Single-Center Real-World Digital Cohort Study

## Primary Claim

The study demonstrates a reproducible workflow for constructing and auditing a multi-brand, patient-level CIED programming report database from real-world programming reports.

## Evidence Hierarchy

1. Structured source files generated from the locked manuscript-specific analysis snapshot.
2. Accepted analysis-ready tables and JSON summaries.
3. Field-level audit outputs.
4. Figure/table source data.
5. Manuscript text.

Never write exact manuscript numbers from memory, screenshots, or older prose.

## Section Workflow

Write in this order:

1. Results
2. Methods
3. Discussion
4. Introduction
5. Abstract
6. Title and keywords
7. Figure legends, table notes, and supplementary narrative
8. Declarations and journal adaptation

For each section:

- State the section purpose.
- List source data and display files.
- Define what the evidence can and cannot support.
- Edit the single active manuscript in place.
- Update `06_manuscript/WRITING_PROGRESS.md`.

## Claim Boundaries

Do not claim:

- Clinical outcome association.
- Prognostic prediction.
- National representativeness.
- Diagnostic or therapeutic decision support.
- Automated clinical adjudication.

Allowed claims:

- Data organization and standardization.
- Field availability and auditability.
- Patient-level longitudinal structure.
- Local dashboard-supported review and navigation.
- Foundation for future real-world research.

## Journal Adaptation

Initial target family:

- Medical informatics.
- Digital health.
- Health data systems.

Candidate journals remain provisional until live target-journal checks are completed.

## Display Plan

| Display | Required before writing |
|---|---|
| Figure 1 workflow | Final pipeline diagram |
| Figure 2 database coverage | Source data from locked analysis snapshot |
| Figure 3 audit summary | Source data from audit result |
| Figure 4 visit-count structure | Source data from patient JSON summary |
| Table 1 database characteristics | Source table |
| Table 2 variable dictionary/availability | Source table |
| Table 3 audit results | Source table |

## Human Gate

Before drafting Results, the user should review:

- Locked analysis snapshot summary.
- Analysis-ready fields.
- Device-type and brand normalization.
- Exclusion handling for proxy/nonstandard records.
- Whether Paper 1 includes limited real-world descriptive results or remains mostly methods/audit focused.

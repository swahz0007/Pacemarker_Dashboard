# Project Map

Project: Pacemaker Dashboard CIED 程控真实世界数据库  
Updated: 2026-06-30

## 1. Existing Chinese Planning Layer

| Path | Role |
|---|---|
| `README.md` | SCI 写作工作区入口和硬边界 |
| `00_项目总览与路线图/` | 项目路线图、课题成果归属 |
| `01_论文一_数据库构建与字段级审计/` | 论文一构思和结果展示清单 |
| `02_论文二_三甲医院程控报告回顾性分析/` | 论文二储备构思 |
| `03_后续论文储备/` | 纵向、亚组、自动结局方向储备 |
| `04_数据冻结与质控/` | 启动快照和后续 freeze 说明 |
| `05_字段字典与人工终核/` | 字段字典草案和人工终核边界 |
| `06_期刊调研与投稿策略/` | 期刊和投稿策略 |
| `json/` | 机器可读项目事实层 |

## 2. Standard SCI Workflow Layer

| Path | Role | Current Status |
|---|---|---|
| `01_data/raw_private_readonly/` | Raw data inventory or pointers only | Empty; raw data remains in `../01_data_repository/` |
| `01_data/cleaned_frozen/` | Frozen cleaned master table | Not created |
| `01_data/analysis_ready/` | Analysis-ready CSV/JSON/XLSX | Not created |
| `01_data/dictionaries/` | Data dictionaries and codebooks | To be populated from `05_字段字典与人工终核/` |
| `02_code/data_cleaning/` | Data cleaning scripts | Not created |
| `02_code/statistical_analysis/` | Statistical analysis scripts | Not created |
| `02_code/statistical_validation/` | Validation scripts | Not created |
| `02_code/table_figure_generation/` | Table/figure scripts | Not created |
| `03_results/cleaning_audit/` | Cleaning audit and QA | Not created |
| `03_results/statistical_outputs/` | Statistical output files | Not created |
| `03_results/validation/` | Validation reports | Not created |
| `03_results/manuscript_ready_data/` | Accepted result files for writing | Not created |
| `04_tables/main/` | Main tables | Not created |
| `04_tables/supplementary/` | Supplementary tables | Not created |
| `04_tables/source_data/` | Table source data | Not created |
| `05_figures/main/` | Main figures | Not created |
| `05_figures/supplementary/` | Supplementary figures | Not created |
| `05_figures/source_data/` | Figure source data | Not created |
| `06_manuscript/blueprint/` | Writing strategy and manuscript blueprint | Initialized |
| `06_manuscript/current_manuscript/` | Single active manuscript | Placeholder only; no full draft |
| `06_manuscript/working_drafts/` | Temporary notes only | Empty |
| `06_manuscript/supplementary_materials/` | Supplementary narrative | Empty |
| `07_literature/` | Search logs, evidence matrix, references | Empty |
| `08_submission/` | Journal adaptation and package | Empty |
| `90_history/` | Obsolete drafts | Empty |
| `99_archive/` | Intentional archives | Empty |
| `99_project_audit/` | Structure audits and manifests | Initialized |

## 3. Private and Read-Only Source Locations

These paths are outside the public SCI writing layer and should not be uploaded:

- `../01_data_repository/`
- `../patient_records/`
- `../dashboard_ui/data/`
- `../doc/audit_result.json`
- `../2026年自筹课题申报/`

## 4. Traceability Plan

```text
../01_data_repository/ and ../patient_records/
  -> 02_code/data_cleaning/
    -> 01_data/cleaned_frozen/
      -> 01_data/analysis_ready/ and 01_data/dictionaries/
        -> 02_code/statistical_analysis/ and 03_results/statistical_outputs/
          -> 03_results/validation/
            -> 04_tables/source_data/ and 05_figures/source_data/
              -> 04_tables/main/, 05_figures/main/
                -> 06_manuscript/current_manuscript/
```

## 5. Current Active Files

| Role | Path | Status |
|---|---|---|
| Startup project facts | `json/project_snapshot_20260517.json` | Planning only |
| Startup roadmap facts | `json/research_roadmap_20260517.json` | Planning only |
| Paper portfolio facts | `json/paper_portfolio_20260517.json` | Planning only |
| Data freeze note | `04_数据冻结与质控/数据冻结_20260517.md` | Startup snapshot |
| Active manuscript | `06_manuscript/current_manuscript/manuscript_论文一_数据库构建与字段级审计_主稿.md` | Placeholder only; no full draft |

# Start Here

Project: Pacemaker Dashboard CIED 程控真实世界数据库  
Updated: 2026-06-30

## One-Sentence Status

项目已从中文路线图工作区升级为 qinchao-sci-workflow 标准 SCI 项目脚手架；当前只接受结构化、可复现、可审计的 SCI 工作流，不改原始数据、不改 dashboard 代码、不人工收集临床结局。

## Current Research Direction

当前唯一 active manuscript 是论文一：

> 多品牌起搏器/ICD/CRT 程控报告结构化数据库的构建与字段级审计：一项单中心真实世界数字化队列研究

论文二作为储备方向保留：

> 中国三甲医院 CIED 程控报告真实世界特征及随访模式的回顾性分析

## Current Stage

Stage 0: project initialization / scaffold accepted for use, pending human confirmation.

已经完成：
- 中文科研路线图和两篇论文方向。
- 2026-05-17 启动数据快照。
- 标准 SCI 目录结构。
- 中央状态文件。
- 隐私禁止上传清单。
- 论文一 writing strategy 和 writing progress。

尚未完成：
- 正式投稿用分析快照锁定。
- analysis-ready CSV/JSON 表。
- 表格和图件 source data。
- 文献检索矩阵。
- 正式 active manuscript 正文。

## Required Reading Order

1. `00_START_HERE.md`
2. `00_master_project_state.md`
3. `00_project_map.md`
4. `00_writing_brain.md`
5. `PRIVATE_FILES_DO_NOT_UPLOAD.md`
6. `06_manuscript/WRITING_PROGRESS.md`
7. `06_manuscript/blueprint/WRITING_STRATEGY.md`
8. `00_项目总览与路线图/科研转化路线图.md`
9. `04_数据冻结与质控/滚动更新与论文分析快照策略_20260630.md`
10. `04_数据冻结与质控/数据冻结_20260517.md`

## Single Next Action

对论文一做正式分析快照锁定：从持续更新的 `patient_records/*.json`、`patient_records/matching_report.csv`、`doc/audit_result.json` 和 `dashboard_ui/data/data_bundle.js` 切出一个带日期版本号的 analysis-ready 快照，并生成数据字典、统计摘要和表图 source data。

## Stop Boundary

在论文分析快照和字段字典门禁通过前，不写正文中的精确结果数字，不准备投稿包，不公开 dashboard 真实数据。动态数据库本身继续每周更新，不因论文写作而停止。

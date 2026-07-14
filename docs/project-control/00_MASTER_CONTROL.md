# Pacemaker Dashboard 项目总控

更新时间：2026-07-10  
状态：暂停推进，等待下一次人工启动  
权威级别：本目录的跨会话主入口

## 1. 一句话状态

项目已具备 Excel 程控报告提取、患者级纵向归并、字段审计、脱敏公开构建和 Netlify 仪表盘能力；正式站点目前运行公开免登录的 `v304`，本地已完成但尚未上线的 `v305` 包含真实结论的直接标识脱敏和关键事件换行修复。

## 2. 当前权威状态

| 层级 | 当前状态 | 权威来源 |
|---|---|---|
| 研究源数据 | 私有、持续更新，不得上传 | `01_data_repository/`、`patient_records/` |
| SCI 写作 | Stage 0 脚手架完成，论文一尚未锁定正式分析快照 | `SCI论文写作/00_START_HERE.md` |
| 公开演示数据 | 734 份匿名化演示记录 | `dashboard_ui/demo_data/data_bundle.js` |
| 正式网站 | `v304`，公开免登录，结论仍为不发布占位文本 | <https://gxmu-pacemaker-dashboard.netlify.app/> |
| 本地前端 | `v305`，结论直接标识脱敏、事件卡片两列换行 | `dashboard_ui/` |
| 本地验证 | 6 项测试通过，734 份发布记录隐私审计通过 | `tests/`、临时发布包审计 |
| Git 状态 | 工作树存在大量未提交变更和未跟踪文件 | `git status --short` |

## 3. 当前停止边界

暂停期间不做以下操作：

- 不继续上传包含真实病例级程控结论的公开生产版本。
- 不改动或覆盖原始 Excel、患者 JSON、审计结果。
- 不把当前工作树视为已提交或可回滚的稳定版本。
- 不把公开演示的 734 份记录与 SCI 启动快照中的研究队列数字混用。
- 不将仪表盘展示用于临床诊断或治疗决策。

## 4. 下次启动的单一入口

按以下顺序阅读：

1. 本文档。
2. [07_DECISIONS_RISKS_BACKLOG.md](07_DECISIONS_RISKS_BACKLOG.md)。
3. [08_RESUME_CHECKLIST.md](08_RESUME_CHECKLIST.md)。
4. 根据任务进入对应专题文档。
5. 若任务涉及论文，转到 `SCI论文写作/00_START_HERE.md`。

## 5. 专题文档索引

| 文档 | 用途 |
|---|---|
| [01_PRODUCT_SCOPE.md](01_PRODUCT_SCOPE.md) | 产品目标、边界、用户与成功标准 |
| [02_SYSTEM_ARCHITECTURE.md](02_SYSTEM_ARCHITECTURE.md) | 目录、组件、数据流和关键入口 |
| [03_DATA_PRIVACY.md](03_DATA_PRIVACY.md) | 数据分层、脱敏策略、公开边界 |
| [04_FRONTEND_UI_GUIDE.md](04_FRONTEND_UI_GUIDE.md) | UI 设计系统、响应式规则和已知细节 |
| [05_BUILD_TEST_DEPLOY.md](05_BUILD_TEST_DEPLOY.md) | 构建、测试、审计、CI 和 Netlify 发布 |
| [06_OPERATIONS_RUNBOOK.md](06_OPERATIONS_RUNBOOK.md) | 日常更新、故障排查、恢复操作 |
| [07_DECISIONS_RISKS_BACKLOG.md](07_DECISIONS_RISKS_BACKLOG.md) | 决策、风险、未决项和优先级 |
| [08_RESUME_CHECKLIST.md](08_RESUME_CHECKLIST.md) | 下次会话的可执行检查清单 |
| [09_CHANGELOG.md](09_CHANGELOG.md) | 关键阶段与变更记录 |

## 6. 最重要的下一项决策

决定病例级结论的正式发布方式：

- 公开站点仅发布标准化技术结论；或
- 恢复授权访问后展示完整脱敏结论；或
- 继续在公开站点隐藏结论。

该决策应先于 `v305` 生产部署。

## 7. 人工复核点

- 机构伦理、数据治理和患者信息公开授权是否覆盖病例级结论。
- `v305` 结论规则是否应采用术语白名单，而不是仅删除直接标识。
- 大量未提交变更如何拆分、审查和提交。
- SCI 项目是否正式接受论文一为唯一 active manuscript。


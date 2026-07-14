# 系统架构与数据流

## 1. 目录职责

| 路径 | 职责 | 隐私级别 |
|---|---|---|
| `01_data_repository/` | 原始 Excel 程控报告 | 私有、只读 |
| `backend/` | 匹配、提取、分组、审计 | 代码 |
| `patient_records/` | 患者级结构化 JSON 与匹配报告 | 私有 |
| `dashboard_ui/data/` | 内部仪表盘数据 | 私有 |
| `dashboard_ui/demo_data/` | 提交到仓库的匿名化演示数据 | 可用于公开构建 |
| `dashboard_ui/` | 前端页面、样式、脚本与构建器 | 代码 |
| `netlify_publish/` | 本地构建产物 | 生成物，不是源数据 |
| `tests/` | 安全与流水线回归测试 | 代码 |
| `SCI论文写作/` | 论文工作流与研究记忆 | 混合，遵循其隐私清单 |
| `docs/project-control/` | 工程项目总控与交接 | 文档 |

## 2. 主数据流

```text
原始 Excel
  -> 模板匹配
  -> 字段提取
  -> 身份验证与冲突隔离
  -> 患者级纵向 JSON
  -> 独立字段审计
  -> 内部数据包 / 匿名化公开数据包
  -> 浏览器仪表盘
  -> Netlify 公开演示站点
```

## 3. 后端关键入口

- `backend/main.py`
  - `full_process()`：全量流程。
  - `incremental_update()`：新增、修改和删除来源的增量处理。
- `backend/scripts/match_templates.py`
  - 解析文件名与内容特征，选择模板。
- `backend/core/extractors.py`
  - 提取 KV、表格、事件、结论、签名日期等字段。
- `backend/core/grouping.py`
  - 按登记号归并、排序、隔离身份冲突、清理失效来源。
- `backend/core/file_tracker.py`
  - 文件哈希、处理索引和变更检测。
- `backend/scripts/audit_extraction.py`
  - 独立读取 Excel 单元格，不复用生产提取函数进行核验。

## 4. 前端关键入口

- `dashboard_ui/index.html`：页面结构和资源版本标识。
- `dashboard_ui/assets/css/style.css`：设计令牌、布局、响应式和暗色主题。
- `dashboard_ui/assets/js/app.js`：数据加载、统计聚合、患者详情与图表。
- `dashboard_ui/assets/js/auth-entry.js`：当前仅初始化 Chart.js 和公开演示会话。
- `dashboard_ui/scripts/build_identity_client.mjs`：打包前端入口；名称沿用历史 Identity 方案。
- `dashboard_ui/scripts/build_netlify_preview.py`：匿名化、拆分记录、扫描泄露并生成发布包。

## 5. 公开构建流

```text
dashboard_ui/demo_data/data_bundle.js
  -> collect_sensitive_values()
  -> anonymize_bundle()
  -> audit_anonymized_bundle()
  -> data/index.json
  -> data/records/Pxxxx.json
  -> scan_publish_dir()
  -> privacy_audit.json
  -> 仅 status=pass 才允许部署
```

## 6. 数据口径差异

- `patient_records/` 当前可见 918 个 JSON 文件，其中可能包含辅助/隔离文件，不能直接当作患者数。
- 2026-05-17 SCI 启动快照记录 917 个患者 JSON、1,363 条程控记录；仅用于规划，投稿前必须重算。
- 当前公开演示包为 734 名匿名患者。
- 本地 `v305` 发布包检测到 943 条结论；该数字只描述演示包，不是研究结果。


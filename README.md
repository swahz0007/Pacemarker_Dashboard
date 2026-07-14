# Pacemaker Dashboard 🫀

**心脏起搏器程控报告数据提取、审计与可视化系统**

> ⚠️ 本仓库仅包含核心代码逻辑，**不包含任何临床原始数据**（患者隐私保护）。

## 项目总控与交接

工程进度、线上/本地版本差异、数据边界、UI 规范、部署流程和下一步任务统一记录在：

- [项目总控](docs/project-control/00_MASTER_CONTROL.md)
- [下次启动检查清单](docs/project-control/08_RESUME_CHECKLIST.md)

若任务涉及 SCI 论文，请从 [SCI 写作入口](SCI论文写作/00_START_HERE.md) 开始，两套文档分别管理工程交付与论文工作流。

## 项目简介

将心电诊断科数千份不同品牌（美敦力、雅培、波科、百多力、创领）的 Excel 程控报告，自动提取为标准化 JSON 结构，为后续回顾性分析、机器学习、深度学习研究提供高质量数据基础。

## 核心指标

| 指标           | 数值                                             |
| -------------- | ------------------------------------------------ |
| 支持品牌       | 美敦力 / 雅培 / 波科 / 百多力 / 创领             |
| 支持设备类型   | 起搏器 / ICD / CRT-D / CRT-P / EV-ICD / Micra AV |
| 审计字段数     | 40,202                                           |
| 提取准确率     | 以独立审计报告为准（不得预设为 100%）             |
| 身份冲突记录   | 隔离至 `patient_records/quarantine_records.json` |

## 系统架构

```
Pacemarker_Dashboard/
├── backend/                    # 数据处理引擎
│   ├── core/                   # 核心模块
│   │   ├── handlers.py         #   Excel 文件处理器 (智能 Sheet 选择)
│   │   ├── extractors.py       #   数据提取器 (KV/表格/事件/签名)
│   │   ├── grouping.py         #   患者分组与纵向匹配
│   │   ├── utils.py            #   工具函数
│   │   └── file_tracker.py     #   文件索引
│   ├── scripts/
│   │   ├── audit_extraction.py #   自动化审计 → audit_result.json
│   │   ├── extract_data.py     #   独立提取工具
│   │   └── match_templates.py  #   模板匹配工具
│   ├── data/templates.json     #   模板定义
│   ├── config.py               #   全局配置
│   └── main.py                 #   主入口 (模板匹配→提取→分组)
├── dashboard_ui/               # 可视化面板
│   ├── index.html              #   公开脱敏演示入口
│   ├── assets/                 #   CSS/JS 资源
│   └── scripts/                #   数据打包脚本
├── 01_data_repository/         # 原始 Excel 报告 [Git Ignored 🔒]
├── patient_records/            # 标准化 JSON 病历库 [Git Ignored 🔒]
└── doc/                        # 文档
```

## 使用方法

### 环境准备
```bash
python -m pip install -r requirements.txt
npm ci
```

### 完整流程
```bash
# 1. 数据提取 (Excel → JSON)
python backend/main.py

# 2. 独立审计（仅在全量提取成功且无未匹配模板时运行）
python backend/scripts/audit_extraction.py

# 3. 构建、语法和隐私回归检查
npm run check

# 4. 生成仅含脱敏数据的 Netlify 发布目录
npm run build
```

### 审计输出
`doc/audit_result.json` — 包含独立单元格校验、源文件覆盖率与逐字段结果：
- **MATCH**: 提取值与 Excel 原始值一致
- **MISMATCH**: 值不一致（附根因分类）
- **MISSING**: Excel 有值但提取为空
- **NOT_FOUND**: 无法在 Excel 中定位验证

## 技术特性

- **智能 Sheet 选择**：根据文件名患者姓名自动匹配正确的 Sheet（解决雅培模板多 Sheet 残留问题）
- **独立审计**：审计器不复用生产提取函数；表格通过原始单元格行/列表头交叉验证，签名自由文本单独标记为人工复核
- **问题自动分类**：CROSS_SHEET / NAME_TYPO / ARROW_VALUE 等 8 类根因，区分系统 bug 与数据源问题
- **全量覆盖**：header、设置参数、表格参数、测试阈值、事件记录、抗心动过速参数、签名日期

## 数据安全与使用边界

- 身份信息冲突不会再以文件名自动覆盖，而是写入隔离队列等待人工复核。
- 全量输出和处理索引采用原子写入，并记录 schema、流水线版本与来源指纹；全量成功后才会清理失效输出。
- 历史 `generate_demo_data.py` 已停用。公开发布仅可使用 `dashboard_ui/scripts/build_netlify_preview.py`，该脚本会在写出发布目录前执行 fail-closed 脱敏检查。
- 仪表盘仅用于数据整理与研究辅助。电池与事件展示必须以原始程控报告、设备状态和临床判断为准，不用于临床决策。

## 公开演示发布

- 正式站点当前为免登录公开演示：<https://gxmu-pacemaker-dashboard.netlify.app/>。
- 发布构建将索引与逐例记录拆分为 `data/index.json` 和 `data/records/Pxxxx.json`；逐例数据只会在用户选择患者或主动加载研究统计时请求。
- `netlify.toml` 对数据响应禁用缓存，并设置 CSP、Referrer Policy、Permissions Policy 等安全响应头。
- GitHub Actions 使用锁定的 Python/Node/npm 依赖，先执行回归和脱敏审计，再允许生产部署。
- 公开字段范围和结论发布决策以 [数据与隐私边界](docs/project-control/03_DATA_PRIVACY.md) 为准。

## 隐私与安全

- **代码与数据分离**：原始 Excel 和提取结果均通过 `.gitignore` 排除
- **最小化发布**：发布目录不包含原始数据包、真实登记号、原始文件名、来源路径、签名或叙述性自由文本
- **本地化提取**：Excel 提取与独立审计在本地完成；仅经脱敏检查的发布目录可部署

---
*Developed for Electrophysiology Research.*

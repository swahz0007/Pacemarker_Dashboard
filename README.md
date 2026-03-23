# Pacemaker Dashboard 🫀

**心脏起搏器程控报告数据提取、审计与可视化系统**

> ⚠️ 本仓库仅包含核心代码逻辑，**不包含任何临床原始数据**（患者隐私保护）。

## 项目简介

将心电诊断科数千份不同品牌（美敦力、雅培、波科、百多力、创领）的 Excel 程控报告，自动提取为标准化 JSON 结构，为后续回顾性分析、机器学习、深度学习研究提供高质量数据基础。

## 核心指标

| 指标           | 数值                                             |
| -------------- | ------------------------------------------------ |
| 支持品牌       | 美敦力 / 雅培 / 波科 / 百多力 / 创领             |
| 支持设备类型   | 起搏器 / ICD / CRT-D / CRT-P / EV-ICD / Micra AV |
| 审计字段数     | 40,202                                           |
| **提取准确率** | **100%**                                         |
| 需修复问题     | 0                                                |

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
│   ├── index.html              #   面板入口 (双击即用)
│   ├── assets/                 #   CSS/JS 资源
│   └── scripts/                #   数据打包脚本
├── 01_data_repository/         # 原始 Excel 报告 [Git Ignored 🔒]
├── patient_records/            # 标准化 JSON 病历库 [Git Ignored 🔒]
└── doc/                        # 文档
```

## 使用方法

### 环境准备
```bash
pip install openpyxl xlrd pandas
```

### 完整流程
```bash
# 1. 数据提取 (Excel → JSON)
python backend/main.py

# 2. 自动化审计 (验证提取准确性)
python backend/scripts/audit_extraction.py

# 3. 更新可视化面板
python dashboard_ui/scripts/generate_data.py

# 4. 查看面板
# 双击 dashboard_ui/index.html
```

### 审计输出
`doc/audit_result.json` — 包含逐字段对比结果：
- **MATCH**: 提取值与 Excel 原始值一致
- **MISMATCH**: 值不一致（附根因分类）
- **MISSING**: Excel 有值但提取为空
- **NOT_FOUND**: 无法在 Excel 中定位验证

## 技术特性

- **智能 Sheet 选择**：根据文件名患者姓名自动匹配正确的 Sheet（解决雅培模板多 Sheet 残留问题）
- **重提取审计**：表格/事件/签名区域使用提取脚本同一函数重新提取后逐键对比，保证审计一致性
- **问题自动分类**：CROSS_SHEET / NAME_TYPO / ARROW_VALUE 等 8 类根因，区分系统 bug 与数据源问题
- **全量覆盖**：header、设置参数、表格参数、测试阈值、事件记录、抗心动过速参数、签名日期

## 隐私与安全

- **代码与数据分离**：原始 Excel 和提取结果均通过 `.gitignore` 排除
- **本地化运行**：全流程在本地完成，无外部数据传输

---
*Developed for Electrophysiology Research.*

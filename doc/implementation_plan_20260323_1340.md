# 审计流程重构：JSON 自动闭环

## 目标
删除所有 CSV 审计输出，用 JSON 重建审计流程，实现「提取 → 审计 → 分析 → 自动修复」闭环。

## Proposed Changes

### 1. 清理旧文件
- 删除 `doc/` 下所有 CSV 审计表和过期文件
- 保留 `doc/brand_distribution.png` 和 `doc/implant_trends.png`（可视化图表）

---

### 2. 重写审计脚本输出为 JSON

#### [MODIFY] [audit_extraction.py](file:///e:/Pacemarker_Dashboard/backend/scripts/audit_extraction.py)

- 输出 `doc/audit_result.json` 而非 CSV
- JSON 结构：
```json
{
  "meta": {"timestamp": "...", "total_records": N, "total_fields": N},
  "records": {
    "文件名.xls": {
      "fields": [
        {"section": "header", "key": "姓名", "excel_val": "张三", "extracted_val": "张三", "status": "MATCH"},
        {"section": "basic_params.measurements", "key": "心房_输出电压", "excel_val": "3.5", "extracted_val": "3.5", "status": "MATCH"},
        ...
      ],
      "summary": {"total": 25, "match": 23, "mismatch": 1, "missing": 1}
    }
  },
  "summary": {
    "by_status": {"MATCH": 5000, "MISMATCH": 50, "MISSING": 20, "NOT_FOUND": 10},
    "by_section": {...},
    "accuracy": 0.985
  }
}
```

---

### 3. 删除独立的 audit_analyzer.py 和 gold_standard.py

将分析逻辑**内置**到审计脚本中，一次运行完成全部流程：
1. 遍历所有已提取记录
2. 对每条记录用重提取法验证
3. 自动分类问题（NAME_TYPO / CROSS_SHEET / ARROW_VALUE / TRUE_MISMATCH）
4. 输出 JSON 结果 + 终端摘要

---

### 4. 自动闭环

我（AI）执行：
1. `python backend/scripts/audit_extraction.py` → 生成 `audit_result.json`
2. 读取 JSON → 分析 TRUE_MISMATCH 和 MISSING 的模式
3. 如果有可修复问题 → 修改提取脚本 → 重新提取 → 重新审计
4. 循环直到 TRUE_MISMATCH ≈ 0

## Verification Plan

### Automated
- 每轮循环后检查 `audit_result.json` 的 `summary.accuracy`
- 目标：accuracy ≥ 0.95（真实的字段匹配率）

### Manual
- 最终结果由用户抽查确认

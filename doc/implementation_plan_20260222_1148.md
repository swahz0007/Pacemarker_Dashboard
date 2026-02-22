# 修复数据读取Bug：Dashboard 显示 644 份档案，实际应为 ~750+

## 问题诊断

数据流全链路追踪结果：

| 环节                             | 数量    | 说明               |
| -------------------------------- | ------- | ------------------ |
| 源文件 (`01_data_repository/`)   | **971** | 608 xls + 363 xlsx |
| 匹配成功 (`matching_report.csv`) | **965** | 6个 No Match       |
| 分组后的程控记录                 | **859** | 106条被过滤        |
| 唯一患者 JSON                    | **643** | 多次程控合并       |
| `data_bundle.js` index           | **644** | 前端显示数         |

**根因**：两处代码存在过于激进的数据过滤，丢弃了约 **106 条** 合法记录。

### Bug 1：`extractors.py` 的 `validate_and_fix_header()` (L217-219)

当文件名中提取的姓名与 Excel 内部 header 的姓名不匹配时，会**清空登记号**：

```python
d_header["登记号"] = ""  # 清空污染的登记号
```

之后 `grouping.py` 的 `group_by_registration_id()` (L39) 用 `if reg_id:` 过滤掉空登记号的记录，导致这些记录被永久丢弃。

### Bug 2：`grouping.py` 的 `is_valid_record()` (L15-25)

要求文件名姓名与 header 姓名互相包含，但 `extract_name_from_filename()` 使用的 `NAME_SUFFIXES` 列表（含空格 `" "`）可能误截断文件名，导致姓名提取不准确、误判为"不匹配"。

> [!IMPORTANT]
> 这两个过滤器形成了**双重过滤**：`validate_and_fix_header` 可能清空了登记号，而 `is_valid_record` 本身也在做相同的姓名匹配——导致即使手动修正登记号，记录也会被标记为无效并丢弃。

## Proposed Changes

### 核心修复：`grouping.py`

#### [MODIFY] [grouping.py](file:///e:/Gemini%20CLI%20实战/Pacemarker_Dashboard/backend/core/grouping.py)

1. **移除 `is_valid_record()` 过滤**：不再根据文件名与 header 的姓名匹配来过滤记录。改为**日志警告**但保留记录。
2. **处理空登记号**：对于登记号为空的记录，使用文件名生成一个代理 ID以确保不丢失数据。

---

### 配套修复：`extractors.py`

#### [MODIFY] [extractors.py](file:///e:/Gemini%20CLI%20实战/Pacemarker_Dashboard/backend/core/extractors.py)

1. **`validate_and_fix_header()`**：不再清空登记号——即使姓名不匹配，也保留原始登记号。登记号和姓名是独立字段，姓名不匹配不代表登记号是错的。

## Verification Plan

### 自动验证

修改完成后，请用户手动在终端执行以下命令，按顺序运行：

```powershell
# 步骤1：运行后端全量处理
cd "e:\Gemini CLI 实战\Pacemarker_Dashboard"
python backend/main.py

# 步骤2：重新生成前端数据
python dashboard_ui/scripts/generate_data.py

# 步骤3：验证最终患者数量
# 期望: 远大于 644
```

### 手动验证
- 在浏览器中打开 `dashboard_ui/index.html`，检查左下角"共 X 份档案"数字是否增加。

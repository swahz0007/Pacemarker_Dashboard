"""
数据提取准确性审计脚本 (v2 — JSON 输出)
=========================================
对比原始 Excel 与提取 JSON，生成机器可读的审计报告。

核心策略:
  - 简单键值字段 → _find_in_excel 查找
  - 表格字段 → 用提取脚本同一函数重提取 → 逐键对比
  - 分析逻辑内置 → 自动分类问题根因
  - 输出 JSON → 方便 AI 自动分析和迭代修复

用法:
    python backend/scripts/audit_extraction.py           # 审计全部
    python backend/scripts/audit_extraction.py --sample 20

输出:
    doc/audit_result.json
"""

import argparse
import json
import logging
import os
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import (
    PATIENT_RECORDS_DIR, DATA_REPOSITORY,
    KW_BASIC, KW_ANTITACHY, KW_TEST, KW_EVENT,
    ZAT_COL_HEADERS, ZAT_ROW_HEADERS,
    Z2_COL_HEADERS, Z2_ROW_HEADERS, Z3_COL_HEADERS, Z3_ROW_HEADERS,
)
from core.handlers import get_handler
from core.utils import atomic_write_json, clean_value, stable_source_id

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = BACKEND_DIR.parent
DOC_DIR = PROJECT_ROOT / "doc"
AUDIT_JSON = DOC_DIR / "audit_result.json"


# ============================================================
# 工具函数
# ============================================================

def read_extracted_json(filepath):
    """读取正式或隔离患者输出，保留 source_id，避免同名源文件相互覆盖。"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error("读取患者JSON失败，已跳过: %s", str(filepath), extra={"file": str(filepath), "error": str(e)})
        return {}
    if not isinstance(data, dict):
        logger.warning("患者JSON结构异常，已跳过: %s", str(filepath))
        return {}
    result = []
    records = data.get("程控记录", data.get("records", []))
    if not isinstance(records, list):
        return result
    for record in records:
        meta = record.get("meta", {})
        fn = meta.get("filename", "")
        if fn:
            result.append({
                "source_id": meta.get("source_id", ""),
                "filename": fn,
                "raw_record": record,
            })
    return result


def build_source_index():
    """一次性建立 source_id 与文件名索引，杜绝按同名文件随机取第一个。"""
    by_id = {}
    by_filename = defaultdict(list)
    for root, dirs, files in os.walk(DATA_REPOSITORY):
        dirs.sort()
        for filename in sorted(files):
            if filename.startswith("~$") or not filename.lower().endswith((".xls", ".xlsx")):
                continue
            path = os.path.join(root, filename)
            source_id = stable_source_id(path)
            by_id[source_id] = path
            by_filename[filename].append(path)
    return by_id, by_filename


def get_audit_anchors(handler):
    """审计专用锚点扫描，不复用生产提取器的定位逻辑。"""
    anchors = {"basic": None, "antitachy": None, "test": None, "event": None}
    at_af_row = None
    keywords = {
        "basic": KW_BASIC,
        "antitachy": KW_ANTITACHY,
        "test": KW_TEST,
        "event": KW_EVENT,
    }
    for row in range(handler.nrows):
        for col in range(min(5, handler.ncols)):
            value = clean_value(handler.get_cell_value(row, col))
            for name, keyword in keywords.items():
                if anchors[name] is None and keyword in value:
                    anchors[name] = row
            if at_af_row is None and "AT/AF事件" in value:
                at_af_row = row
    if anchors["event"] is None:
        anchors["event"] = at_af_row
    return anchors


def _values_match(a, b):
    """智能匹配：处理数值格式差异（60.0 vs 60）和空格差异"""
    if a == b:
        return True
    try:
        if abs(float(a) - float(b)) < 0.01:
            return True
    except (ValueError, TypeError):
        logger.debug("value-match numeric conversion failed", extra={"expected": a, "extracted": b})
    a_text = str(a).replace(" ", "").replace("　", "").lower()
    b_text = str(b).replace(" ", "").replace("　", "").lower()
    return a_text == b_text


def _find_in_excel(handler, key, expected_value, start_row=0, end_row=None):
    """独立查找标签右侧值；多处同名标签无法消歧时显式报告 AMBIGUOUS。"""
    if not key:
        return ""
    key_str = str(key).strip()
    end_row = handler.nrows if end_row is None else min(end_row, handler.nrows)
    candidates = []
    for r in range(max(0, start_row), end_row):
        for c in range(handler.ncols):
            cell_val = clean_value(handler.get_cell_value(r, c))
            if cell_val and cell_val.strip() == key_str:
                for offset in range(1, 8):
                    next_col = c + offset
                    if next_col >= handler.ncols:
                        break
                    value = clean_value(handler.get_cell_value(r, next_col))
                    if value and handler.is_blue_cell(r, next_col):
                        break
                    if value:
                        candidates.append(value)
                        break
    if not candidates:
        return "__NOT_FOUND__"
    matched = [candidate for candidate in candidates if _values_match(candidate, expected_value)]
    if matched:
        return matched[0]
    unique = list(dict.fromkeys(candidates))
    return unique[0] if len(unique) == 1 else "__AMBIGUOUS__"


def _table_value_oracle(handler, start_row, end_row, key, row_headers, col_headers):
    """用原始单元格行/列表头交叉定位表格值，不调用生产表格提取函数。"""
    row_label = next((item for item in row_headers if key.startswith(f"{item}_")), None)
    if not row_label:
        return "__NOT_FOUND__"
    col_label = key[len(row_label) + 1:]
    if col_label not in col_headers:
        return "__NOT_FOUND__"

    row_index = None
    col_index = None
    for row in range(max(0, start_row), min(end_row, handler.nrows)):
        for col in range(handler.ncols):
            value = clean_value(handler.get_cell_value(row, col))
            if row_index is None and value == row_label:
                row_index = row
            if col_index is None and col_label in value:
                col_index = col
        if row_index is not None and col_index is not None:
            break
    if row_index is None or col_index is None:
        return "__NOT_FOUND__"
    value = clean_value(handler.get_cell_value(row_index, col_index))
    if not value:
        value = clean_value(handler.get_cell_value(row_index, col_index + 1))
    return value or "__NOT_FOUND__"


def _footer_date_oracle(handler, start_row, expected_value):
    """独立扫描页脚日期；签名自由文本不以同一提取函数回读验证。"""
    date_pattern = re.compile(r"\d{4}\s*[-./年]\s*\d{1,2}\s*[-./月]\s*\d{1,2}\s*[日]?")
    candidates = []
    for row in range(max(0, start_row), min(handler.nrows, start_row + 50)):
        for col in range(handler.ncols):
            value = clean_value(handler.get_cell_value(row, col))
            if value:
                match = date_pattern.search(value)
                if match:
                    candidates.append(match.group(0))
    if not candidates:
        return "__NOT_FOUND__"
    matched = [candidate for candidate in candidates if _values_match(candidate, expected_value)]
    if matched:
        return matched[0]
    unique = list(dict.fromkeys(candidates))
    return unique[0] if len(unique) == 1 else "__AMBIGUOUS__"


# ============================================================
# 核心：审计单条记录
# ============================================================

def audit_single_record(source_path, extracted_record):
    """
    审计单条记录：对比 Excel 原始值与提取值。
    返回字段审计列表，每项: {section, key, excel_val, extracted_val, status}
    """
    fields = []
    filename = os.path.basename(source_path)
    handler = None
    try:
        handler = get_handler(source_path)
    except Exception as e:
        return [{"section": "ERROR", "key": "OPEN_FILE", "excel_val": "", "extracted_val": "", "status": "ERROR", "detail": str(e)}]

    try:
        raw_record = extracted_record.get("raw_record", {})
        anchors = get_audit_anchors(handler)

        header_end = anchors["basic"] if anchors["basic"] is not None else min(5, handler.nrows)
        basic_start = anchors["basic"] if anchors["basic"] is not None else 0
        basic_end = anchors["antitachy"] if anchors["antitachy"] is not None else (
            anchors["test"] if anchors["test"] is not None else handler.nrows
        )
        test_start = anchors["test"] if anchors["test"] is not None else basic_end
        test_end = anchors["event"] if anchors["event"] is not None else handler.nrows
        event_start = anchors["event"] if anchors["event"] is not None else test_end

        def add_field(section, key, excel_val, extracted_val, status_override=None):
            ev = str(excel_val).strip() if excel_val else ""
            xv = str(extracted_val).strip() if extracted_val else ""
            if status_override:
                status = status_override
            elif ev == "__AMBIGUOUS__":
                status = "AMBIGUOUS"
                ev = ""
            elif ev == "__NOT_FOUND__":
                status = "NOT_FOUND"
                ev = ""
            elif not ev and not xv:
                status = "BOTH_EMPTY"
            elif not ev and xv:
                status = "PHANTOM"
            elif ev and not xv:
                status = "MISSING"
            elif _values_match(ev, xv):
                status = "MATCH"
            else:
                status = "MISMATCH"
            if status == "BOTH_EMPTY":
                return
            if status == "NOT_FOUND" and not xv:
                return
            fields.append({
                "section": section, "key": key, "excel_val": ev,
                "extracted_val": xv, "status": status,
            })

        # 1. Header 与 2. 设置：独立的标签-右侧值查找。
        for key, value in raw_record.get("header", {}).items():
            add_field("header", key, _find_in_excel(handler, key, value, 0, header_end), value)

        settings = raw_record.get("basic_params", {}).get("settings", {})
        for key, value in settings.items():
            add_field("settings", key, _find_in_excel(handler, key, value, basic_start, basic_end), value)

        # 3. 基础表格和 5. 阈值表格：独立的行/列表头交叉定位。
        measurements = raw_record.get("basic_params", {}).get("measurements", {})
        for key, value in measurements.items():
            add_field(
                "measurements", key,
                _table_value_oracle(handler, basic_start, basic_end, key, Z2_ROW_HEADERS, Z2_COL_HEADERS),
                value,
            )

        battery = raw_record.get("test_params", {}).get("battery_and_leads", {})
        for key, value in battery.items():
            add_field("battery", key, _find_in_excel(handler, key, value, test_start, test_end), value)

        thresholds = raw_record.get("test_params", {}).get("threshold_tests", {})
        for key, value in thresholds.items():
            add_field(
                "thresholds", key,
                _table_value_oracle(handler, test_start, test_end, key, Z3_ROW_HEADERS, Z3_COL_HEADERS),
                value,
            )

        # 6. 事件：仅以原始表格中的同名标签和值作为审计依据。
        events = raw_record.get("events_and_footer", {})
        for key, value in events.items():
            add_field("events", key, _find_in_excel(handler, key, value, event_start, handler.nrows), value)

        # 7. 页脚：日期独立扫描；签名自由文本要求人工抽查，不再循环回读生产函数。
        footer = raw_record.get("footer_meta", {})
        for key, value in footer.items():
            if not value:
                continue
            if key == "程控日期":
                add_field("footer", key, _footer_date_oracle(handler, event_start, value), value)
            else:
                add_field("footer", key, "", value, status_override="UNVERIFIED")

        # 8. 抗心动过速参数：同样采用独立行/列表头交叉定位。
        antitachy = raw_record.get("antitachy_params", {})
        antitachy_start = anchors["antitachy"] if anchors["antitachy"] is not None else 0
        antitachy_end = anchors["test"] if anchors["test"] is not None else handler.nrows
        for key, value in antitachy.items():
            if isinstance(value, dict):
                for child_key, child_value in value.items():
                    composite = f"{key}_{child_key}"
                    add_field(
                        "antitachy", composite,
                        _table_value_oracle(
                            handler, antitachy_start, antitachy_end, composite,
                            ZAT_ROW_HEADERS, ZAT_COL_HEADERS,
                        ),
                        child_value,
                    )
            else:
                add_field(
                    "antitachy", key,
                    _table_value_oracle(
                        handler, antitachy_start, antitachy_end, key,
                        ZAT_ROW_HEADERS, ZAT_COL_HEADERS,
                    ),
                    value,
                )
    finally:
        if handler is not None and hasattr(handler, 'close'):
            try:
                handler.close()
            except Exception as e:
                logger.warning("关闭 handler 失败", extra={"file": filename, "error": str(e)})

    return fields


# ============================================================
# 问题分类（合并自 audit_analyzer.py）
# ============================================================

def build_record_maps():
    """构建跨记录映射，用于分类 CROSS_SHEET / CROSS_RECORD"""
    filename_record_count = Counter()
    multi_patient_files = set()
    for pf in PATIENT_RECORDS_DIR.glob("*.json"):
        if pf.name in ('processed_files.json', 'matching_report.csv'):
            continue
        try:
            with open(pf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            filenames = [r.get('meta', {}).get('filename', '') for r in data.get('程控记录', [])]
            for fn in filenames:
                filename_record_count[fn] += 1
            if len(filenames) > 1:
                for fn in filenames:
                    multi_patient_files.add(fn)
        except Exception as e:
            logger.warning("build_record_maps: skip file due parse error", extra={"file": str(pf)})
            logger.debug("build_record_maps exception", exc_info=True, extra={"file": str(pf), "error": str(e)})
    return filename_record_count, multi_patient_files


def classify_issue(field, filename, fn_count, multi_files):
    """对 MISMATCH/MISSING 字段进行根因分类"""
    key = field["key"]
    ev = field["excel_val"]
    xv = field["extracted_val"]
    status = field["status"]

    if key == "姓名":
        return "NAME_TYPO"
    if fn_count.get(filename, 1) > 1:
        return "CROSS_SHEET"
    if filename in multi_files and ev and xv and ev != xv:
        return "CROSS_RECORD"
    if '→' in ev or '⇒' in ev:
        return "ARROW_VALUE"
    if ev and ev[0] in ('>', '<', '≥', '≤', '＞', '＜'):
        return "SYMBOL_PREFIX"
    if '#NAME?' in ev or '#REF!' in ev or '#VALUE!' in ev:
        return "EXCEL_ERROR"
    if status == "MISSING":
        return "EXTRACTION_MISSING"
    if key == "植入日期":
        return "DATE_FORMAT"
    try:
        if abs(float(ev) - float(xv)) / max(abs(float(ev)), 0.01) < 0.05:
            return "NUMERIC_NOISE"
    except (ValueError, TypeError):
        logger.debug("Numeric tolerance check skipped", extra={"ev": ev, "xv": xv})
    return "TRUE_MISMATCH"


# ============================================================
# 主流程
# ============================================================

def run_audit(target_file=None, sample_size=None):
    """执行独立审计，并同时检查源文件与输出记录的覆盖完整性。"""
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    source_by_id, source_by_filename = build_source_index()
    patient_files = [
        path for path in PATIENT_RECORDS_DIR.glob("*.json")
        if path.name != "processed_files.json"
    ]
    if not patient_files:
        logger.error("未找到患者记录文件")
        return None

    output_records = []
    for patient_file in patient_files:
        output_records.extend(read_extracted_json(patient_file))

    audit_pairs = []
    unresolved_records = []
    represented_source_ids = set()
    for record_data in output_records:
        source_id = record_data.get("source_id", "")
        filename = record_data.get("filename", "")
        if target_file and target_file not in filename:
            continue
        source_path = source_by_id.get(source_id)
        if source_path is None:
            candidates = source_by_filename.get(filename, [])
            if len(candidates) == 1:
                source_path = candidates[0]
                source_id = stable_source_id(source_path)
            else:
                unresolved_records.append({
                    "filename": filename,
                    "source_id": source_id,
                    "reason": "SOURCE_NOT_FOUND" if not candidates else "AMBIGUOUS_FILENAME",
                })
                continue
        represented_source_ids.add(source_id)
        audit_pairs.append((source_path, source_id, filename, record_data))

    sampled = bool(sample_size and sample_size < len(audit_pairs))
    if sampled:
        audit_pairs = random.Random(0).sample(audit_pairs, sample_size)

    expected_source_ids = {
        source_id for source_id, path in source_by_id.items()
        if not target_file or target_file in os.path.basename(path)
    }
    missing_source_ids = [] if sampled else sorted(expected_source_ids - represented_source_ids)
    logger.info("独立审计 %s 条记录（源文件覆盖 %s/%s）...", len(audit_pairs), len(represented_source_ids), len(expected_source_ids))

    fn_count, multi_files = build_record_maps()
    records = {}
    status_totals = Counter()
    category_totals = Counter()
    section_stats = defaultdict(lambda: {"total": 0, "match": 0, "mismatch": 0, "missing": 0})
    issues_list = []

    for index, (source_path, source_id, source_filename, record_data) in enumerate(audit_pairs):
        if (index + 1) % 50 == 0:
            logger.info("  进度: %s/%s...", index + 1, len(audit_pairs))
        try:
            fields = audit_single_record(source_path, record_data)
        except Exception as error:
            logger.error("审计失败: %s - %s", source_filename, error)
            fields = [{
                "section": "ERROR", "key": "AUDIT", "excel_val": "", "extracted_val": "",
                "status": "ERROR", "detail": str(error),
            }]

        record_fields = []
        for field in fields:
            field_copy = dict(field)
            status = field["status"]
            status_totals[status] += 1
            section = field["section"]
            section_stats[section]["total"] += 1
            if status == "MATCH":
                section_stats[section]["match"] += 1
            elif status in ("MISMATCH", "MISSING"):
                section_stats[section]["mismatch" if status == "MISMATCH" else "missing"] += 1

            if status in ("MISMATCH", "MISSING"):
                category = classify_issue(field, source_filename, fn_count, multi_files)
                field_copy["category"] = category
                category_totals[category] += 1
            elif status not in ("MATCH", "UNVERIFIED"):
                field_copy["category"] = f"AUDIT_{status}"
                category_totals[field_copy["category"]] += 1

            if status not in ("MATCH", "UNVERIFIED"):
                issues_list.append({"file": source_filename, "source_id": source_id, **field_copy})
            record_fields.append(field_copy)

        verified = [field for field in record_fields if field["status"] not in ("UNVERIFIED",)]
        match_count = sum(1 for field in verified if field["status"] == "MATCH")
        record_key = source_id or f"{source_filename}#{index}"
        records[record_key] = {
            "filename": source_filename,
            "fields": record_fields,
            "summary": {
                "total": len(record_fields),
                "verified": len(verified),
                "match": match_count,
                "accuracy": round(match_count / len(verified), 4) if verified else None,
            },
        }

    total_fields = sum(status_totals.values())
    verified_total = total_fields - status_totals.get("UNVERIFIED", 0)
    total_match = status_totals.get("MATCH", 0)
    accuracy = round(total_match / verified_total, 4) if verified_total else None
    missing_source_records = [
        {"source_id": source_id, "filename": os.path.basename(source_by_id[source_id])}
        for source_id in missing_source_ids
    ]

    # 身份不一致、幻影字段、歧义和覆盖缺失都不能再被计入“可忽略问题”。
    ignorable_cats = {"ARROW_VALUE", "SYMBOL_PREFIX", "EXCEL_ERROR", "DATE_FORMAT", "NUMERIC_NOISE"}
    ignorable = sum(value for key, value in category_totals.items() if key in ignorable_cats)
    actionable = len(issues_list) + len(unresolved_records) + len(missing_source_records)
    coverage_complete = not sampled and not unresolved_records and not missing_source_records

    result = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "audit_method": "independent_oracle_v1",
            "sampled": sampled,
            "total_records": len(records),
            "total_fields": total_fields,
        },
        "coverage": {
            "source_files": len(expected_source_ids),
            "represented_source_files": len(represented_source_ids),
            "complete": coverage_complete,
            "unresolved_output_records": unresolved_records,
            "missing_source_records": missing_source_records,
        },
        "summary": {
            "by_status": dict(status_totals),
            "by_category": dict(category_totals),
            "by_section": {key: dict(value) for key, value in section_stats.items()},
            "accuracy": accuracy,
            "verified_fields": verified_total,
            "unverified_fields": status_totals.get("UNVERIFIED", 0),
            "ignorable_issues": ignorable,
            "actionable_issues": actionable,
        },
        "actionable_issues": issues_list[:200],
        "records": records,
    }
    atomic_write_json(AUDIT_JSON, result)

    print("=" * 60)
    print(f"独立审计完成 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    print(f"记录数: {len(records)}   字段数: {total_fields}")
    print(f"源文件覆盖: {len(represented_source_ids)}/{len(expected_source_ids)}   完整: {coverage_complete}")
    print("匹配状态:")
    for status in ("MATCH", "MISMATCH", "MISSING", "NOT_FOUND", "PHANTOM", "AMBIGUOUS", "UNVERIFIED", "ERROR"):
        if status_totals.get(status, 0) > 0:
            print(f"  {status}: {status_totals[status]}")
    print(f"独立可验证字段准确率: {'N/A' if accuracy is None else f'{accuracy * 100:.1f}%'}")
    print(f"需关注: {actionable}   仅人工复核: {status_totals.get('UNVERIFIED', 0)}")
    print(f"JSON 报告: {AUDIT_JSON}")
    print("=" * 60)
    return result


def main():
    parser = argparse.ArgumentParser(description='数据提取准确性审计 (JSON)')
    parser.add_argument('--file', '-f', type=str, default=None)
    parser.add_argument('--sample', '-s', type=int, default=None)
    args = parser.parse_args()
    run_audit(target_file=args.file, sample_size=args.sample)


if __name__ == "__main__":
    main()

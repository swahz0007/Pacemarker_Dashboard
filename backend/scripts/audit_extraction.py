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
    Z2_COL_HEADERS, Z2_ROW_HEADERS, Z3_COL_HEADERS, Z3_ROW_HEADERS,
)
from core.handlers import get_handler
from core.utils import clean_value
from core.extractors import (
    extract_table_in_range, get_anchors,
    extract_events_flexible, extract_antitachy_table,
    extract_footer_info, extract_kv_in_range,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = BACKEND_DIR.parent
DOC_DIR = PROJECT_ROOT / "doc"
AUDIT_JSON = DOC_DIR / "audit_result.json"


# ============================================================
# 工具函数
# ============================================================

def read_extracted_json(filepath):
    """读取患者 JSON，返回 {source_filename: record_data} 映射"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error("读取患者JSON失败，已跳过: %s", str(filepath), extra={"file": str(filepath), "error": str(e)})
        return {}
    if not isinstance(data, dict):
        logger.warning("患者JSON结构异常，已跳过: %s", str(filepath))
        return {}
    result = {}
    for record in data.get("程控记录", []):
        meta = record.get("meta", {})
        fn = meta.get("filename", "")
        if fn:
            result[fn] = {"raw_record": record, "flat_fields": {}}
    return result


def find_source_file(filename):
    """在数据仓库中查找源 Excel 文件"""
    for root, dirs, files in os.walk(DATA_REPOSITORY):
        if filename in files:
            return os.path.join(root, filename)
    return None


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


def _find_in_excel(handler, key, expected_value):
    """在 Excel 中查找简单键值字段（标签→右侧值）"""
    if not key:
        return ""
    key_str = str(key).strip()
    key_positions = []
    for r in range(handler.nrows):
        for c in range(handler.ncols):
            cell_val = clean_value(handler.get_cell_value(r, c))
            if cell_val and cell_val.strip() == key_str:
                key_positions.append((r, c))
    if key_positions:
        for kr, kc in key_positions:
            for offset in range(1, 8):
                nc = kc + offset
                if nc >= handler.ncols:
                    break
                val = clean_value(handler.get_cell_value(kr, nc))
                if val and handler.is_blue_cell(kr, nc):
                    break
                if val:
                    return val
        return "__NOT_FOUND__"
    return "__NOT_FOUND__"


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
        anchors = get_anchors(handler)

        def add_field(section, key, excel_val, extracted_val):
            ev = str(excel_val).strip() if excel_val else ""
            xv = str(extracted_val).strip() if extracted_val else ""
            if ev == "__NOT_FOUND__":
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
            # 过滤无意义字段：双方都没有数据的不纳入统计
            if status == "BOTH_EMPTY":
                return
            if status == "NOT_FOUND" and not xv:
                return  # Excel 找不到 + 系统也没提取到 = 该字段不存在（如左心室在双腔起搏器中）
            fields.append({"section": section, "key": key, "excel_val": ev, "extracted_val": xv, "status": status})

        # 1. Header
        header = raw_record.get("header", {})
        for key, val in header.items():
            add_field("header", key, _find_in_excel(handler, key, val), val)

        # 2. Basic Params - Settings (KV)
        settings = raw_record.get("basic_params", {}).get("settings", {})
        for key, val in settings.items():
            add_field("settings", key, _find_in_excel(handler, key, val), val)

        # 3. Basic Params - Measurements (表格重提取)
        measurements = raw_record.get("basic_params", {}).get("measurements", {})
        if measurements:
            basic_start = (anchors.get("basic") or 0) + 1
            basic_end = anchors.get("antitachy") or anchors.get("test") or handler.nrows
            re_z2 = extract_table_in_range(handler, basic_start, basic_end, Z2_COL_HEADERS, Z2_ROW_HEADERS)
            for key, val in measurements.items():
                re_val = re_z2.get(key, "__NOT_FOUND__")
                add_field("measurements", key, re_val or "__NOT_FOUND__", val)

        # 4. Test Params - Battery (KV)
        battery = raw_record.get("test_params", {}).get("battery_and_leads", {})
        for key, val in battery.items():
            add_field("battery", key, _find_in_excel(handler, key, val), val)

        # 5. Test Params - Thresholds (表格重提取)
        thresholds = raw_record.get("test_params", {}).get("threshold_tests", {})
        if thresholds:
            test_start = (anchors.get("test") or 0) + 1
            test_end = anchors.get("event") or handler.nrows
            re_z3 = extract_table_in_range(handler, test_start, test_end, Z3_COL_HEADERS, Z3_ROW_HEADERS)
            for key, val in thresholds.items():
                re_val = re_z3.get(key, "__NOT_FOUND__")
                add_field("thresholds", key, re_val or "__NOT_FOUND__", val)

        # 6. Events (重提取)
        events = raw_record.get("events_and_footer", {})
        if events:
            event_start = anchors.get("event") or 0
            re_events = extract_events_flexible(handler, event_start, handler.nrows)
            for key, val in events.items():
                re_val = re_events.get(key)
                if re_val is not None:
                    excel_val = re_val or "__NOT_FOUND__"
                else:
                    excel_val = _find_in_excel(handler, key, val)
                add_field("events", key, excel_val, val)

        # 7. Footer Meta (重提取)
        footer = raw_record.get("footer_meta", {})
        if footer:
            # 用与提取脚本相同的逻辑重新提取签名和日期
            event_start = anchors.get("event") or 0
            _, conc_row = extract_kv_in_range(handler, event_start, handler.nrows)
            if conc_row is not None:
                re_sig, re_date = extract_footer_info(handler, conc_row)
            else:
                re_sig, re_date = extract_footer_info(handler, event_start)
            re_footer = {"签名行内容": re_sig, "程控日期": re_date}
            for key, val in footer.items():
                if val:
                    re_val = re_footer.get(key, "__NOT_FOUND__")
                    add_field("footer", key, re_val or "__NOT_FOUND__", val)

        # 8. Antitachy (重提取)
        antitachy = raw_record.get("antitachy_params", {})
        if antitachy:
            at_start = (anchors.get("antitachy") or 0) + 1
            at_end = anchors.get("test") or handler.nrows
            re_at = extract_antitachy_table(handler, at_start, at_end)
            flat_at = {}
            for rk, cols in re_at.items():
                if isinstance(cols, dict):
                    for ck, cv in cols.items():
                        flat_at[f"{rk}_{ck}"] = cv
                        flat_at[f"{rk}.{ck}"] = cv
                else:
                    flat_at[rk] = cols
            for key, val in antitachy.items():
                if isinstance(val, dict):
                    for k2, v2 in val.items():
                        composite = f"{key}.{k2}"
                        re_val = flat_at.get(composite) or flat_at.get(f"{key}_{k2}")
                        if re_val is not None:
                            excel_val = re_val or "__NOT_FOUND__"
                        else:
                            excel_val = _find_in_excel(handler, k2, v2)
                        add_field("antitachy", composite, excel_val, v2)
                else:
                    re_val = flat_at.get(key)
                    if re_val is not None:
                        excel_val = re_val or "__NOT_FOUND__"
                    else:
                        excel_val = _find_in_excel(handler, key, val)
                    add_field("antitachy", key, excel_val, val)
    except Exception:
        raise
    # end audit
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
    DOC_DIR.mkdir(parents=True, exist_ok=True)

    # 收集患者 JSON
    patient_files = [f for f in PATIENT_RECORDS_DIR.glob("*.json")
                     if f.name not in ('processed_files.json', 'matching_report.csv')]
    if not patient_files:
        logger.error("未找到患者记录文件")
        return

    # 收集审计对
    audit_pairs = []
    for pf in patient_files:
        extracted = read_extracted_json(pf)
        for src_fn, record_data in extracted.items():
            if target_file and target_file not in src_fn:
                continue
            src_path = find_source_file(src_fn)
            if src_path:
                audit_pairs.append((src_path, src_fn, record_data))

    if sample_size and sample_size < len(audit_pairs):
        audit_pairs = random.sample(audit_pairs, sample_size)

    logger.info(f"审计 {len(audit_pairs)} 条记录...")

    # 构建分类映射
    fn_count, multi_files = build_record_maps()

    # 执行审计
    records = {}
    status_totals = Counter()
    category_totals = Counter()
    section_stats = defaultdict(lambda: {"total": 0, "match": 0, "mismatch": 0, "missing": 0})
    issues_list = []  # 汇总所有真正需要关注的问题

    for i, (src_path, src_fn, record_data) in enumerate(audit_pairs):
        if (i + 1) % 50 == 0:
            logger.info(f"  进度: {i+1}/{len(audit_pairs)}...")

        try:
            fields = audit_single_record(src_path, record_data)
        except Exception as e:
            logger.error(f"审计失败: {src_fn} - {e}")
            fields = [{"section": "ERROR", "key": "AUDIT", "excel_val": "", "extracted_val": "", "status": "ERROR", "detail": str(e)}]

        # 分类每个字段
        record_fields = []
        for f in fields:
            f_copy = dict(f)
            status_totals[f["status"]] += 1
            sec = f["section"]
            section_stats[sec]["total"] += 1

            if f["status"] == "MATCH":
                section_stats[sec]["match"] += 1
            elif f["status"] in ("MISMATCH", "MISSING"):
                section_stats[sec]["mismatch" if f["status"] == "MISMATCH" else "missing"] += 1
                category = classify_issue(f, src_fn, fn_count, multi_files)
                f_copy["category"] = category
                category_totals[category] += 1
                if category in ("TRUE_MISMATCH", "EXTRACTION_MISSING"):
                    issues_list.append({"file": src_fn, **f_copy})

            record_fields.append(f_copy)

        rec_match = sum(1 for f in record_fields if f["status"] == "MATCH")
        rec_total = len(record_fields)
        records[src_fn] = {
            "fields": record_fields,
            "summary": {
                "total": rec_total,
                "match": rec_match,
                "accuracy": round(rec_match / rec_total, 4) if rec_total else 0,
            }
        }

    # 汇总
    total_fields = sum(status_totals.values())
    total_match = status_totals.get("MATCH", 0)

    # 准确率：排除 CROSS_SHEET（数据源多sheet问题，非提取错误）
    cross_sheet_noise = category_totals.get("CROSS_SHEET", 0)
    effective_issues = (status_totals.get("MISMATCH", 0) + status_totals.get("MISSING", 0)) - cross_sheet_noise
    effective_verified = total_match + effective_issues
    accuracy = round(total_match / effective_verified, 4) if effective_verified else 0

    # 可忽略 vs 需关注（CROSS_SHEET 单独标注）
    noise_cats = {"CROSS_SHEET"}  # 不计入准确率的噪音
    ignorable_cats = {"NAME_TYPO", "CROSS_RECORD", "ARROW_VALUE",
                       "SYMBOL_PREFIX", "EXCEL_ERROR", "DATE_FORMAT", "NUMERIC_NOISE"}
    noise = sum(v for k, v in category_totals.items() if k in noise_cats)
    ignorable = sum(v for k, v in category_totals.items() if k in ignorable_cats)
    actionable = sum(v for k, v in category_totals.items() if k not in noise_cats and k not in ignorable_cats)

    result = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "total_records": len(records),
            "total_fields": total_fields,
        },
        "summary": {
            "by_status": dict(status_totals),
            "by_category": dict(category_totals),
            "by_section": {k: dict(v) for k, v in section_stats.items()},
            "accuracy": accuracy,
            "cross_sheet_noise": noise,
            "ignorable_issues": ignorable,
            "actionable_issues": actionable,
        },
        "actionable_issues": issues_list[:200],  # 截断防文件过大
        "records": records,
    }

    with open(AUDIT_JSON, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 终端摘要
    print("=" * 60)
    print(f"审计完成 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    print(f"记录数: {len(records)}   字段数: {total_fields}")
    print(f"")
    print(f"匹配状态:")
    for s in ("MATCH", "MISMATCH", "MISSING", "NOT_FOUND", "PHANTOM", "ERROR"):
        if status_totals.get(s, 0) > 0:
            print(f"  {s}: {status_totals[s]}")
    print(f"")
    print(f"问题分类 ({sum(category_totals.values())} 条):")
    all_skip = noise_cats | ignorable_cats
    for cat, cnt in category_totals.most_common():
        tag = "[noise]" if cat in noise_cats else ("[skip]" if cat in ignorable_cats else "[FIX!]")
        print(f"  {tag} {cat}: {cnt}")
    print(f"")
    print(f"准确率 (排除多sheet噪音+无法验证): {accuracy*100:.1f}%")
    print(f"多sheet噪音: {noise}   可忽略: {ignorable}   需修复: {actionable}")
    print(f"")
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

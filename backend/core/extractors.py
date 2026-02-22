"""
数据提取器模块
核心数据抽取逻辑
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    KW_BASIC, KW_ANTITACHY, KW_TEST, KW_EVENT,
    ZAT_COL_HEADERS, ZAT_ROW_HEADERS,
    Z2_COL_HEADERS, Z2_ROW_HEADERS,
    Z3_COL_HEADERS, Z3_ROW_HEADERS
)
from core.handlers import get_handler
from core.utils import (
    clean_value, clean_label, is_ignored,
    extract_name_from_filename, excel_date_to_str
)


def get_anchors(handler):
    """查找关键区域的锚点行号"""
    anchors = {"basic": None, "antitachy": None, "test": None, "event": None}
    at_af_row = None  # 备选：AT/AF事件行
    
    for r in range(handler.nrows):
        for c in range(min(5, handler.ncols)):
            val = str(handler.get_cell_value(r, c)).strip()
            if KW_BASIC in val:
                anchors["basic"] = r
            elif KW_ANTITACHY in val:
                anchors["antitachy"] = r
            elif KW_TEST in val:
                anchors["test"] = r
            elif KW_EVENT in val:
                anchors["event"] = r
            # 备选：检测AT/AF事件行（用于没有"事件记录"标题的模板）
            elif at_af_row is None and "AT/AF事件" in val:
                at_af_row = r
    
    # 如果没有找到"事件记录"锚点，使用AT/AF事件行作为备选
    if anchors["event"] is None and at_af_row is not None:
        anchors["event"] = at_af_row
    
    return anchors


def extract_antitachy_table(handler, start_row, end_row):
    """提取抗心动过速参数表格 (ICD/CRT-D 特有)"""
    data = {}
    col_positions = {}
    
    for r in range(start_row, min(start_row + 5, end_row)):
        for c in range(handler.ncols):
            val = clean_label(handler.get_cell_value(r, c))
            for h in ZAT_COL_HEADERS:
                if h in val and h not in col_positions:
                    col_positions[h] = c
    
    for r in range(start_row, end_row):
        for c in range(min(3, handler.ncols)):
            val = clean_label(handler.get_cell_value(r, c))
            for rh in ZAT_ROW_HEADERS:
                if val == rh:
                    freq_val = ""
                    treat_val = ""
                    if "检测频率" in col_positions:
                        freq_col = col_positions["检测频率"]
                        freq_val = clean_value(handler.get_cell_value(r, freq_col))
                        if not freq_val:
                            freq_val = clean_value(handler.get_cell_value(r, freq_col + 1))
                    if "治疗" in col_positions:
                        treat_col = col_positions["治疗"]
                        treat_val = clean_value(handler.get_cell_value(r, treat_col))
                        if not treat_val:
                            treat_val = clean_value(handler.get_cell_value(r, treat_col + 1))
                    data[f"{rh}_检测频率"] = freq_val
                    data[f"{rh}_治疗"] = treat_val
    return data


def find_value_smart(handler, r, start_c):
    """智能查找值：跳过合并单元格的 None 值"""
    for offset in range(1, 8):
        curr_c = start_c + offset
        if curr_c >= handler.ncols:
            break
        val = clean_value(handler.get_cell_value(r, curr_c))
        if handler.is_blue_cell(r, curr_c) and val:
            break
        if val:
            return val
    return ""


def extract_kv_in_range(handler, start_row, end_row):
    """在指定范围内提取键值对"""
    data = {}
    conclusion_row = None
    for r in range(start_row, end_row):
        for c in range(handler.ncols):
            if handler.is_blue_cell(r, c):
                label = clean_label(handler.get_cell_value(r, c))
                if "结论" in label:
                    conclusion_row = r
                if label and not is_ignored(label):
                    data[label] = find_value_smart(handler, r, c)
    return data, conclusion_row


def extract_table_in_range(handler, start_row, end_row, col_headers, row_headers):
    """提取表格数据"""
    data, f_cols, f_rows = {}, {}, {}
    for r in range(start_row, end_row):
        for c in range(handler.ncols):
            val = clean_label(handler.get_cell_value(r, c))
            for h in col_headers:
                if h in val and h not in f_cols:
                    f_cols[h] = c
            for h in row_headers:
                if h == val and h not in f_rows:
                    f_rows[h] = r
    for rh, ri in f_rows.items():
        for ch, ci in f_cols.items():
            val = clean_value(handler.get_cell_value(ri, ci))
            if not val:
                val = clean_value(handler.get_cell_value(ri, ci + 1))
            data[f"{rh}_{ch}"] = val
    return data


def extract_footer_info(handler, conc_row):
    """提取页脚信息"""
    import re
    full_lines = []
    date_str = ""
    date_pattern = re.compile(r"\d{4}\s*[-./年]\s*\d{1,2}\s*[-./月]\s*\d{1,2}\s*[日]?")

    def has_data_in_rows(start_row, end_row):
        for r in range(start_row, end_row):
            row_content = [
                clean_value(handler.get_cell_value(r, c)) for c in range(handler.ncols)
            ]
            line = " ".join([x for x in row_content if x])
            if line:
                return True
        return False

    # 扩大扫描范围：确保能覆盖表格最后50行
    scan_range = 2
    max_scan = min(handler.nrows - conc_row, 50)  # 最多扫描50行

    while scan_range <= max_scan:
        if has_data_in_rows(conc_row + 1, conc_row + 1 + scan_range):
            break
        scan_range += 1
        if scan_range > 50:  # 扩展到50行
            break

    for r in range(conc_row + 1, min(conc_row + 1 + scan_range, handler.nrows)):
        row_content = []
        for c in range(handler.ncols):
            raw_val = handler.get_cell_value(r, c)
            
            # 优先检测Excel日期序列号
            if not date_str:
                excel_date = excel_date_to_str(raw_val)
                if excel_date:
                    date_str = excel_date
            
            cleaned = clean_value(raw_val)
            if cleaned:
                row_content.append(cleaned)
        
        line = " ".join(row_content)
        if line:
            full_lines.append(line)
            # 同时检测文本格式日期
            if not date_str:
                match = date_pattern.search(line)
                if match:
                    date_str = match.group(0)

    return " | ".join(full_lines), date_str


def extract_events_flexible(handler, start_row, end_row):
    """更灵活的事件提取，支持非蓝色单元格"""
    data = {}
    for r in range(start_row, end_row):
        row_content = []
        for c in range(handler.ncols):
            val = clean_value(handler.get_cell_value(r, c))
            if val:
                row_content.append((c, val))
        if len(row_content) >= 2:
            for i in range(len(row_content) - 1):
                c1, v1 = row_content[i]
                if handler.is_blue_cell(r, c1):
                    key = v1
                    if not is_ignored(key) and len(key) > 0:
                        data[key] = find_value_smart(handler, r, c1)
    return data


def validate_and_fix_header(d_header: dict, filename: str) -> dict:
    """校验并修复 header 数据：姓名不匹配时仅用文件名姓名覆盖，但保留登记号"""
    import logging
    logger = logging.getLogger(__name__)
    
    header_name = d_header.get("姓名", "")
    filename_name = extract_name_from_filename(filename)
    
    if not header_name or not filename_name:
        return d_header
    
    # 姓名不匹配时，修正姓名但保留登记号（登记号是独立字段，不应被清空）
    if filename_name not in header_name and header_name not in filename_name:
        logger.warning(f"姓名不匹配: 文件名='{filename_name}', header='{header_name}', 文件={filename}")
        d_header["姓名"] = filename_name
    
    return d_header


def process_file(filepath, filename):
    """处理单个文件并返回结构化数据"""
    try:
        handler = get_handler(filepath)
        anchors = get_anchors(handler)
        
        rb = anchors["basic"] or handler.nrows
        rat = anchors["antitachy"]
        rt = anchors["test"] or handler.nrows
        re_row = anchors["event"] or handler.nrows
        basic_end = rat if rat else rt

        d_header, _ = extract_kv_in_range(handler, 0, rb)
        
        # 校验并修复 header 数据
        d_header = validate_and_fix_header(d_header, filename)
        
        d_basic, _ = extract_kv_in_range(handler, rb, basic_end)
        d_basic_tbl = extract_table_in_range(handler, rb, basic_end, Z2_COL_HEADERS, Z2_ROW_HEADERS)

        d_antitachy = {}
        if rat:
            d_antitachy = extract_antitachy_table(handler, rat, rt)

        d_test, _ = extract_kv_in_range(handler, rt, re_row)
        d_test_tbl = extract_table_in_range(handler, rt, re_row, Z3_COL_HEADERS, Z3_ROW_HEADERS)
        
        d_events, conc_row = extract_kv_in_range(handler, re_row, handler.nrows)
        d_events_flexible = extract_events_flexible(handler, re_row, handler.nrows)
        d_events.update(d_events_flexible)

        sig_text, sig_date = ("", "")
        if conc_row is not None:
            sig_text, sig_date = extract_footer_info(handler, conc_row)

        result = {
            "meta": {"filename": filename, "path": filepath},
            "header": d_header,
            "basic_params": {"settings": d_basic, "measurements": d_basic_tbl},
        }
        if d_antitachy:
            result["antitachy_params"] = d_antitachy

        result.update({
            "test_params": {"battery_and_leads": d_test, "threshold_tests": d_test_tbl},
            "events_and_footer": d_events,
            "footer_meta": {"签名行内容": sig_text, "程控日期": sig_date},
        })
        return result
    except Exception as e:
        return {"meta": {"filename": filename, "error": str(e)}}


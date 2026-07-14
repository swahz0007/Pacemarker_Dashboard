"""
数据提取器模块
核心数据抽取逻辑
"""

from pathlib import Path

from config import (
    KW_BASIC, KW_ANTITACHY, KW_TEST, KW_EVENT,
    ZAT_COL_HEADERS, ZAT_ROW_HEADERS,
    Z2_COL_HEADERS, Z2_ROW_HEADERS,
    Z3_COL_HEADERS, Z3_ROW_HEADERS,
    PIPELINE_VERSION, RECORD_SCHEMA_VERSION,
)
from core.handlers import get_handler
from core.utils import (
    clean_value, clean_label, is_ignored,
    extract_name_from_filename, excel_date_to_str, stable_source_id,
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


def find_full_row_text(handler, r, start_c):
    """读取 key 右侧所有非空非蓝色单元格的内容，拼接为完整文本。
    用于结论、事件说明等可能跨多列合并的长文本字段。"""
    parts = []
    for offset in range(1, handler.ncols - start_c):
        curr_c = start_c + offset
        if curr_c >= handler.ncols:
            break
        val = clean_value(handler.get_cell_value(r, curr_c))
        if handler.is_blue_cell(r, curr_c) and val:
            break  # 遇到下一个标签列，停止
        if val:
            parts.append(val)
    return "，".join(parts) if len(parts) > 1 else (parts[0] if parts else "")


# 需要读取全行文本的长文本字段
_LONG_TEXT_FIELDS = {"结论", "备注", "AT/AF事件说明", "快心室率事件说明",
                     "快心室率说明", "快心房率事件说明", "快心室率事件说明",
                     "其余事件", "建议下次程控时间"}

# 事件区域的重复列标签，由 extract_events_flexible 以复合键提取，kv 提取跳过
_EVENT_COL_LABELS = {"持续最长时间", "治疗类型"}


def extract_kv_in_range(handler, start_row, end_row):
    """在指定范围内提取键值对"""
    data = {}
    conclusion_row = None
    seen_labels = set()  # 防止合并单元格导致重复读取
    for r in range(start_row, end_row):
        for c in range(handler.ncols):
            if handler.is_blue_cell(r, c):
                label = clean_label(handler.get_cell_value(r, c))
                if "结论" in label:
                    conclusion_row = r
                if label and not is_ignored(label):
                    # 跳过事件区列标签（由 extract_events_flexible 以复合键提取）
                    if label in _EVENT_COL_LABELS:
                        continue
                    # 对于合并单元格产生的重复 label，只取第一次出现
                    if label in seen_labels:
                        continue
                    seen_labels.add(label)
                    # 长文本字段使用全行读取
                    if label in _LONG_TEXT_FIELDS:
                        data[label] = find_full_row_text(handler, r, c)
                    else:
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

    # 直接扫描结论行之后最多50行，提取签名和日期
    scan_end = min(conc_row + 1 + 50, handler.nrows)

    for r in range(conc_row + 1, scan_end):
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
    """更灵活的事件提取，支持非蓝色单元格和重复列标签。
    
    事件区域的典型行结构：
      [事件名次数] | 值 | [持续最长时间] | 值 | [负荷%/治疗类型] | 值
    
    对"持续最长时间"等重复列标签，生成复合键：
      AT/AF事件次数 → AT/AF_持续最长时间
      VF次数 → VF_持续最长时间
    """
    data = {}
    # 已知的"列标签"（在同一行中不作为独立 key，而是与行首标签组合）
    col_labels = {"持续最长时间", "治疗类型", "AT/AF负荷%"}
    
    for r in range(start_row, end_row):
        # 收集该行所有非空单元格
        row_content = []
        for c in range(handler.ncols):
            val = clean_value(handler.get_cell_value(r, c))
            if val:
                is_label = handler.is_blue_cell(r, c)
                row_content.append((c, val, is_label))
        
        if len(row_content) < 2:
            continue
        
        # 该行第一个单元格作为"行标签"
        row_label = row_content[0][1] if row_content else ""
        # 去掉行标签中可能的括号后缀，得到前缀
        row_prefix = row_label.replace("次数", "").replace("事件", "").strip()
        
        # 遍历行内容，提取 key-value 对
        i = 0
        while i < len(row_content):
            c, v, is_label = row_content[i]
            
            # 判断这个单元格是否是一个标签
            # （蓝色，或者是已知的列标签文本）
            is_known_label = v in col_labels or is_label
            
            if is_known_label and not is_ignored(v):
                # 找紧跟其后的值
                value = find_value_smart(handler, r, c)
                
                if v in col_labels and row_prefix:
                    # 重复列标签 → 生成复合键
                    compound_key = f"{row_prefix}_{v}"
                    data[compound_key] = value
                elif is_label:
                    # 普通蓝色标签
                    if v not in data:  # 避免覆盖已有值
                        data[v] = value
            i += 1
    
    return data


def validate_header_identity(d_header: dict, filename: str) -> tuple[dict, list[dict]]:
    """校验身份信息；不再以文件名静默覆盖 Excel 中的姓名。"""
    import logging
    logger = logging.getLogger(__name__)
    flags = []
    header_name = d_header.get("姓名", "")
    filename_name = extract_name_from_filename(filename)

    if not header_name or not filename_name:
        return d_header, flags

    # 身份冲突必须进入隔离队列人工复核，不能用文件名覆盖原始 header。
    if filename_name not in header_name and header_name not in filename_name:
        logger.warning("患者姓名与文件名不一致，已标记待复核: %s", filename)
        flags.append({
            "code": "IDENTITY_NAME_MISMATCH",
            "source": "filename_vs_header",
        })

    return d_header, flags


def process_file(filepath, filename):
    """处理单个文件并返回结构化数据"""
    handler = None
    try:
        handler = get_handler(filepath)
        anchors = get_anchors(handler)
        
        rb = anchors["basic"] if anchors["basic"] is not None else handler.nrows
        rat = anchors["antitachy"]
        rt = anchors["test"] if anchors["test"] is not None else handler.nrows
        event_row = anchors["event"] if anchors["event"] is not None else handler.nrows
        basic_end = rat if rat is not None else rt

        d_header, _ = extract_kv_in_range(handler, 0, rb)
        
        # 兜底：非蓝色模板的 header 提取（ICD/CRT-D 等模板标签无蓝色背景）
        _HEADER_KEYS = {"姓名", "性别", "年龄（岁）", "年龄", "登记号", 
                        "品牌", "型号", "植入日期"}
        missing_keys = _HEADER_KEYS - set(d_header.keys())
        if missing_keys:
            for r in range(0, min(rb, 5)):
                for c in range(handler.ncols):
                    label = clean_label(handler.get_cell_value(r, c))
                    if label in missing_keys:
                        val = find_value_smart(handler, r, c)
                        if val:
                            d_header[label] = val
                            missing_keys.discard(label)
        
        # 身份冲突由分组阶段隔离，不污染患者主档案。
        d_header, identity_flags = validate_header_identity(d_header, filename)
        
        d_basic, _ = extract_kv_in_range(handler, rb, basic_end)
        d_basic_tbl = extract_table_in_range(handler, rb, basic_end, Z2_COL_HEADERS, Z2_ROW_HEADERS)

        d_antitachy = {}
        if rat is not None:
            d_antitachy = extract_antitachy_table(handler, rat, rt)

        d_test, _ = extract_kv_in_range(handler, rt, event_row)
        d_test_tbl = extract_table_in_range(handler, rt, event_row, Z3_COL_HEADERS, Z3_ROW_HEADERS)
        
        d_events, conc_row = extract_kv_in_range(handler, event_row, handler.nrows)
        d_events_flexible = extract_events_flexible(handler, event_row, handler.nrows)
        d_events.update(d_events_flexible)

        sig_text, sig_date = ("", "")
        if conc_row is not None:
            sig_text, sig_date = extract_footer_info(handler, conc_row)
        else:
            # 兜底：非蓝色模板可能没有标记结论行，从事件区域开始扫描签名/日期
            sig_text, sig_date = extract_footer_info(handler, event_row)

        result = {
            "meta": {
                "filename": filename,
                "source_id": stable_source_id(filepath),
                "schema_version": RECORD_SCHEMA_VERSION,
                "pipeline_version": PIPELINE_VERSION,
            },
            "header": d_header,
            "basic_params": {"settings": d_basic, "measurements": d_basic_tbl},
        }
        if d_antitachy:
            result["antitachy_params"] = d_antitachy

        if identity_flags:
            result["meta"]["quality_flags"] = identity_flags

        result.update({
            "test_params": {"battery_and_leads": d_test, "threshold_tests": d_test_tbl},
            "events_and_footer": d_events,
            "footer_meta": {"签名行内容": sig_text, "程控日期": sig_date},
        })
        return result
    except Exception as e:
        return {"meta": {"filename": filename, "error": str(e)}}
    finally:
        if handler and hasattr(handler, 'close'):
            handler.close()



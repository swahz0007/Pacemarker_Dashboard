"""
工具函数模块
"""

import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import IGNORE_IN_KV


def clean_value(val):
    """清理单元格值"""
    if val is None:
        return ""
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
    val_str = str(val).strip()
    return "" if val_str == "None" else val_str


def clean_label(label):
    """清理标签字符串"""
    return str(label).strip() if label else ""


def is_ignored(label):
    """判断是否需要忽略该标签"""
    if not label:
        return True
    cl = label.split("（")[0].split("(")[0].strip()
    return cl in IGNORE_IN_KV or label in IGNORE_IN_KV


# ============= 公共函数：从其他模块提取 =============

# 文件名解析后缀列表（供 extract_name_from_filename 使用）
NAME_SUFFIXES = [
    "起搏器报告单", "CRT-P报告单", "CRT-D报告单", "ICD报告单", "EV-ICD报告单",
    "（美敦力）", "（雅培）", "（百多力）", "(美敦力)", "(雅培)", "(百多力)",
    "Vitatron", " ", "(", "（", ")", "）", "-", "_"
]


def extract_name_from_filename(filename: str) -> str:
    """从文件名中提取患者姓名"""
    name = filename.replace(".xlsx", "").replace(".xls", "")

    for suffix in NAME_SUFFIXES:
        name = name.split(suffix)[0]

    name = re.sub(r'\s*\(\d+\)\s*$', '', name)
    name = re.sub(r'\s*（\d+）\s*$', '', name)

    return name.strip()


# 日期解析格式（供 parse_date 使用）
DATE_PATTERNS = [
    r"(\d{4})年(\d{1,2})月(\d{1,2})日",
    r"(\d{4})/(\d{1,2})/(\d{1,2})",
    r"(\d{4})\.(\d{1,2})\.(\d{1,2})",
    r"(\d{4})-(\d{1,2})-(\d{1,2})",
]


def parse_date(date_str: str):
    """解析多种日期格式"""
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()

    for pattern in DATE_PATTERNS:
        match = re.match(pattern, date_str)
        if match:
            try:
                year, month, day = match.groups()
                return datetime(int(year), int(month), int(day))
            except ValueError:
                continue

    return None


def excel_date_to_str(val):
    """将Excel日期序列号转换为日期字符串"""
    if isinstance(val, float) and 40000 < val < 55000:
        try:
            dt = datetime(1899, 12, 30) + timedelta(days=val)
            return dt.strftime('%Y年%m月%d日')
        except:
            pass
    return None

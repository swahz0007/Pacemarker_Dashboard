"""
数据提取脚本
从匹配报告中提取所有文件的数据
"""

import csv
import warnings
import sys
from pathlib import Path

# 添加 backend 目录到路径
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
from config import MATCHING_REPORT_FILE
from core.extractors import process_file


def extract_all_data():
    """
    从匹配报告中提取所有文件的数据
    返回: 提取的数据列表（内存管道，不写入文件）
    """
    if not MATCHING_REPORT_FILE.exists():
        print(f"错误: 匹配报告不存在 ({MATCHING_REPORT_FILE})")
        print("请先运行 match_templates.py")
        return []
    
    with open(MATCHING_REPORT_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        files = [
            r for r in reader
            if "Match" in r["Status"] and not r["Filename"].startswith("~$")
        ]

    print(f"开始全量提取，共 {len(files)} 个文件...")
    
    json_output = []
    for i, file in enumerate(files):
        if (i + 1) % 50 == 0:
            print(f"已处理 {i + 1}/{len(files)}...")
        json_output.append(process_file(file["Full Path"], file["Filename"]))

    error_count = sum(1 for r in json_output if "error" in r.get("meta", {}))
    print(f"数据提取完成，共 {len(json_output)} 条记录（成功 {len(json_output) - error_count}, 失败 {error_count}）。")
    return json_output


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data = extract_all_data()
        print(f"提取了 {len(data)} 条记录（内存模式，未写入文件）")

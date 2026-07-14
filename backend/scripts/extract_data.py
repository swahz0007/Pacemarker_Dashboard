"""
数据提取脚本
从匹配报告中提取所有文件的数据
"""

import csv
import warnings
import sys
from collections import Counter
from pathlib import Path

# 添加 backend 目录到路径
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
from config import MATCHING_REPORT_FILE
from core.extractors import process_file
from core.handlers import is_xls_supported
from scripts.match_templates import is_matched_status


def extract_all_data(return_summary=False):
    """
    从匹配报告中提取所有文件的数据
    返回: 提取的数据列表（内存管道，不写入文件）。
    ``return_summary=True`` 时同时返回可用于阻断不完整全量处理的汇总信息。
    """
    if not MATCHING_REPORT_FILE.exists():
        print(f"错误: 匹配报告不存在 ({MATCHING_REPORT_FILE})")
        print("请先运行 match_templates.py")
        summary = {
            "matching_report_found": False,
            "matched_files": 0,
            "unmatched_files": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped_unsupported": 0,
        }
        return ([], summary) if return_summary else []
    
    with open(MATCHING_REPORT_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        all_rows = [r for r in reader if not r.get("Filename", "").startswith("~$")]
        files = [r for r in all_rows if is_matched_status(r.get("Status"))]

    print(f"开始全量提取，共 {len(files)} 个文件...")
    
    json_output = []
    xls_supported = is_xls_supported()
    skipped_unsupported = []
    failed_records = []
    for i, file in enumerate(files):
        if (i + 1) % 50 == 0:
            print(f"已处理 {i + 1}/{len(files)}...")
        filename = file["Filename"]
        if filename.lower().endswith(".xls") and not xls_supported:
            skipped_unsupported.append(filename)
            continue
        record = process_file(file["Full Path"], file["Filename"])
        if "error" in record.get("meta", {}):
            failed_records.append({
                "filename": filename,
                "error": record.get("meta", {}).get("error", "unknown error")
            })
            continue
        json_output.append(record)

    error_count = len(failed_records)
    skipped_count = len(skipped_unsupported)
    print(
        f"数据提取完成，共 {len(files)} 个文件（成功 {len(json_output)}, "
        f"失败 {error_count}, 环境受限跳过 {skipped_count}）。"
    )
    if skipped_count:
        print("环境受限跳过主因: 当前环境缺少 xlrd，无法处理 .xls 文件。")
    if error_count:
        reason_counter = Counter(item.get("error", "unknown error") for item in failed_records)
        top_reason, top_count = reason_counter.most_common(1)[0]
        print(f"失败主因: {top_reason} ({top_count} 条)")
        if "xlrd is not installed" in top_reason:
            print("提示: 当前环境缺少 xlrd，.xls 文件将被跳过；安装 xlrd 后可恢复 .xls 提取能力。")
    summary = {
        "matching_report_found": True,
        "matched_files": len(files),
        "unmatched_files": len(all_rows) - len(files),
        "succeeded": len(json_output),
        "failed": error_count,
        "skipped_unsupported": skipped_count,
    }
    return (json_output, summary) if return_summary else json_output


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data = extract_all_data()
        print(f"提取了 {len(data)} 条记录（内存模式，未写入文件）")

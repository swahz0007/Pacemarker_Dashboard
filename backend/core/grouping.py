"""
患者分组模块
负责按登记号对患者记录进行分组、排序和拆分输出
"""

import json
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from config import PATIENT_RECORDS_DIR
from core.utils import extract_name_from_filename, parse_date


def is_valid_record(record: dict) -> bool:
    """校验记录有效性：文件名中的姓名应与header中的姓名匹配"""
    filename = record.get("meta", {}).get("filename", "")
    header_name = record.get("header", {}).get("姓名", "")
    
    if not filename or not header_name:
        return False
    
    filename_name = extract_name_from_filename(filename)
    
    return filename_name in header_name or header_name in filename_name


def group_by_registration_id(data: list) -> dict:
    """按登记号分组（仅保留有效记录）"""
    grouped = defaultdict(list)
    invalid_count = 0
    
    for record in data:
        if not is_valid_record(record):
            invalid_count += 1
            continue
        
        reg_id = record.get("header", {}).get("登记号", "")
        if reg_id:
            grouped[reg_id].append(record)
    
    print(f"过滤脏数据: {invalid_count}条")
    return grouped


def sort_by_date(records: list) -> list:
    """按程控日期排序（从早到晚）"""
    def get_date(record):
        date_str = record.get("footer_meta", {}).get("程控日期", "")
        parsed = parse_date(date_str)
        return parsed if parsed else datetime.max
    
    return sorted(records, key=get_date)


def process_and_split_records(data: list):
    """
    内存管道处理：分组 + 排序 + 拆分输出
    直接从提取的数据列表生成患者独立JSON文件
    """
    print(f"总记录数: {len(data)}")
    
    # 按登记号分组
    grouped = group_by_registration_id(data)
    print(f"唯一患者数（按登记号）: {len(grouped)}")
    
    # 创建输出目录
    PATIENT_RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    
    count = 0
    multi_visit_count = 0
    
    for reg_id, records in grouped.items():
        sorted_records = sort_by_date(records)
        
        patient_data = {
            "登记号": reg_id,
            "姓名": sorted_records[0].get("header", {}).get("姓名", "未知"),
            "程控次数": len(sorted_records),
            "程控记录": sorted_records
        }
        
        if len(sorted_records) > 1:
            multi_visit_count += 1
        
        # 确保文件名安全
        safe_filename = "".join([c for c in reg_id if c.isalnum() or c in (' ', '.', '_')]).strip()
        file_path = PATIENT_RECORDS_DIR / f"{safe_filename}.json"
        
        with open(file_path, 'w', encoding='utf-8') as outfile:
            json.dump(patient_data, outfile, ensure_ascii=False, indent=2)
        
        count += 1
        if count % 100 == 0:
            print(f"已处理 {count}/{len(grouped)} 条记录...")
    
    print(f"多次程控患者数: {multi_visit_count}")
    print(f"已拆分 {count} 条患者记录至: {PATIENT_RECORDS_DIR}")

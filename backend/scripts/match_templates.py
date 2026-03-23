"""
模板匹配脚本
根据文件名匹配对应的报告模板
"""

import os
import json
import csv
import sys
from pathlib import Path

# 添加 backend 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_REPOSITORY, TEMPLATES_FILE, MATCHING_REPORT_FILE


def load_templates(json_path):
    """加载模板定义文件"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_filename_features(filename):
    """
    从文件名解析品牌和设备类型
    返回 (brand, device_type)
    """
    name = filename.upper()
    
    # 1. 判断品牌
    brand = None
    if "美敦力" in name or "MEDTRONIC" in name:
        if "MICRA" in name:
            brand = "美敦力Micra AV"
        elif "VITATRON" in name:
            brand = "美敦力"
        else:
            brand = "美敦力"
    elif "雅培" in name or "ABBOTT" in name or "ST.JUDE" in name:
        brand = "雅培"
    elif "百多力" in name or "BIOTRONIK" in name:
        brand = "百多力"
    elif "波科" in name or "BOSTON" in name:
        brand = "波科"
    elif "创领" in name:
        brand = "创领"
    elif "传导束" in name:
        brand = "传导束起搏"
    
    # 2. 判断设备类型
    # 优先级: EV-ICD > CRT-D > CRT-P > ICD > 起搏器
    device_type = "起搏器报告单"  # 默认
    
    if "EV-ICD" in name:
        device_type = "EV-ICD报告单"
    elif "CRT-D" in name or "CRTD" in name:
        device_type = "CRT-D报告单"
    elif "CRT-P" in name or "CRTP" in name:
        device_type = "CRT-P报告单"
    elif "ICD" in name:
        device_type = "ICD报告单"
    elif "传导束" in name:
        device_type = "起搏器报告单"
    
    return brand, device_type


def find_best_template(filename, templates_data):
    """查找最匹配的模板"""
    target_brand, target_type = parse_filename_features(filename)
    
    if not target_brand:
        return None, "Unknown Brand", target_type

    best_match = None
    for tmpl_filename, tmpl_info in templates_data.items():
        t_brand = tmpl_info['brand']
        t_type = tmpl_info['type']
        
        brand_match = False
        if target_brand == t_brand:
            brand_match = True
        if target_brand == "美敦力" and t_brand == "美敦力Micra AV":
            brand_match = False
        
        if brand_match and target_type == t_type:
            best_match = tmpl_filename
            break
            
    if best_match:
        return best_match, target_brand, target_type
    
    return None, target_brand, target_type


def match_all_files():
    """匹配所有文件并生成报告"""
    templates = load_templates(TEMPLATES_FILE)
    print(f"已加载 {len(templates)} 个模板。")
    
    file_records = []
    
    for root, dirs, files in os.walk(DATA_REPOSITORY):
        for f in files:
            if not f.lower().endswith(('.xls', '.xlsx')):
                continue
            if f.startswith('~$'):  # 跳过临时文件
                continue
                
            full_path = os.path.join(root, f)
            matched_template, brand, dtype = find_best_template(f, templates)
            
            status = "Match" if matched_template else "No Match"
            
            if "VITATRON" in f.upper() and brand == "美敦力":
                status = "Match (Vitatron->Medtronic)"
            
            file_records.append({
                "Filename": f,
                "Full Path": full_path,  # 使用绝对路径，避免目录切换问题
                "Detected Brand": brand,
                "Detected Type": dtype,
                "Matched Template": matched_template if matched_template else "N/A",
                "Status": status
            })

    # 写入 CSV
    headers = ["Filename", "Full Path", "Detected Brand", "Detected Type", "Matched Template", "Status"]
    
    with open(MATCHING_REPORT_FILE, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(file_records)
        
    print(f"处理完成。共处理 {len(file_records)} 个文件。")
    print(f"报告已保存到 {MATCHING_REPORT_FILE}")
    
    # 统计
    matched_count = sum(1 for r in file_records if "Match" in r["Status"])
    total = len(file_records)
    pct = f"{matched_count/total*100:.2f}" if total > 0 else "N/A"
    print(f"匹配成功率: {matched_count}/{total} ({pct}%)")
    
    return file_records


if __name__ == "__main__":
    match_all_files()

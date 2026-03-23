"""
Pacemaker Dashboard Backend - 主入口
提供统一的接口来运行数据处理流程

用法:
    python main.py            # 全量处理
    python main.py --update   # 增量更新
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 确保导入路径正确
sys.path.insert(0, str(Path(__file__).parent))

from scripts.match_templates import match_all_files, find_best_template, load_templates
from scripts.extract_data import extract_all_data
from core.grouping import process_and_split_records
from core.extractors import process_file
from core.file_tracker import (
    build_file_index, find_new_or_modified_files,
    load_processed_files, save_processed_files, get_file_hash
)
from config import TEMPLATES_FILE, PATIENT_RECORDS_DIR, DATA_REPOSITORY

from datetime import datetime


def full_process():
    """全量处理：匹配模板 + 提取数据 + 分组拆分"""
    logger.info("=" * 50)
    logger.info("Pacemaker Dashboard 后端数据处理")
    logger.info("=" * 50)

    logger.info("[1/3] 匹配模板...")
    match_all_files()

    logger.info("[2/3] 提取数据...")
    data = extract_all_data()

    logger.info("[3/3] 按患者分组并拆分...")
    process_and_split_records(data)

    # 建立文件索引（用于增量更新）
    logger.info("建立文件索引...")
    count = build_file_index()
    logger.info(f"文件索引已建立，共 {count} 个文件。")
    logger.info("全量处理完成！")


def incremental_update():
    """增量更新：仅处理新增/修改的文件"""
    logger.info("=" * 50)
    logger.info("Pacemaker Dashboard 增量更新")
    logger.info("=" * 50)

    new_files, modified_files = find_new_or_modified_files()
    total_changes = len(new_files) + len(modified_files)

    if total_changes == 0:
        logger.info("没有检测到新增或修改的文件，无需更新。")
        return

    logger.info(f"检测到变更: {len(new_files)} 个新文件, {len(modified_files)} 个修改文件")

    # 加载模板
    templates = load_templates(TEMPLATES_FILE)

    # 处理变更文件
    extracted = []
    processed = load_processed_files()
    change_list = new_files + modified_files

    for rel_path, filename, file_hash in change_list:
        full_path = str(DATA_REPOSITORY.parent / rel_path)
        matched_template, brand, dtype = find_best_template(filename, templates)

        if not matched_template and "Match" not in (brand or ""):
            logger.warning(f"跳过无法匹配模板的文件: {filename}")
            continue

        record = process_file(full_path, filename)
        if "error" not in record.get("meta", {}):
            extracted.append(record)
            processed[rel_path] = {
                'hash': file_hash,
                'last_processed': datetime.now().isoformat()
            }
        else:
            logger.warning(f"提取失败: {filename} - {record['meta'].get('error')}")

    if not extracted:
        logger.info("没有成功提取的记录。")
        return

    logger.info(f"成功提取 {len(extracted)} 条记录，开始增量合并...")

    # 增量合并：读取现有患者 JSON，追加/替换记录
    from core.utils import extract_name_from_filename, parse_date
    from collections import defaultdict

    # 按登记号分组新记录
    new_by_reg = defaultdict(list)
    for record in extracted:
        reg_id = record.get("header", {}).get("登记号", "")
        if not reg_id:
            filename = record.get("meta", {}).get("filename", "unknown")
            reg_id = f"PROXY_{filename.replace('.xls', '').replace('.xlsx', '')}"
        new_by_reg[reg_id].append(record)

    merged_count = 0
    created_count = 0

    for reg_id, new_records in new_by_reg.items():
        safe_filename = "".join([c for c in reg_id if c.isalnum() or c in (' ', '.', '_')]).strip()
        file_path = PATIENT_RECORDS_DIR / f"{safe_filename}.json"

        if file_path.exists():
            # 合并到已有文件
            with open(file_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)

            existing_files = {
                r.get("meta", {}).get("filename") for r in existing.get("程控记录", [])
            }

            for nr in new_records:
                nr_filename = nr.get("meta", {}).get("filename")
                if nr_filename in existing_files:
                    # 替换已有记录
                    existing["程控记录"] = [
                        r for r in existing["程控记录"]
                        if r.get("meta", {}).get("filename") != nr_filename
                    ]
                existing["程控记录"].append(nr)

            existing["程控次数"] = len(existing["程控记录"])
            merged_count += 1
        else:
            # 创建新文件
            name = new_records[0].get("header", {}).get("姓名", "未知")
            existing = {
                "登记号": reg_id,
                "姓名": name,
                "程控次数": len(new_records),
                "程控记录": new_records
            }
            created_count += 1

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    # 保存更新后的文件索引
    save_processed_files(processed)

    logger.info(f"增量更新完成: 合并 {merged_count} 个已有患者, 新建 {created_count} 个患者记录")


def main():
    parser = argparse.ArgumentParser(description='Pacemaker Dashboard 后端数据处理')
    parser.add_argument('--update', '-u', action='store_true',
                        help='增量更新（只处理新增/修改的文件）')
    parser.add_argument('--match', '-m', action='store_true',
                        help='仅运行模板匹配')
    parser.add_argument('--extract', '-e', action='store_true',
                        help='仅运行数据提取')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='启用调试模式')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.update:
        incremental_update()
    elif args.match:
        match_all_files()
    elif args.extract:
        data = extract_all_data()
        logger.info(f"提取了 {len(data)} 条记录")
    else:
        full_process()


if __name__ == "__main__":
    main()


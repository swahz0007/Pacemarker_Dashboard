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
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.match_templates import (
    match_all_files, find_best_template_for_file, load_templates, is_matched_status,
)
from scripts.extract_data import extract_all_data
from core.grouping import (
    append_quarantine_records, group_by_registration_id,
    process_and_split_records, remove_records_for_deleted_sources, sort_by_date,
)
from core.extractors import process_file
from core.handlers import is_xls_supported
from core.file_tracker import (
    build_file_index, find_new_or_modified_files,
    load_processed_files, make_processed_entry, save_processed_files,
)
from core.utils import atomic_write_json, stable_patient_filename, stable_source_id
from config import (
    TEMPLATES_FILE, PATIENT_RECORDS_DIR, DATA_REPOSITORY,
    PIPELINE_VERSION, RECORD_SCHEMA_VERSION,
)

from datetime import datetime, timezone


def full_process():
    """全量处理：仅在匹配和提取完整成功时才替换正式患者输出。"""
    logger.info("=" * 50)
    logger.info("Pacemaker Dashboard 后端数据处理")
    logger.info("=" * 50)

    logger.info("[1/3] 匹配模板...")
    match_records = match_all_files()
    unmatched = [record for record in match_records if not is_matched_status(record.get("Status"))]
    if unmatched:
        raise RuntimeError(
            f"发现 {len(unmatched)} 个未匹配模板文件；已保留既有患者输出，"
            "请先补充模板或人工确认后再执行全量处理。"
        )

    logger.info("[2/3] 提取数据...")
    data, extraction_summary = extract_all_data(return_summary=True)
    if (
        extraction_summary["failed"]
        or extraction_summary["skipped_unsupported"]
        or extraction_summary["succeeded"] != extraction_summary["matched_files"]
    ):
        raise RuntimeError(
            "提取未完整成功；已保留既有患者输出。"
            f" 匹配={extraction_summary['matched_files']}，"
            f"成功={extraction_summary['succeeded']}，"
            f"失败={extraction_summary['failed']}，"
            f"跳过={extraction_summary['skipped_unsupported']}。"
        )

    if not data:
        logger.info("没有可处理的匹配文件，未改动患者输出。")
        return

    logger.info("[3/3] 按患者分组并拆分...")
    split_summary = process_and_split_records(data, reconcile=True)

    # 建立文件索引（用于增量更新）
    logger.info("建立文件索引...")
    count = build_file_index()
    logger.info(f"文件索引已建立，共 {count} 个文件。")
    logger.info(
        "全量处理完成：写入 %(patients)s 位患者，隔离 %(quarantined)s 条身份冲突记录，清理 %(stale)s 条旧输出。",
        {
            "patients": split_summary["patients_written"],
            "quarantined": split_summary["quarantined"],
            "stale": split_summary["stale_removed"],
        },
    )


def incremental_update():
    """增量更新：处理新增、修改和删除，并保留冲突记录供人工复核。"""
    logger.info("=" * 50)
    logger.info("Pacemaker Dashboard 增量更新")
    logger.info("=" * 50)

    new_files, modified_files, deleted_files = find_new_or_modified_files(include_deleted=True)
    total_changes = len(new_files) + len(modified_files) + len(deleted_files)

    if total_changes == 0:
        logger.info("没有检测到新增、修改或删除的文件，无需更新。")
        return

    logger.info(
        "检测到变更: %s 个新文件, %s 个修改文件, %s 个删除文件",
        len(new_files), len(modified_files), len(deleted_files),
    )

    extracted = []
    processed = load_processed_files()
    change_list = new_files + modified_files
    source_path_by_id = {}

    deleted_source_ids = {
        stable_source_id(DATA_REPOSITORY.parent / rel_path)
        for rel_path in deleted_files
    }
    deleted_filenames = {Path(rel_path).name for rel_path in deleted_files}
    deletion_summary = remove_records_for_deleted_sources(deleted_source_ids, deleted_filenames)
    for rel_path in deleted_files:
        processed.pop(rel_path, None)

    # 加载模板并处理新增/修改文件
    templates = load_templates(TEMPLATES_FILE)

    xls_supported = is_xls_supported()
    skipped_unsupported = 0
    for rel_path, filename, file_hash in change_list:
        full_path = str(DATA_REPOSITORY.parent / rel_path)
        if filename.lower().endswith(".xls") and not xls_supported:
            logger.warning(f"环境受限跳过 .xls 文件（缺少 xlrd）: {filename}")
            skipped_unsupported += 1
            continue
        matched_template, brand, dtype, _ = find_best_template_for_file(full_path, filename, templates)

        if not matched_template:
            logger.warning(f"跳过无法匹配模板的文件: {filename}")
            continue

        record = process_file(full_path, filename)
        if "error" not in record.get("meta", {}):
            extracted.append(record)
            source_path_by_id[record.get("meta", {}).get("source_id", "")] = rel_path
            processed[rel_path] = make_processed_entry(file_hash)
        else:
            logger.warning(f"提取失败: {filename} - {record['meta'].get('error')}")

    if not extracted:
        save_processed_files(processed)
        logger.info(
            "没有成功提取的新记录；已同步删除变更（移除 %s 条记录、%s 个空患者档案）。",
            deletion_summary["records_removed"], deletion_summary["patients_removed"],
        )
        return

    logger.info(f"成功提取 {len(extracted)} 条记录，开始增量合并...")

    new_by_reg, quarantined = group_by_registration_id(extracted, return_quarantine=True)
    accepted_source_ids = {
        record.get("meta", {}).get("source_id", "") for record in quarantined
    }
    written_paths = set()

    merged_count = 0
    created_count = 0

    for reg_id, new_records in new_by_reg.items():
        file_path = PATIENT_RECORDS_DIR / stable_patient_filename(reg_id)

        if file_path.exists():
            # 合并到已有文件
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error("患者记录文件损坏，已保留原文件等待人工处理: %s - %s", file_path, e)
                for record in new_records:
                    rel_path = source_path_by_id.get(record.get("meta", {}).get("source_id", ""))
                    if rel_path:
                        processed.pop(rel_path, None)
                continue

            if not isinstance(existing.get("程控记录"), list):
                logger.error("患者记录结构异常，已保留原文件等待人工处理: %s", file_path)
                for record in new_records:
                    rel_path = source_path_by_id.get(record.get("meta", {}).get("source_id", ""))
                    if rel_path:
                        processed.pop(rel_path, None)
                continue

            existing_sources = {
                r.get("meta", {}).get("source_id") or r.get("meta", {}).get("filename")
                for r in existing.get("程控记录", [])
                if isinstance(r, dict)
            }

            for nr in new_records:
                nr_source = nr.get("meta", {}).get("source_id") or nr.get("meta", {}).get("filename")
                if nr_source in existing_sources:
                    # 替换已有记录
                    existing["程控记录"] = [
                        r for r in existing["程控记录"]
                        if (r.get("meta", {}).get("source_id") or r.get("meta", {}).get("filename")) != nr_source
                    ]
                existing["程控记录"].append(nr)

            existing["程控记录"] = sort_by_date(existing["程控记录"])
            existing["程控次数"] = len(existing["程控记录"])
            existing["schema_version"] = RECORD_SCHEMA_VERSION
            existing["pipeline_version"] = PIPELINE_VERSION
            existing["generated_at"] = datetime.now(timezone.utc).isoformat()
            existing["provenance"] = {
                "source_record_count": len(existing["程控记录"]),
                "source_ids": [
                    record.get("meta", {}).get("source_id", "")
                    for record in existing["程控记录"]
                ],
            }
            merged_count += 1
        else:
            # 创建新文件
            name = new_records[0].get("header", {}).get("姓名", "未知")
            sorted_new_records = sort_by_date(new_records)
            existing = {
                "schema_version": RECORD_SCHEMA_VERSION,
                "pipeline_version": PIPELINE_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "登记号": reg_id,
                "姓名": name,
                "程控次数": len(sorted_new_records),
                "程控记录": sorted_new_records,
                "provenance": {
                    "source_record_count": len(sorted_new_records),
                    "source_ids": [
                        record.get("meta", {}).get("source_id", "")
                        for record in sorted_new_records
                    ],
                },
            }
            created_count += 1

        atomic_write_json(file_path, existing)
        written_paths.add(file_path)
        accepted_source_ids.update(
            record.get("meta", {}).get("source_id", "") for record in new_records
        )

    # 新记录原子写入成功后，清理其在其他患者输出中的旧版本，再写入隔离队列。
    replacement_summary = remove_records_for_deleted_sources(
        accepted_source_ids, set(), preserve_paths=written_paths,
    )
    quarantined_count = append_quarantine_records(quarantined)

    # 保存更新后的文件索引
    save_processed_files(processed)

    logger.info(
        "增量更新完成: 合并 %s 个已有患者, 新建 %s 个患者记录, 隔离 %s 条身份冲突；"
        "删除变更移除 %s 条记录，更新替换移除 %s 条旧记录。",
        merged_count, created_count, quarantined_count,
        deletion_summary["records_removed"], replacement_summary["records_removed"],
    )


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


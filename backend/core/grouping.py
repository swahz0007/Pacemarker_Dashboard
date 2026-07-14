"""
患者分组模块
负责按登记号对患者记录进行分组、排序和拆分输出
"""

import logging
import json
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)

from config import (
    PATIENT_RECORDS_DIR, QUARANTINE_RECORDS_FILE,
    PIPELINE_VERSION, RECORD_SCHEMA_VERSION,
)
from core.utils import (
    extract_name_from_filename, parse_date, atomic_write_json,
    proxy_registration_id, stable_patient_filename,
)


def is_valid_record(record: dict) -> bool:
    """校验记录有效性：仅检查关键字段是否存在（不再过滤姓名不匹配的记录）"""
    filename = record.get("meta", {}).get("filename", "")
    header_name = record.get("header", {}).get("姓名", "")
    extract_error = record.get("meta", {}).get("error", "")
    
    if not filename:
        return False
    if extract_error:
        logger.warning(f"提取失败记录已过滤: {filename} - {extract_error}")
        return False
    
    # 姓名不匹配时仅警告，不过滤
    if header_name:
        filename_name = extract_name_from_filename(filename)
        if filename_name and filename_name not in header_name and header_name not in filename_name:
            logger.warning(f"姓名不匹配但保留: 文件名='{filename_name}', header='{header_name}'")
    
    return True


def _identity_flags(record: dict) -> list[dict]:
    """读取提取阶段写入的身份冲突标记。"""
    flags = record.get("meta", {}).get("quality_flags", [])
    if not isinstance(flags, list):
        return []
    return [flag for flag in flags if isinstance(flag, dict) and str(flag.get("code", "")).startswith("IDENTITY_")]


def group_by_registration_id(data: list, return_quarantine: bool = False):
    """按登记号分组；身份冲突记录进入隔离队列而不写入患者主档案。"""
    grouped = defaultdict(list)
    invalid_count = 0
    proxy_count = 0
    quarantined = []
    
    for record in data:
        if not is_valid_record(record):
            invalid_count += 1
            continue

        flags = _identity_flags(record)
        if flags:
            quarantined.append(record)
            logger.warning("身份冲突记录已隔离: %s", record.get("meta", {}).get("filename", "unknown"))
            continue
        
        reg_id = record.get("header", {}).get("登记号", "")
        if not reg_id:
            # 用来源哈希生成代理登记号，避免不同目录下的同名报告被错误合并。
            filename = record.get("meta", {}).get("filename", "unknown")
            source_hint = record.get("meta", {}).get("source_id", "")
            reg_id = proxy_registration_id(filename, source_hint)
            record.setdefault("header", {})["登记号"] = reg_id
            proxy_count += 1
        
        grouped[reg_id].append(record)
    
    logger.info(f"过滤无效记录: {invalid_count}条")
    if proxy_count > 0:
        logger.info(f"代理登记号: {proxy_count}条（原始登记号为空）")
    if return_quarantine:
        return grouped, quarantined
    return grouped


def sort_by_date(records: list) -> list:
    """按程控日期排序（从早到晚）"""
    def get_date(record):
        date_str = record.get("footer_meta", {}).get("程控日期", "")
        parsed = parse_date(date_str)
        return parsed if parsed else datetime.max
    
    return sorted(records, key=get_date)


def _is_patient_record_file(path) -> bool:
    """只将符合患者输出结构的 JSON 视为可由全量流程清理的生成物。"""
    try:
        with open(path, "r", encoding="utf-8") as infile:
            payload = json.load(infile)
    except (OSError, json.JSONDecodeError):
        logger.warning("无法判断旧输出是否可清理，已保留: %s", path)
        return False
    return isinstance(payload, dict) and isinstance(payload.get("程控记录"), list)


def _reconcile_patient_files(generated_names: set[str]) -> int:
    """在全量成功写入后清除已不再对应任何源记录的旧患者输出。"""
    reserved = {"processed_files.json", QUARANTINE_RECORDS_FILE.name}
    removed = 0
    for path in PATIENT_RECORDS_DIR.glob("*.json"):
        if path.name in reserved or path.name in generated_names:
            continue
        if _is_patient_record_file(path):
            path.unlink()
            removed += 1
    return removed


def _write_quarantine_records(records: list, generated_at: str) -> None:
    """写入待人工复核的身份冲突记录，不混入正式患者主档案。"""
    payload = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": generated_at,
        "record_count": len(records),
        "records": records,
    }
    atomic_write_json(QUARANTINE_RECORDS_FILE, payload)


def append_quarantine_records(records: list) -> int:
    """追加增量流程发现的身份冲突记录，并按 source_id 去重。"""
    if not records:
        return 0
    existing = []
    if QUARANTINE_RECORDS_FILE.exists():
        try:
            with open(QUARANTINE_RECORDS_FILE, "r", encoding="utf-8") as infile:
                payload = json.load(infile)
            if isinstance(payload, dict) and isinstance(payload.get("records"), list):
                existing = payload["records"]
        except (OSError, json.JSONDecodeError):
            logger.warning("隔离队列无法读取，保留原文件并跳过本次追加")
            return 0

    existing_ids = {
        record.get("meta", {}).get("source_id", "")
        for record in existing if isinstance(record, dict)
    }
    appended = [
        record for record in records
        if record.get("meta", {}).get("source_id", "") not in existing_ids
    ]
    if appended:
        _write_quarantine_records(existing + appended, datetime.now(timezone.utc).isoformat())
    return len(appended)


def remove_records_for_deleted_sources(
    source_ids: set[str], filenames: set[str], preserve_paths: set | None = None,
) -> dict:
    """从正式输出和隔离队列中移除来源记录，可保留本次刚写入的目标文件。"""
    if not source_ids and not filenames:
        return {"records_removed": 0, "patients_removed": 0}

    def belongs_to_deleted_source(record: dict) -> bool:
        meta = record.get("meta", {}) if isinstance(record, dict) else {}
        source_id = meta.get("source_id", "")
        if source_id:
            return source_id in source_ids
        return meta.get("filename", "") in filenames

    records_removed = 0
    patients_removed = 0
    reserved = {"processed_files.json", QUARANTINE_RECORDS_FILE.name}
    preserved = {str(path) for path in (preserve_paths or set())}
    generated_at = datetime.now(timezone.utc).isoformat()

    for path in PATIENT_RECORDS_DIR.glob("*.json"):
        if str(path) in preserved or path.name in reserved or not _is_patient_record_file(path):
            continue
        with open(path, "r", encoding="utf-8") as infile:
            patient = json.load(infile)
        original = patient.get("程控记录", [])
        retained = [record for record in original if not belongs_to_deleted_source(record)]
        if len(retained) == len(original):
            continue
        records_removed += len(original) - len(retained)
        if not retained:
            path.unlink()
            patients_removed += 1
            continue
        patient["程控记录"] = sort_by_date(retained)
        patient["程控次数"] = len(retained)
        patient["generated_at"] = generated_at
        patient["pipeline_version"] = PIPELINE_VERSION
        patient["provenance"] = {
            "source_record_count": len(retained),
            "source_ids": [record.get("meta", {}).get("source_id", "") for record in retained],
        }
        atomic_write_json(path, patient)

    if QUARANTINE_RECORDS_FILE.exists():
        try:
            with open(QUARANTINE_RECORDS_FILE, "r", encoding="utf-8") as infile:
                quarantine = json.load(infile)
            original = quarantine.get("records", []) if isinstance(quarantine, dict) else []
            retained = [record for record in original if not belongs_to_deleted_source(record)]
            if len(retained) != len(original):
                records_removed += len(original) - len(retained)
                _write_quarantine_records(retained, generated_at)
        except (OSError, json.JSONDecodeError):
            logger.warning("无法更新隔离队列，已保留原文件: %s", QUARANTINE_RECORDS_FILE)

    return {"records_removed": records_removed, "patients_removed": patients_removed}


def process_and_split_records(data: list, *, reconcile: bool = True) -> dict:
    """
    内存管道处理：分组 + 排序 + 拆分输出
    直接从提取的数据列表生成患者独立JSON文件
    """
    logger.info(f"总记录数: {len(data)}")
    
    # 按登记号分组
    grouped, quarantined = group_by_registration_id(data, return_quarantine=True)
    logger.info(f"唯一患者数（按登记号）: {len(grouped)}")
    
    # 创建输出目录
    PATIENT_RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    
    count = 0
    multi_visit_count = 0
    generated_names = set()
    generated_at = datetime.now(timezone.utc).isoformat()
    
    for reg_id, records in grouped.items():
        sorted_records = sort_by_date(records)
        
        patient_data = {
            "schema_version": RECORD_SCHEMA_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "generated_at": generated_at,
            "登记号": reg_id,
            "姓名": sorted_records[0].get("header", {}).get("姓名", "未知"),
            "程控次数": len(sorted_records),
            "程控记录": sorted_records,
            "provenance": {
                "source_record_count": len(sorted_records),
                "source_ids": [
                    record.get("meta", {}).get("source_id", "")
                    for record in sorted_records
                ],
            },
        }
        
        if len(sorted_records) > 1:
            multi_visit_count += 1
        
        file_path = PATIENT_RECORDS_DIR / stable_patient_filename(reg_id)
        atomic_write_json(file_path, patient_data)
        generated_names.add(file_path.name)
        
        count += 1
        if count % 100 == 0:
            logger.info(f"已处理 {count}/{len(grouped)} 条记录...")
    
    stale_removed = 0
    if grouped and reconcile:
        stale_removed = _reconcile_patient_files(generated_names)
        logger.info("已清理 %s 条不再对应源数据的旧患者输出", stale_removed)
    elif data:
        logger.warning("没有可写入的正式患者记录，已保留旧输出以避免意外清空")

    _write_quarantine_records(quarantined, generated_at)
    logger.info(f"多次程控患者数: {multi_visit_count}")
    logger.info(f"已拆分 {count} 条患者记录至: {PATIENT_RECORDS_DIR}")
    logger.info("身份冲突隔离记录: %s", len(quarantined))
    return {
        "patients_written": count,
        "quarantined": len(quarantined),
        "stale_removed": stale_removed,
    }

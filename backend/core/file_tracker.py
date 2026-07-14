"""
文件追踪模块
负责文件哈希计算、已处理文件记录和增量更新检测
"""

import os
import json
import hashlib
import logging
from datetime import datetime

from config import (
    DATA_REPOSITORY, PROCESSED_FILES_FILE, TEMPLATES_FILE, PIPELINE_VERSION,
)
from core.utils import atomic_write_json

logger = logging.getLogger(__name__)
EXCEL_EXTENSIONS = ('.xls', '.xlsx')
TEMP_PREFIX = '~$'


def get_file_hash(filepath):
    """计算文件的 SHA-256 哈希值，用于来源可追溯与变更检测。"""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read(65536)
        while buf:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()


def load_processed_files():
    """加载已处理文件的记录"""
    if PROCESSED_FILES_FILE.exists():
        try:
            with open(PROCESSED_FILES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            logger.warning("processed files 文件格式异常，预期 dict，已回退空记录")
        except json.JSONDecodeError as e:
            logger.error("processed files 文件解析失败，已回退空记录: %s", str(e))
        except OSError as e:
            logger.error("读取 processed files 文件失败，已回退空记录: %s", str(e))
    return {}


def save_processed_files(data):
    """保存已处理文件的记录"""
    atomic_write_json(PROCESSED_FILES_FILE, data)


def make_processed_entry(file_hash: str) -> dict:
    """构建含版本与模板指纹的单文件处理记录。"""
    templates_hash = get_file_hash(TEMPLATES_FILE) if TEMPLATES_FILE.exists() else ""
    return {
        'hash': file_hash,
        'hash_algorithm': 'sha256',
        'templates_hash': templates_hash,
        'pipeline_version': PIPELINE_VERSION,
        'last_processed': datetime.now().isoformat(),
    }


def find_new_or_modified_files(include_deleted: bool = False):
    """查找新增、修改（以及可选的已删除）文件。"""
    processed = load_processed_files()
    new_files = []
    modified_files = []
    seen_paths = set()

    if not DATA_REPOSITORY.exists():
        logger.warning("数据仓库目录不存在: %s", str(DATA_REPOSITORY))
        return (new_files, modified_files, []) if include_deleted else (new_files, modified_files)

    for rel_path, filename, file_hash in _iter_excel_files():
        seen_paths.add(rel_path)
        record = processed.get(rel_path) if isinstance(processed.get(rel_path), dict) else None
        if not record:
            new_files.append((rel_path, filename, file_hash))
        elif record.get('hash') != file_hash:
            modified_files.append((rel_path, filename, file_hash))
    
    deleted_files = sorted(set(processed) - seen_paths)
    if include_deleted:
        return new_files, modified_files, deleted_files
    return new_files, modified_files


def build_file_index():
    """建立所有Excel文件的索引"""
    processed = {}
    if not DATA_REPOSITORY.exists():
        logger.warning("数据仓库目录不存在: %s", str(DATA_REPOSITORY))
        return 0

    for rel_path, _, file_hash in _iter_excel_files():
        processed[rel_path] = make_processed_entry(file_hash)
    
    save_processed_files(processed)
    return len(processed)


def _iter_excel_files():
    for root, dirs, files in os.walk(DATA_REPOSITORY):
        dirs.sort()
        for filename in sorted(files):
            if not filename.lower().endswith(EXCEL_EXTENSIONS):
                continue
            if filename.startswith(TEMP_PREFIX):
                continue

            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, start=DATA_REPOSITORY.parent)
            try:
                file_hash = get_file_hash(full_path)
            except (FileNotFoundError, OSError) as e:
                logger.warning("计算文件哈希失败，已跳过", extra={"file": full_path, "error": str(e)})
                continue

            yield rel_path, filename, file_hash

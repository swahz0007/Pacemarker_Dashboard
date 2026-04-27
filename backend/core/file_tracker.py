"""
文件追踪模块
负责文件哈希计算、已处理文件记录和增量更新检测
"""

import os
import json
import hashlib
import logging
from datetime import datetime

from config import DATA_REPOSITORY, PROCESSED_FILES_FILE

logger = logging.getLogger(__name__)
EXCEL_EXTENSIONS = ('.xls', '.xlsx')
TEMP_PREFIX = '~$'


def get_file_hash(filepath):
    """计算文件的 MD5 哈希值"""
    hasher = hashlib.md5()
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
    with open(PROCESSED_FILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_new_or_modified_files():
    """查找新增或修改的文件"""
    processed = load_processed_files()
    new_files = []
    modified_files = []

    if not DATA_REPOSITORY.exists():
        logger.warning("数据仓库目录不存在: %s", str(DATA_REPOSITORY))
        return new_files, modified_files

    for rel_path, filename, file_hash in _iter_excel_files():
        record = processed.get(rel_path) if isinstance(processed.get(rel_path), dict) else None
        if not record:
            new_files.append((rel_path, filename, file_hash))
        elif record.get('hash') != file_hash:
            modified_files.append((rel_path, filename, file_hash))
    
    return new_files, modified_files


def build_file_index():
    """建立所有Excel文件的索引"""
    processed = {}
    if not DATA_REPOSITORY.exists():
        logger.warning("数据仓库目录不存在: %s", str(DATA_REPOSITORY))
        return 0

    for rel_path, _, file_hash in _iter_excel_files():
        processed[rel_path] = {'hash': file_hash, 'last_processed': datetime.now().isoformat()}
    
    save_processed_files(processed)
    return len(processed)


def _iter_excel_files():
    for root, _, files in os.walk(DATA_REPOSITORY):
        for filename in files:
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

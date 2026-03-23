"""
文件追踪模块
负责文件哈希计算、已处理文件记录和增量更新检测
"""

import os
import json
import hashlib
from datetime import datetime

from config import DATA_REPOSITORY, PROCESSED_FILES_FILE


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
        with open(PROCESSED_FILES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
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
    
    for root, dirs, files in os.walk(DATA_REPOSITORY):
        for f in files:
            if not f.lower().endswith(('.xls', '.xlsx')):
                continue
            if f.startswith('~$'):
                continue
                
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, start=DATA_REPOSITORY.parent)
            file_hash = get_file_hash(full_path)
            
            if rel_path not in processed:
                new_files.append((rel_path, f, file_hash))
            elif processed[rel_path]['hash'] != file_hash:
                modified_files.append((rel_path, f, file_hash))
    
    return new_files, modified_files


def build_file_index():
    """建立所有Excel文件的索引"""
    processed = {}
    for root, dirs, files in os.walk(DATA_REPOSITORY):
        for f in files:
            if not f.lower().endswith(('.xls', '.xlsx')):
                continue
            if f.startswith('~$'):
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, start=DATA_REPOSITORY.parent)
            file_hash = get_file_hash(full_path)
            processed[rel_path] = {'hash': file_hash, 'last_processed': datetime.now().isoformat()}
    
    save_processed_files(processed)
    return len(processed)

"""
Pacemaker Dashboard Backend - 主入口
提供统一的接口来运行数据处理流程

用法:
    python main.py            # 全量处理
    python main.py --update   # 增量更新
"""

import argparse
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

from scripts.match_templates import match_all_files
from scripts.extract_data import extract_all_data
from core.grouping import process_and_split_records
from core.file_tracker import build_file_index


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
        logger.warning("增量更新模式暂时禁用，请使用全量处理。")
        # TODO: 重构增量更新逻辑以适配新的内存管道
    elif args.match:
        match_all_files()
    elif args.extract:
        data = extract_all_data()
        logger.info(f"提取了 {len(data)} 条记录")
    else:
        full_process()


if __name__ == "__main__":
    main()

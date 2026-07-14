"""
Pacemaker Dashboard Backend - 配置文件
版本: 1.0
"""

import os
from pathlib import Path

# 路径配置
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent


def _env_path(name: str, default: Path) -> Path:
    """读取可选路径配置；未配置时保持开发环境的原有默认值。"""
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser() if value else default


# 科室版通过环境变量把原始报告与程序包解耦；开发环境仍默认使用仓库内目录。
DATA_REPOSITORY = _env_path(
    "PACEMAKER_REPORT_DIR",
    PROJECT_ROOT / "01_data_repository",
)
WORK_DIR = _env_path("PACEMAKER_WORK_DIR", PROJECT_ROOT)

# 数据文件
TEMPLATES_FILE = BACKEND_DIR / "data" / "templates.json"
# PyInstaller 的模块 __file__ 位于临时运行根目录时，数据文件会保留 backend/data 层级。
if not TEMPLATES_FILE.exists():
    bundled_templates = BACKEND_DIR / "backend" / "data" / "templates.json"
    if bundled_templates.exists():
        TEMPLATES_FILE = bundled_templates
PATIENT_RECORDS_DIR = _env_path(
    "PACEMAKER_PATIENT_RECORDS_DIR",
    WORK_DIR / "patient_records",
)  # 所有输出都在工作目录，不写入原始报告目录
MATCHING_REPORT_FILE = PATIENT_RECORDS_DIR / "matching_report.csv"
PROCESSED_FILES_FILE = PATIENT_RECORDS_DIR / "processed_files.json"
QUARANTINE_RECORDS_FILE = PATIENT_RECORDS_DIR / "quarantine_records.json"

# 输出数据的可追溯版本。每次改变提取/分组规则时递增，以便增量流程与审计
# 能够识别需要重新处理的历史记录。
PIPELINE_VERSION = "2.0.0"
RECORD_SCHEMA_VERSION = "2.0.0"

# 关键字定义
KW_BASIC = "基本工作参数"
KW_ANTITACHY = "抗心动过速参数"  # ICD/CRT-D 特有
KW_TEST = "测试参数"
KW_EVENT = "事件记录"

# 抗心动过速参数表格定义 (ICD/CRT-D)
ZAT_COL_HEADERS = ["分区", "检测频率", "治疗"]
ZAT_ROW_HEADERS = ["VF", "F-VT", "VT-2", "VT-1"]

# 表格定义
Z2_COL_HEADERS = [
    "输出电压", "输出脉宽", "阈值管理", "感知灵敏度",
    "起搏极性", "感知极性", "备注"
]
Z2_ROW_HEADERS = ["心房", "右心室", "左心室"]

Z3_COL_HEADERS = ["阈值", "脉宽", "感知", "阻抗", "起搏极性", "感知极性", "起搏比例"]
Z3_ROW_HEADERS = ["心房", "右心室", "左心室"]

# 忽略字段集合
IGNORE_IN_KV = set(
    Z2_COL_HEADERS + Z2_ROW_HEADERS + Z3_COL_HEADERS + Z3_ROW_HEADERS +
    [KW_BASIC, KW_TEST, KW_EVENT]
)
for h in Z2_COL_HEADERS + Z3_COL_HEADERS:
    IGNORE_IN_KV.update([
        h, h + "（V）", h + "（ms）", h + "（mV）", h + "（Ω）", h + "（%）",
        h + "(V)", h + "(ms)", h + "(mV)", h + "(Ω)", h + "(%)"
    ])

# 确保输出目录存在
PATIENT_RECORDS_DIR.mkdir(parents=True, exist_ok=True)


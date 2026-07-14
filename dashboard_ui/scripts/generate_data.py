"""生成离线 Dashboard 数据包及数据质量核查摘要。"""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


# .../dashboard_ui/scripts/generate_data.py -> .../Pacemarker_Dashboard
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PATIENT_RECORDS_DIR = Path(
    os.environ.get("PACEMAKER_PATIENT_RECORDS_DIR", BASE_DIR / "patient_records")
).expanduser()
OUTPUT_DIR = Path(
    os.environ.get("PACEMAKER_DASHBOARD_DATA_DIR", BASE_DIR / "dashboard_ui" / "data")
).expanduser()
OUTPUT_FILE = OUTPUT_DIR / "data_bundle.js"

# 非患者记录文件，应跳过
SKIP_FILES = {"processed_files.json", "matching_report.csv", "quarantine_records.json"}
QUALITY_SCHEMA_VERSION = "1.0.0"
OFFLINE_MODE = os.environ.get("PACEMAKER_OFFLINE_MODE", "") == "1"


def _read_json(path: Path, default):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError):
        return default


def _read_matching_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            return [
                row for row in reader
                if row.get("Filename", "") and not row.get("Filename", "").startswith("~$")
            ]
    except (OSError, csv.Error):
        return []


def _is_matched_status(value: str) -> bool:
    return str(value or "").strip().upper() == "MATCHED"


def _iso_mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return ""


def _issue_from_unmatched(row: dict) -> dict:
    return {
        "issue_id": f"unmatched:{row.get('Filename', '')}",
        "issue_type": "模板未匹配",
        "severity": "blocker",
        "status": "待核查",
        "filename": row.get("Filename", ""),
        "source_path": row.get("Full Path", ""),
        "patient_name": "",
        "registration_id": "",
        "report_date": "",
        "detail": "未找到可用模板；本轮全量处理会保留既有患者输出。",
        "values": {
            "识别品牌": row.get("Detected Brand", ""),
            "识别类型": row.get("Detected Type", ""),
            "匹配模板": row.get("Matched Template", ""),
        },
    }


def _issue_from_quarantine(record: dict, source_by_filename: dict[str, str], index: int) -> dict:
    meta = record.get("meta", {}) if isinstance(record, dict) else {}
    header = record.get("header", {}) if isinstance(record, dict) else {}
    filename = str(meta.get("filename", ""))
    flags = meta.get("quality_flags", [])
    flags = flags if isinstance(flags, list) else []
    codes = [str(flag.get("code", "")) for flag in flags if isinstance(flag, dict)]

    detail_map = {
        "IDENTITY_NAME_MISMATCH": "文件名姓名与报告内姓名不一致。",
    }
    detail = "；".join(detail_map.get(code, code) for code in codes if code)
    if not detail:
        detail = "记录已被隔离，等待人工核查。"

    return {
        "issue_id": f"quarantine:{meta.get('source_id', '') or filename or index}",
        "issue_type": "身份信息矛盾" if any(code.startswith("IDENTITY_") for code in codes) else "隔离记录",
        "severity": "review",
        "status": "待核查",
        "filename": filename,
        "source_path": source_by_filename.get(filename, ""),
        "patient_name": str(header.get("姓名", "")),
        "registration_id": str(header.get("登记号", "")),
        "report_date": str(record.get("footer_meta", {}).get("程控日期", "")),
        "detail": detail,
        "values": {
            "报告内姓名": str(header.get("姓名", "")),
            "报告内登记号": str(header.get("登记号", "")),
            "质量标记": ", ".join(codes),
        },
    }


def build_quality_report(
    records_dir: Path,
    index_data: list[dict],
    records_map: dict,
    *,
    offline_mode: bool = False,
    pipeline_warning: str = "",
) -> dict:
    """从现有处理产物构建质量报告；不触碰原始报告目录。"""
    matching_path = records_dir / "matching_report.csv"
    matching_rows = _read_matching_rows(matching_path)
    source_by_filename = {
        row.get("Filename", ""): row.get("Full Path", "")
        for row in matching_rows
        if row.get("Filename", "")
    }

    quarantine_payload = _read_json(records_dir / "quarantine_records.json", {})
    if isinstance(quarantine_payload, dict):
        quarantine_records = quarantine_payload.get("records", [])
    elif isinstance(quarantine_payload, list):
        quarantine_records = quarantine_payload
    else:
        quarantine_records = []
    quarantine_records = [record for record in quarantine_records if isinstance(record, dict)]

    issues = [
        _issue_from_unmatched(row)
        for row in matching_rows
        if not _is_matched_status(row.get("Status", ""))
    ]
    issues.extend(
        _issue_from_quarantine(record, source_by_filename, index)
        for index, record in enumerate(quarantine_records, start=1)
    )

    issue_type_counts = Counter(issue["issue_type"] for issue in issues)
    severity_counts = Counter(issue["severity"] for issue in issues)
    record_count = sum(
        len(patient.get("程控记录", []))
        for patient in records_map.values()
        if isinstance(patient, dict) and isinstance(patient.get("程控记录"), list)
    )
    summary = {
        "state": "处理未完整成功" if pipeline_warning else ("需核查" if issues else "处理正常"),
        "total_files": len(matching_rows),
        "matched_files": sum(1 for row in matching_rows if _is_matched_status(row.get("Status", ""))),
        "unmatched_files": sum(1 for row in matching_rows if not _is_matched_status(row.get("Status", ""))),
        "patient_count": len(index_data),
        "record_count": record_count,
        "quarantine_records": len(quarantine_records),
        "pending_issues": len(issues),
        "issue_type_counts": dict(issue_type_counts),
        "severity_counts": dict(severity_counts),
        "matching_report_updated_at": _iso_mtime(matching_path),
        "source_dir": os.environ.get("PACEMAKER_REPORT_DIR", "") if offline_mode else "",
    }

    return {
        "available": bool(offline_mode),
        "schema_version": QUALITY_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_warning": pipeline_warning if offline_mode else "",
        "summary": summary,
        # 公开演示包只保留空列表，避免暴露本地路径和真实核查明细。
        "issues": issues if offline_mode else [],
    }


def generate_bundle():
    print(f"Base Dir: {BASE_DIR}")
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True)

    patient_files = sorted(PATIENT_RECORDS_DIR.glob("*.json"))
    index_data = []
    records_map = {}
    error_count = 0

    print(f"Scanning {len(patient_files)} files in {PATIENT_RECORDS_DIR}...")

    for file_path in patient_files:
        try:
            filename = file_path.name
            if filename in SKIP_FILES:
                continue
            with open(file_path, "r", encoding="utf-8") as stream:
                data = json.load(stream)

            records_map[filename] = data
            registration_id = data.get("登记号", "Unknown")
            name = data.get("姓名", "Unknown")
            record_count = data.get("程控次数", 0)

            latest_record = data.get("程控记录", [])[-1] if data.get("程控记录") else {}
            header = latest_record.get("header", {})
            index_data.append({
                "id": str(registration_id),
                "name": name,
                "count": record_count,
                "brand": header.get("品牌", "Unknown"),
                "model": header.get("型号", "Unknown"),
                "implant_date": header.get("植入日期", ""),
                "file_name": filename,
            })
        except Exception as exc:
            error_count += 1
            print(f"Error reading {file_path}: {exc}")

    index_data.sort(key=lambda item: item["id"])
    quality = build_quality_report(
        PATIENT_RECORDS_DIR,
        index_data,
        records_map,
        offline_mode=OFFLINE_MODE,
        pipeline_warning=os.environ.get("PACEMAKER_PIPELINE_WARNING", ""),
    )

    bundle_content = {
        "index": index_data,
        "records": records_map,
        "quality": quality,
    }
    js_content = f"window.PACEMAKER_DATA={json.dumps(bundle_content, ensure_ascii=False, separators=(',', ':'))};"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as stream:
        stream.write(js_content)

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    size_display = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.2f} MB"
    print(f"Generated: {len(index_data)} patients, bundle size: {size_display}")
    if error_count > 0:
        print(f"Warning: {error_count} files failed to load")
    if OFFLINE_MODE:
        print(
            "Quality: "
            f"{quality['summary']['pending_issues']} pending issues, "
            f"{quality['summary']['quarantine_records']} quarantined records"
        )
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_bundle()

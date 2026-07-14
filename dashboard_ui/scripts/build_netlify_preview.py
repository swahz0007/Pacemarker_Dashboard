"""
Build an anonymized Netlify preview package for the static dashboard.

The generated package is intentionally written outside the repository under
C:\\tmp so ignored patient data in dashboard_ui/data is never deployed directly.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DASHBOARD_DIR = BASE_DIR / "dashboard_ui"
SOURCE_BUNDLE = DASHBOARD_DIR / "data" / "data_bundle.js"
DEFAULT_OUTPUT_ROOT = Path(r"C:\tmp")
DEFAULT_SOURCE_BUNDLE = DASHBOARD_DIR / "data" / "data_bundle.js"
SENSITIVE_KEYWORDS = (
    r"E:\\",
    r"C:\\",
    "01_data_repository",
    "patient_records",
    ".xls",
    ".xlsx",
    "DISPIMG",
)
DROP_KEYS = {
    "filename",
    "path",
    "source",
    "source_path",
    "file_path",
    "签名行内容",
}
PRIVACY_POLICY_VERSION = "2.1.0"
IDENTIFIER_KEY_FRAGMENTS = (
    "姓名", "登记号", "身份证", "证件", "手机号", "电话", "邮箱",
    "address", "email", "phone", "patient_name", "patient_id",
)
# The public demo preserves programming conclusions after identifier scrubbing.
# Less constrained free-text fields remain withheld because they are more likely
# to contain incidental identifiers or narrative history.
FREE_TEXT_KEY_FRAGMENTS = ("备注", "说明", "建议", "签名", "地址", "病史")
PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[0-9Xx](?![0-9Xx])")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PATH_PATTERN = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|/(?:home|users|tmp|var)/)")
ANON_RECORD_NAME_PATTERN = re.compile(r"P\d{4}\.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an anonymized static publish directory for Netlify."
    )
    parser.add_argument(
        "--source-bundle",
        type=Path,
        default=DEFAULT_SOURCE_BUNDLE,
        help="Source data_bundle.js to anonymize.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Exact publish directory to create. Overrides --output-root and --timestamp.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory where the timestamped preview package will be created.",
    )
    parser.add_argument(
        "--timestamp",
        default=datetime.now().strftime("%Y%m%d_%H%M%S"),
        help="Timestamp suffix for reproducible package paths.",
    )
    return parser.parse_args()


def load_bundle(bundle_path: Path) -> dict[str, Any]:
    raw = bundle_path.read_text(encoding="utf-8")
    prefix = "window.PACEMAKER_DATA="
    if not raw.startswith(prefix) or not raw.rstrip().endswith(";"):
        raise ValueError(f"Unexpected bundle format: {bundle_path}")
    return json.loads(raw[len(prefix) : raw.rfind(";")])


def stable_shift_days(seed: str) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 1461 - 730


def parse_date_value(value: str, key: str) -> date | None:
    text = value.strip()
    if not text:
        return None

    match = re.search(r"(20\d{2}|19\d{2})[-./年](\d{1,2})(?:[-./月](\d{1,2}))?", text)
    if match:
        year, month, day = match.groups()
        try:
            return date(int(year), int(month), int(day or 1))
        except ValueError:
            return None

    if "日期" in key and re.fullmatch(r"\d{5}", text):
        serial = int(text)
        if 30000 <= serial <= 60000:
            return date(1899, 12, 30) + timedelta(days=serial)

    return None


def shift_date_value(value: str, key: str, shift_days: int) -> str:
    parsed = parse_date_value(value, key)
    if parsed is None:
        return value
    shifted = parsed + timedelta(days=shift_days)
    return shifted.isoformat()


def age_bucket(value: Any) -> str:
    match = re.search(r"\d{1,3}", str(value))
    if not match:
        return "未知"
    age = int(match.group(0))
    if age < 0 or age > 120:
        return "未知"
    lower = age // 10 * 10
    upper = lower + 9
    return f"{lower}-{upper}岁"


def is_allowed_anonymized_value(value: str) -> bool:
    return bool(
        re.fullmatch(r"P\d{4}", value)
        or re.fullmatch(r"P\d{4}\.json", value)
        or re.fullmatch(r"患者 P\d{4}", value)
        or re.fullmatch(r"患者 P\d{4} P\d{4}", value)
    )


def _is_identifier_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment.lower() in lowered for fragment in IDENTIFIER_KEY_FRAGMENTS)


def _is_free_text_key(key: str) -> bool:
    return any(fragment in key for fragment in FREE_TEXT_KEY_FRAGMENTS)


def _mark(redaction_counts: dict[str, int], category: str) -> None:
    redaction_counts[category] = redaction_counts.get(category, 0) + 1


def sanitize_string(
    value: str, key: str, shift_days: int,
    sensitive_values: list[str], redaction_counts: dict[str, int],
) -> str:
    if _is_free_text_key(key):
        _mark(redaction_counts, "free_text")
        return "[已脱敏：自由文本不发布]"
    if "日期" in key or "时间" in key:
        value = shift_date_value(value, key, shift_days)

    for sensitive_value in sensitive_values:
        if sensitive_value and sensitive_value in value:
            value = value.replace(sensitive_value, "[已脱敏]")
            _mark(redaction_counts, "known_identifier")
    value, phone_count = PHONE_PATTERN.subn("[电话已脱敏]", value)
    value, id_card_count = ID_CARD_PATTERN.subn("[证件号已脱敏]", value)
    value, email_count = EMAIL_PATTERN.subn("[邮箱已脱敏]", value)
    value, path_count = PATH_PATTERN.subn("[路径已脱敏]", value)
    for category, count in (
        ("phone", phone_count), ("id_card", id_card_count),
        ("email", email_count), ("path", path_count),
    ):
        if count:
            redaction_counts[category] = redaction_counts.get(category, 0) + count

    lowered = value.lower()
    if any(token.lower() in lowered for token in SENSITIVE_KEYWORDS):
        _mark(redaction_counts, "sensitive_token")
        return ""
    return value


def sanitize_obj(
    obj: Any, alias: str, display_name: str, shift_days: int,
    sensitive_values: list[str], redaction_counts: dict[str, int],
) -> Any:
    if isinstance(obj, list):
        return [
            sanitize_obj(item, alias, display_name, shift_days, sensitive_values, redaction_counts)
            for item in obj
        ]

    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for key, value in obj.items():
            lower_key = key.lower()
            if (
                lower_key in DROP_KEYS or key in DROP_KEYS or "签名" in key
                or any(token in lower_key for token in ("filename", "path", "source"))
            ):
                _mark(redaction_counts, "dropped_metadata")
                continue

            if "姓名" in key and "登记号" in key:
                cleaned[key] = f"{display_name} {alias}"
            elif "姓名" in key:
                cleaned[key] = display_name
            elif "登记号" in key:
                cleaned[key] = alias
            elif _is_identifier_key(key):
                cleaned[key] = "[已脱敏]"
                _mark(redaction_counts, "identifier_field")
            elif "年龄" in key:
                cleaned[key] = age_bucket(value)
            elif key == "file_name":
                cleaned[key] = f"{alias}.json"
            elif isinstance(value, str):
                cleaned[key] = sanitize_string(
                    value, key, shift_days, sensitive_values, redaction_counts,
                )
            else:
                cleaned[key] = sanitize_obj(
                    value, alias, display_name, shift_days, sensitive_values, redaction_counts,
                )
        return cleaned

    if isinstance(obj, str):
        return sanitize_string(obj, "", shift_days, sensitive_values, redaction_counts)

    return obj


def collect_sensitive_values(bundle: dict[str, Any]) -> list[str]:
    """收集原包内可识别字段值，供全局泄露扫描与自由文本替换使用。"""
    values: set[str] = set()

    def visit(obj: Any, key: str = "") -> None:
        if isinstance(obj, dict):
            for child_key, child_value in obj.items():
                if (
                    _is_identifier_key(child_key)
                    or "签名" in child_key
                    or child_key.lower() in {"filename", "path", "source", "source_id"}
                ):
                    if isinstance(child_value, str) and child_value.strip():
                        stripped = child_value.strip()
                        if not is_allowed_anonymized_value(stripped):
                            values.add(stripped)
                if child_key == "file_name" and isinstance(child_value, str):
                    stripped = child_value.strip()
                    if not is_allowed_anonymized_value(stripped):
                        values.add(stripped)
                visit(child_value, child_key)
        elif isinstance(obj, list):
            for item in obj:
                visit(item, key)

    visit(bundle)
    return sorted(
        {
            value for value in values
            if len(value) >= 2
            and value not in {"未知", "Unknown", "--"}
            and not is_allowed_anonymized_value(value)
        },
        key=len, reverse=True,
    )


def anonymize_bundle(bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    records = bundle.get("records", {})
    if not isinstance(records, dict):
        raise ValueError("Bundle records must be an object")

    anon_index: list[dict[str, Any]] = []
    anon_records: dict[str, Any] = {}
    redaction_counts: dict[str, int] = {}
    sensitive_values = collect_sensitive_values(bundle)

    for idx, original_key in enumerate(sorted(records.keys()), start=1):
        alias = f"P{idx:04d}"
        display_name = f"患者 {alias}"
        original = records[original_key]
        seed = str(original.get("登记号") or original_key)
        shift_days = stable_shift_days(seed)
        cleaned = sanitize_obj(
            copy.deepcopy(original), alias, display_name, shift_days,
            sensitive_values, redaction_counts,
        )

        cleaned["登记号"] = alias
        cleaned["姓名"] = display_name
        cleaned["file_name"] = f"{alias}.json"

        latest = {}
        history = cleaned.get("程控记录") or []
        if isinstance(history, list) and history:
            latest = history[-1] if isinstance(history[-1], dict) else {}
        header = latest.get("header", {}) if isinstance(latest, dict) else {}

        anon_key = f"{alias}.json"
        anon_records[anon_key] = cleaned
        anon_index.append(
            {
                "id": alias,
                "name": display_name,
                "count": cleaned.get("程控次数", 0),
                "brand": header.get("品牌", "Unknown"),
                "model": header.get("型号", "Unknown"),
                "implant_date": header.get("植入日期", ""),
                "file_name": anon_key,
            }
        )

    return {"index": anon_index, "records": anon_records}, redaction_counts


def audit_anonymized_bundle(bundle: dict[str, Any], sensitive_values: list[str]) -> list[dict[str, str]]:
    """在写出任何发布文件前验证脱敏结果；发现候选泄露即 fail closed。"""
    findings: list[dict[str, str]] = []
    serialized = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))

    for value in sensitive_values:
        if value and value in serialized:
            findings.append({"type": "known_identifier", "value": value[:120]})
    def iter_strings(obj: Any):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(key, str):
                    yield key
                yield from iter_strings(value)
        elif isinstance(obj, list):
            for item in obj:
                yield from iter_strings(item)
        elif isinstance(obj, str):
            yield obj

    string_values = list(iter_strings(bundle))
    for name, pattern in (
        ("phone", PHONE_PATTERN), ("id_card", ID_CARD_PATTERN),
        ("email", EMAIL_PATTERN), ("path", PATH_PATTERN),
    ):
        if any(pattern.search(value) for value in string_values):
            findings.append({"type": name, "value": "pattern_match"})
    for token in SENSITIVE_KEYWORDS:
        if token.lower() in serialized.lower():
            findings.append({"type": "sensitive_token", "value": token[:120]})

    def visit(obj: Any, path: str = "$") -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}"
                lowered = key.lower()
                if key != "file_name" and (
                    lowered in DROP_KEYS
                    or any(token in lowered for token in ("filename", "path", "source"))
                    or "签名" in key
                ):
                    findings.append({"type": "forbidden_key", "value": current_path[:120]})
                if "姓名" in key and isinstance(value, str) and not is_allowed_anonymized_value(value):
                    findings.append({"type": "invalid_name_alias", "value": current_path[:120]})
                if (
                    "登记号" in key and "姓名" not in key
                    and isinstance(value, str)
                    and not re.fullmatch(r"P\d{4}", value)
                ):
                    findings.append({"type": "invalid_id_alias", "value": current_path[:120]})
                if _is_free_text_key(key) and isinstance(value, str) and value != "[已脱敏：自由文本不发布]":
                    findings.append({"type": "free_text_present", "value": current_path[:120]})
                visit(value, current_path)
        elif isinstance(obj, list):
            for index, item in enumerate(obj):
                visit(item, f"{path}[{index}]")

    visit(bundle)
    return findings


def create_publish_dir(output_root: Path, timestamp: str, output_dir: Path | None = None) -> Path:
    publish_dir = output_dir or output_root / f"pacemarker_netlify_preview_{timestamp}"
    if publish_dir.exists():
        raise FileExistsError(f"Refusing to reuse existing publish directory: {publish_dir}")

    identity_client = DASHBOARD_DIR / "assets" / "js" / "identity-client.js"
    if not identity_client.exists():
        raise FileNotFoundError(
            "Missing generated identity client. Run 'npm run build:identity' before building the publish directory."
        )

    publish_dir.mkdir(parents=True)
    (publish_dir / "data").mkdir()
    shutil.copy2(DASHBOARD_DIR / "index.html", publish_dir / "index.html")
    shutil.copytree(
        DASHBOARD_DIR / "assets",
        publish_dir / "assets",
        ignore=shutil.ignore_patterns("auth-entry.js"),
    )
    return publish_dir


def write_bundle(publish_dir: Path, bundle: dict[str, Any]) -> Path:
    """Write a compact index and independently fetchable, de-identified records."""
    index = bundle.get("index")
    records = bundle.get("records")
    if not isinstance(index, list) or not isinstance(records, dict):
        raise ValueError("Anonymized bundle must contain an index list and records object")

    data_dir = publish_dir / "data"
    records_dir = data_dir / "records"
    records_dir.mkdir(exist_ok=False)
    index_file = data_dir / "index.json"
    index_file.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    for filename, record in sorted(records.items()):
        if not isinstance(filename, str) or not ANON_RECORD_NAME_PATTERN.fullmatch(filename):
            raise ValueError(f"Unexpected anonymized record filename: {filename!r}")
        output_file = records_dir / filename
        output_file.write_text(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return index_file


def scan_publish_dir(publish_dir: Path, sensitive_values: list[str]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    scan_values = sensitive_values + list(SENSITIVE_KEYWORDS)
    for file_path in publish_dir.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for value in scan_values:
            if value and value in content:
                findings.append(
                    {
                        "file": str(file_path),
                        "value": value[:120],
                    }
                )
    return findings


def write_audit(
    publish_dir: Path, bundle: dict[str, Any], findings: list[dict[str, str]],
    redaction_counts: dict[str, int],
) -> Path:
    audit_file = publish_dir / "privacy_audit.json"
    audit = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "privacy_policy_version": PRIVACY_POLICY_VERSION,
        "status": "pass" if not findings else "fail",
        "patient_count": len(bundle.get("index", [])),
        "record_count": len(bundle.get("records", {})),
        "findings": findings,
        "redaction_counts": redaction_counts,
    }
    audit_file.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit_file


def main() -> int:
    args = parse_args()
    bundle = load_bundle(args.source_bundle)
    sensitive_values = collect_sensitive_values(bundle)
    anonymized, redaction_counts = anonymize_bundle(bundle)
    preflight_findings = audit_anonymized_bundle(anonymized, sensitive_values)
    if preflight_findings:
        print("Privacy audit: FAIL (publish directory was not created)")
        for finding in preflight_findings[:20]:
            print(f"Leak candidate: {finding['type']} -> {finding['value']}")
        return 1

    publish_dir = create_publish_dir(args.output_root, args.timestamp, args.output_dir)
    bundle_file = write_bundle(publish_dir, anonymized)
    findings = scan_publish_dir(publish_dir, sensitive_values)
    audit_file = write_audit(publish_dir, anonymized, findings, redaction_counts)

    print(f"Publish directory: {publish_dir}")
    print(f"Index: {bundle_file}")
    print(f"Audit: {audit_file}")
    print(f"Patients: {len(anonymized['index'])}")
    print(f"Privacy audit: {'PASS' if not findings else 'FAIL'}")
    if findings:
        for finding in findings[:20]:
            print(f"Leak candidate: {finding['file']} -> {finding['value']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

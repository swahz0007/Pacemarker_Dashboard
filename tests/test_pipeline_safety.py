from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from core.grouping import group_by_registration_id  # noqa: E402
from core.utils import atomic_write_json, proxy_registration_id  # noqa: E402
from scripts.match_templates import (  # noqa: E402
    STATUS_MATCHED,
    STATUS_UNMATCHED,
    find_best_template,
    is_matched_status,
    load_templates,
)
from launcher import assert_safe_paths  # noqa: E402
from dashboard_ui.scripts.generate_data import build_quality_report  # noqa: E402


def load_preview_builder():
    module_path = ROOT / "dashboard_ui" / "scripts" / "build_netlify_preview.py"
    spec = importlib.util.spec_from_file_location("build_netlify_preview", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load preview builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PipelineSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preview = load_preview_builder()

    def test_only_explicit_match_status_is_accepted(self):
        self.assertTrue(is_matched_status(STATUS_MATCHED))
        self.assertFalse(is_matched_status(STATUS_UNMATCHED))
        self.assertFalse(is_matched_status("No Match"))
        self.assertFalse(is_matched_status("matched with warning"))

    def test_boston_icd_filename_uses_the_dedicated_template(self):
        templates = load_templates(ROOT / "backend" / "data" / "templates.json")
        matched, brand, device_type = find_best_template(
            "示例患者ICD报告单（波科）.xlsx", templates
        )
        self.assertEqual(matched, "ICD报告单（波科）.xlsx")
        self.assertEqual(brand, "波科")
        self.assertEqual(device_type, "ICD报告单")

    def test_identity_conflicts_are_quarantined(self):
        record = {
            "header": {"姓名": "患者甲", "登记号": "R-001"},
            "meta": {
                "filename": "患者甲.xlsx",
                "quality_flags": [{"code": "IDENTITY_NAME_MISMATCH"}],
                "source_id": "sha256:test",
            },
        }
        grouped, quarantined = group_by_registration_id([record], return_quarantine=True)
        self.assertEqual(grouped, {})
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(
            quarantined[0]["meta"]["quality_flags"][0]["code"],
            "IDENTITY_NAME_MISMATCH",
        )

    def test_proxy_registration_id_uses_source_context(self):
        first = proxy_registration_id("same_name.xls", "sha256:first")
        second = proxy_registration_id("same_name.xls", "sha256:second")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("PROXY_"))

    def test_atomic_json_write_replaces_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "record.json"
            atomic_write_json(target, {"state": "first"})
            atomic_write_json(target, {"state": "second"})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"state": "second"})
            self.assertFalse(list(Path(tmp).glob("*.tmp")))

    def test_anonymization_preserves_scrubbed_conclusion_and_blocks_other_free_text(self):
        source = {
            "records": {
                "private_source.json": {
                    "登记号": "REG-42",
                    "姓名": "示例患者",
                    "file_name": "private_source.json",
                    "程控次数": 1,
                    "程控记录": [
                        {
                            "header": {
                                "姓名": "示例患者",
                                "登记号": "REG-42",
                                "品牌": "测试品牌",
                            },
                            "events_and_footer": {
                                "结论": "示例患者需于下次门诊复核",
                                "备注": "联系方式 13800138000",
                            },
                        }
                    ],
                }
            }
        }
        sensitive_values = self.preview.collect_sensitive_values(source)
        anonymized, _ = self.preview.anonymize_bundle(source)
        findings = self.preview.audit_anonymized_bundle(anonymized, sensitive_values)
        serialized = json.dumps(anonymized, ensure_ascii=False)

        self.assertEqual(findings, [])
        self.assertNotIn("示例患者", serialized)
        self.assertNotIn("REG-42", serialized)
        self.assertNotIn("13800138000", serialized)
        self.assertIn("[已脱敏]需于下次门诊复核", serialized)
        self.assertIn("[已脱敏：自由文本不发布]", serialized)

    def test_publish_bundle_splits_index_and_records(self):
        bundle = {
            "index": [{"id": "P0001", "file_name": "P0001.json"}],
            "records": {"P0001.json": {"登记号": "P0001"}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            publish_dir = Path(tmp)
            (publish_dir / "data").mkdir()
            index_path = self.preview.write_bundle(publish_dir, bundle)
            record_path = publish_dir / "data" / "records" / "P0001.json"
            self.assertEqual(json.loads(index_path.read_text(encoding="utf-8"))[0]["id"], "P0001")
            self.assertEqual(json.loads(record_path.read_text(encoding="utf-8"))["登记号"], "P0001")
            self.assertFalse((publish_dir / "data" / "data_bundle.js").exists())

    def test_runtime_work_dir_cannot_be_inside_report_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "reports"
            report_dir.mkdir()
            with self.assertRaises(RuntimeError):
                assert_safe_paths(report_dir, report_dir / "runtime")

    def test_runtime_work_dir_is_created_when_sibling_to_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "reports"
            work_dir = root / "runtime"
            report_dir.mkdir()
            assert_safe_paths(report_dir, work_dir)
            self.assertTrue(work_dir.is_dir())
            self.assertTrue((work_dir / "dashboard").is_dir())

    def test_quality_report_surfaces_offline_issues_but_hides_public_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            records_dir = Path(tmp)
            (records_dir / "matching_report.csv").write_text(
                "Filename,Full Path,Detected Brand,Detected Type,Matched Template,Status\n"
                "good.xlsx,C:\\reports\\good.xlsx,雅培,起搏器报告单,template.xlsx,MATCHED\n"
                "unknown.xlsx,C:\\reports\\unknown.xlsx,未知,起搏器报告单,N/A,UNMATCHED\n",
                encoding="utf-8-sig",
            )
            (records_dir / "quarantine_records.json").write_text(
                json.dumps({
                    "records": [{
                        "meta": {
                            "filename": "conflict.xlsx",
                            "source_id": "sha256:conflict",
                            "quality_flags": [{"code": "IDENTITY_NAME_MISMATCH"}],
                        },
                        "header": {"姓名": "患者甲", "登记号": "R-001"},
                        "footer_meta": {"程控日期": "2026-07-14"},
                    }]
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            offline = build_quality_report(
                records_dir,
                [{"id": "R-001"}],
                {"R-001.json": {"程控记录": [{}]}},
                offline_mode=True,
            )
            self.assertTrue(offline["available"])
            self.assertEqual(offline["summary"]["unmatched_files"], 1)
            self.assertEqual(offline["summary"]["quarantine_records"], 1)
            self.assertEqual(len(offline["issues"]), 2)
            self.assertTrue(any(item["issue_type"] == "身份信息矛盾" for item in offline["issues"]))

            public = build_quality_report(
                records_dir,
                [{"id": "R-001"}],
                {"R-001.json": {"程控记录": [{}]}},
                offline_mode=False,
            )
            self.assertFalse(public["available"])
            self.assertEqual(public["issues"], [])
            self.assertEqual(public["summary"]["source_dir"], "")


if __name__ == "__main__":
    unittest.main()

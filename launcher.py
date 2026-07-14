"""Pacemaker Dashboard 离线运行入口。

该入口用于 PyInstaller 打包后的科室版运行，不需要目标电脑安装 Python。
它只读取报告目录，将结构化数据和本地 Dashboard 写入独立工作目录。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
import webbrowser
from pathlib import Path


APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
BACKEND_ROOT = APP_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


APP_NAME = "PacemakerDashboard"
CONFIG_FILENAME = "pacemaker_config.json"
DEFAULT_CONFIG = {
    "report_dir": "",
    "work_dir": "",
}


def executable_dir() -> Path:
    """返回 EXE 所在目录；源码运行时返回 launcher.py 所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def default_work_dir() -> Path:
    return app_data_dir() / "runtime_data"


def app_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    base = Path(local_app_data) if local_app_data else Path.home()
    return base / APP_NAME


def config_path() -> Path:
    override = os.environ.get("PACEMAKER_CONFIG_PATH", "").strip()
    return Path(override).expanduser() if override else app_data_dir() / CONFIG_FILENAME


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"配置文件无法读取：{path}\n{exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"配置文件格式不正确：{path}")
    result = dict(DEFAULT_CONFIG)
    result.update({key: value.get(key, "") for key in DEFAULT_CONFIG})
    return result


def save_config(report_dir: Path, work_dir: Path) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "report_dir": str(report_dir),
        "work_dir": str(work_dir),
    }
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
    return path


def choose_report_dir() -> Path | None:
    """首次运行时弹出目录选择器；无图形环境时返回 None。"""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(
            title="选择科室程控报告目录（程序只读）",
            mustexist=True,
        )
        root.destroy()
        return Path(selected) if selected else None
    except Exception as exc:  # pragma: no cover - 仅在无 GUI 的运行环境触发
        print(f"无法打开目录选择窗口：{exc}")
        return None


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    config = load_config()
    report_value = args.report_dir or config.get("report_dir") or ""
    work_value = args.work_dir or config.get("work_dir") or ""

    if not report_value:
        selected = choose_report_dir()
        if selected is None:
            raise RuntimeError(
                "尚未配置报告目录。可重新运行程序选择目录，或使用 --report-dir 指定。"
            )
        report_value = str(selected)

    report_dir = Path(report_value).expanduser().resolve()
    work_dir = (
        Path(work_value).expanduser().resolve()
        if work_value
        else default_work_dir().resolve()
    )
    return report_dir, work_dir


def assert_safe_paths(report_dir: Path, work_dir: Path) -> None:
    if not report_dir.is_dir():
        raise RuntimeError(f"报告目录不存在或不可访问：{report_dir}")
    if report_dir == work_dir:
        raise RuntimeError("报告目录和工作目录不能相同。")
    if report_dir.is_relative_to(work_dir) or work_dir.is_relative_to(report_dir):
        raise RuntimeError(
            "报告目录和工作目录不能互相包含，避免把程序输出重新扫描为原始报告。"
        )
    work_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir = work_dir / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)


def set_runtime_environment(report_dir: Path, work_dir: Path) -> None:
    patient_records_dir = work_dir / "patient_records"
    dashboard_data_dir = work_dir / "dashboard" / "data"
    os.environ["PACEMAKER_REPORT_DIR"] = str(report_dir)
    os.environ["PACEMAKER_WORK_DIR"] = str(work_dir)
    os.environ["PACEMAKER_PATIENT_RECORDS_DIR"] = str(patient_records_dir)
    os.environ["PACEMAKER_DASHBOARD_DATA_DIR"] = str(dashboard_data_dir)
    os.environ["PACEMAKER_OFFLINE_MODE"] = "1"


def acquire_run_lock(work_dir: Path):
    lock_path = work_dir / ".update.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("ascii", errors="ignore"))
        os.close(fd)
    except FileExistsError as exc:
        raise RuntimeError(
            f"检测到已有更新任务锁：{lock_path}\n"
            "请确认没有其他 PacemakerDashboard 正在运行后再重试。"
        ) from exc

    class LockHandle:
        def __enter__(self):
            return lock_path

        def __exit__(self, exc_type, exc_value, traceback):
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    return LockHandle()


def copy_dashboard_assets(work_dir: Path) -> Path:
    source_dashboard = APP_ROOT / "dashboard_ui"
    if not (source_dashboard / "index.html").exists():
        raise RuntimeError(f"运行包缺少 Dashboard 页面资源：{source_dashboard}")

    target_dashboard = work_dir / "dashboard"
    target_dashboard.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_dashboard / "index.html", target_dashboard / "index.html")
    source_assets = source_dashboard / "assets"
    target_assets = target_dashboard / "assets"
    if not source_assets.is_dir():
        raise RuntimeError(f"运行包缺少 Dashboard 静态资源：{source_assets}")
    shutil.copytree(source_assets, target_assets, dirs_exist_ok=True)
    return target_dashboard


def run_pipeline(report_dir: Path, work_dir: Path, full_rebuild: bool) -> Path:
    set_runtime_environment(report_dir, work_dir)

    # 必须在环境变量设置后再导入后端，避免 config.py 提前锁定开发目录。
    from backend import main as backend_main
    from dashboard_ui.scripts.generate_data import generate_bundle

    patient_records_dir = work_dir / "patient_records"
    processed_index = patient_records_dir / "processed_files.json"
    pipeline_warning = ""
    try:
        if full_rebuild or not processed_index.exists():
            print("正在执行首次全量处理..." if not processed_index.exists() else "正在执行全量重建...")
            backend_main.full_process()
        else:
            print("正在执行增量更新...")
            backend_main.incremental_update()
    except RuntimeError as exc:
        message = str(exc)
        recoverable_prefixes = ("发现 ", "提取未完整成功")
        if not message.startswith(recoverable_prefixes):
            raise
        pipeline_warning = message
        print("\n检测到数据质量问题；已保留既有患者输出，继续打开核查中心。")
        print(f"核查提示：{message}")

    if pipeline_warning:
        os.environ["PACEMAKER_PIPELINE_WARNING"] = pipeline_warning
    else:
        os.environ.pop("PACEMAKER_PIPELINE_WARNING", None)

    dashboard_dir = copy_dashboard_assets(work_dir)
    print("正在生成本地 Dashboard 数据包...")
    generate_bundle()
    index_path = dashboard_dir / "index.html"
    if not (dashboard_dir / "data" / "data_bundle.js").exists():
        raise RuntimeError("Dashboard 数据包生成失败，未找到 data_bundle.js。")
    return index_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pacemaker Dashboard 科室离线运行入口")
    parser.add_argument("--configure", action="store_true", help="重新选择报告目录并保存配置")
    parser.add_argument("--report-dir", help="报告目录，可为本地路径或 UNC NAS 路径")
    parser.add_argument("--work-dir", help="派生数据工作目录，不能位于报告目录内")
    parser.add_argument("--full", action="store_true", help="强制全量重建")
    parser.add_argument("--no-open", action="store_true", help="只更新数据，不自动打开浏览器")
    parser.add_argument("--version", action="version", version="PacemakerDashboard offline prototype 0.1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report_dir, work_dir = resolve_paths(args)
        if args.configure or args.report_dir or args.work_dir or not config_path().exists():
            save_config(report_dir, work_dir)
            print(f"配置已保存：{config_path()}")
        assert_safe_paths(report_dir, work_dir)
        with acquire_run_lock(work_dir):
            index_path = run_pipeline(report_dir, work_dir, args.full)
        print(f"处理完成。Dashboard：{index_path}")
        if not args.no_open:
            webbrowser.open(index_path.as_uri())
        return 0
    except Exception as exc:
        logging.exception("离线运行失败")
        print(f"\n运行失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

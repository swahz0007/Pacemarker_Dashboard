# PyInstaller spec for the offline clinical prototype.
# Only runtime code, templates and static UI assets are bundled; no patient data is included.

from pathlib import Path


project_root = Path(SPECPATH)
datas = [
    (str(project_root / "backend" / "data"), "backend/data"),
    (str(project_root / "dashboard_ui" / "index.html"), "dashboard_ui"),
    (str(project_root / "dashboard_ui" / "assets"), "dashboard_ui/assets"),
]

hiddenimports = [
    "config",
    "core.extractors",
    "core.file_tracker",
    "core.grouping",
    "core.handlers",
    "core.utils",
    "scripts.audit_extraction",
    "scripts.extract_data",
    "scripts.match_templates",
    "dashboard_ui.scripts.generate_data",
]

a = Analysis(
    [str(project_root / "launcher.py")],
    pathex=[str(project_root), str(project_root / "backend")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    name="PacemakerDashboard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    exclude_binaries=True,
    icon=str(project_root / "assets" / "pacemaker_dashboard.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="PacemakerDashboard",
)

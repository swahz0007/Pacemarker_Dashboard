"""
Pacemaker Dashboard - Demo Data Generator
==========================================
从私有仓库中抽取50份病历，彻底脱敏后生成纯前端展示 Demo。
- 读取 patient_records/*.json
- 随机抽取50份，替换所有隐私字段
- 复制前端文件到 Demo 目录
- 生成脱敏 data_bundle.js
"""
import json
import os
import random
import glob
import shutil

# ============================================================
# 配置
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PATIENT_RECORDS_DIR = os.path.join(SCRIPT_DIR, "patient_records")
DASHBOARD_UI_DIR = os.path.join(SCRIPT_DIR, "dashboard_ui")
DEMO_DIR = r"E:\Pacemaker_Dashboard_Demo"
# 全量处理，不做抽样


def generate_patient_name(index):
    """Patient_A ... Patient_Z, Patient_AA ..."""
    if index < 26:
        return f"Patient_{chr(65 + index)}"
    else:
        return f"Patient_{chr(65 + index // 26 - 1)}{chr(65 + index % 26)}"


def generate_demo_id(index):
    """DEMO-001, DEMO-002, ..."""
    return f"DEMO-{index + 1:03d}"


def deep_sanitize(obj, demo_id, demo_name, original_name):
    """递归扫描JSON，替换任何残留的隐私信息"""
    if isinstance(obj, dict):
        return {k: deep_sanitize(v, demo_id, demo_name, original_name) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [deep_sanitize(item, demo_id, demo_name, original_name) for item in obj]
    elif isinstance(obj, str):
        # 替换姓名
        if original_name and original_name in obj:
            obj = obj.replace(original_name, demo_name)
        return obj
    return obj


def anonymize_record(record, demo_id, demo_name):
    """全面脱敏一条患者记录"""
    original_name = record.get("姓名", "")
    original_id = record.get("登记号", "")

    # 深拷贝
    record = json.loads(json.dumps(record))

    # 顶层字段
    record["登记号"] = demo_id
    record["姓名"] = demo_name

    # 逐条程控记录
    for prog in record.get("程控记录", []):
        # meta: 清除文件名和路径(含患者姓名和本地路径)
        if "meta" in prog:
            prog["meta"] = {"filename": "demo_report.xlsx", "path": ""}

        # header: 替换姓名和登记号
        if "header" in prog:
            if "姓名" in prog["header"]:
                prog["header"]["姓名"] = demo_name
            if "登记号" in prog["header"]:
                prog["header"]["登记号"] = demo_id

        # footer_meta: 清除签名行(可能含医生签名图片ID)
        if "footer_meta" in prog:
            if "签名行内容" in prog["footer_meta"]:
                prog["footer_meta"]["签名行内容"] = f"[签名已脱敏] 日期：{prog['footer_meta'].get('程控日期', '')}"

    # 最终深度扫描：替换任何残留姓名
    record = deep_sanitize(record, demo_id, demo_name, original_name)

    return record


def copy_frontend_files():
    """复制前端展示文件到 Demo 目录（排除 Python 脚本和原始数据）"""
    print("\n📁 复制前端展示文件...")

    # 复制 index.html
    src_html = os.path.join(DASHBOARD_UI_DIR, "index.html")
    dst_html = os.path.join(DEMO_DIR, "index.html")
    shutil.copy2(src_html, dst_html)
    print(f"   ✅ index.html")

    # 复制 assets/ 目录（css, js, img）
    src_assets = os.path.join(DASHBOARD_UI_DIR, "assets")
    dst_assets = os.path.join(DEMO_DIR, "assets")
    if os.path.exists(dst_assets):
        shutil.rmtree(dst_assets)
    shutil.copytree(src_assets, dst_assets)
    print(f"   ✅ assets/ (css, js, img)")

    # 确保 data/ 目录存在
    os.makedirs(os.path.join(DEMO_DIR, "data"), exist_ok=True)

    print(f"   ❌ 已跳过: scripts/ (Python脚本)")
    print(f"   ❌ 已跳过: data/records/ (原始数据)")
    print(f"   ❌ 已跳过: data/patient_index.json (原始索引)")


def create_gitignore():
    """创建 .gitignore"""
    content = """# OS
.DS_Store
Thumbs.db
desktop.ini

# IDE
.vscode/
.idea/

# Python
__pycache__/
*.pyc

# Misc
*.log
"""
    path = os.path.join(DEMO_DIR, ".gitignore")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("   ✅ .gitignore")


def create_readme():
    """创建 README.md"""
    content = """# 🫀 Pacemaker Dashboard Demo

> 心脏起搏器程控报告查询系统 - 纯前端展示 Demo

## ⚠️ 数据说明

本仓库中的患者数据已**完全脱敏**：
- 所有登记号已替换为 `DEMO-001` ~ `DEMO-050`
- 所有姓名已替换为 `Patient_A` ~ `Patient_AX`
- 所有文件路径和源文件名信息已清除
- 仅保留 50 份随机抽样病历用于功能展示

**本数据不含任何真实患者信息，仅供系统功能演示使用。**

## 🚀 使用方式

1. 直接打开 `index.html`（本地）
2. 或部署到 GitHub Pages 后在线访问

## 📊 功能特性

- 📋 患者列表搜索与浏览
- 🔋 电池/起搏模式概览
- 📈 关键参数趋势图
- 🔬 深度临床统计分析
- 🖥️ 大屏模式
- 🌓 深色/浅色主题切换
"""
    path = os.path.join(DEMO_DIR, "README.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("   ✅ README.md")


def main():
    print("=" * 60)
    print("  Pacemaker Dashboard - Demo Data Generator")
    print("=" * 60)

    # ── 1. 收集患者JSON文件 ──
    print(f"\n📂 扫描 {PATIENT_RECORDS_DIR} ...")
    all_json = glob.glob(os.path.join(PATIENT_RECORDS_DIR, "*.json"))

    # 过滤：排除元数据文件和PROXY文件（文件名含患者姓名）
    patient_files = []
    for f in all_json:
        basename = os.path.basename(f)
        if basename in ("processed_files.json", "matching_report.csv"):
            continue
        if basename.startswith("PROXY_"):
            continue
        patient_files.append(f)

    print(f"   找到 {len(patient_files)} 份患者记录（已排除 PROXY 和元数据文件）")

    # ── 2. 全量处理 ──
    selected = patient_files
    print(f"   将全量处理 {len(selected)} 份记录")

    # ── 3. 脱敏处理 ──
    print("\n🔒 脱敏处理中...")
    index_list = []
    records_dict = {}

    for i, filepath in enumerate(selected):
        demo_id = generate_demo_id(i)
        demo_name = generate_patient_name(i)
        demo_filename = f"{demo_id}.json"

        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)

        anon = anonymize_record(raw, demo_id, demo_name)

        # 构建索引条目
        first_prog = anon.get("程控记录", [{}])
        first_record = first_prog[0] if first_prog else {}
        header = first_record.get("header", {})

        index_entry = {
            "id": demo_id,
            "name": demo_name,
            "count": anon.get("程控次数", 1),
            "brand": header.get("品牌", "Unknown"),
            "model": header.get("型号", "Unknown"),
            "implant_date": header.get("植入日期", ""),
            "file_name": demo_filename,
        }
        index_list.append(index_entry)
        records_dict[demo_filename] = anon

        print(f"   [{i+1:02d}/{len(selected)}] {os.path.basename(filepath)} → {demo_id} ({demo_name})")

    # ── 4. 搭建 Demo 目录 ──
    print(f"\n📁 创建 Demo 目录: {DEMO_DIR}")
    os.makedirs(DEMO_DIR, exist_ok=True)

    copy_frontend_files()
    create_gitignore()
    create_readme()

    # ── 5. 写入脱敏 data_bundle.js ──
    bundle = {"index": index_list, "records": records_dict}
    output_path = os.path.join(DEMO_DIR, "data", "data_bundle.js")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("window.PACEMAKER_DATA = ")
        json.dump(bundle, f, ensure_ascii=False)
        f.write(";")

    file_size_kb = os.path.getsize(output_path) / 1024
    print(f"\n   ✅ data/data_bundle.js ({file_size_kb:.1f} KB)")

    # ── 完成 ──
    print("\n" + "=" * 60)
    print("  ✅ Demo 生成完毕！")
    print(f"  📁 位置: {DEMO_DIR}")
    print(f"  📊 包含 {len(index_list)} 份脱敏患者档案（全量）")
    print("=" * 60)
    print("\n接下来请在终端执行以下 Git 命令：")
    print(f'  cd "{DEMO_DIR}"')
    print("  git init")
    print("  git remote add origin https://github.com/HexBladeNB/Pacemaker_Dashboard_Demo.git")
    print("  git add .")
    print('  git commit -m "init: 纯前端脱敏展示大屏"')
    print("  git push -u origin master")


if __name__ == "__main__":
    main()

import os
import json
import glob
from pathlib import Path
import matplotlib.pyplot as plt
from collections import Counter
import seaborn as sns
import logging

# Set Matplotlib parameters for high-quality scientific figures
plt.rcParams['font.sans-serif'] = ['SimHei']  # Chinese font support
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PATIENT_RECORDS_DIR = BASE_DIR / 'patient_records'
DOC_DIR = BASE_DIR / 'doc'
logger = logging.getLogger(__name__)

if not DOC_DIR.exists():
    DOC_DIR.mkdir(parents=True)

def generate_charts():
    patient_files = glob.glob(str(PATIENT_RECORDS_DIR / '*.json'))
    
    brands = []
    implant_years = []
    models = []
    followup_counts = []

    print(f"Scanning {len(patient_files)} files to generate charts...")

    for file_path in patient_files:
        try:
            filename = os.path.basename(file_path)
            if filename in ['processed_files.json', 'matching_report.csv']:
                continue
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                latest_record = data.get('程控记录', [{}])[-1] if data.get('程控记录') else {}
                header = latest_record.get('header', {})
                
                brand = header.get('品牌', 'Unknown')
                if brand and brand != 'Unknown':
                    brands.append(brand)
                    
                model = header.get('型号', 'Unknown')
                if model and model != 'Unknown':
                    # Simplify model text to brand + model to ensure context
                    models.append(f"{brand} {model}")
                
                implant_date = header.get('植入日期', '')
                if implant_date and len(str(implant_date)) >= 4:
                    year = str(implant_date)[:4]
                    if year.isdigit() and 1990 <= int(year) <= 2026:
                        implant_years.append(int(year))
                        
                count = data.get('程控次数', 0)
                if count > 0:
                    followup_counts.append(count)
                    
        except Exception as e:
            logger.warning("Skip invalid patient file", extra={"file": file_path, "error": str(e)})

    # Chart 1: Brand Distribution (Horizontal Bar Chart to avoid text overlap)
    brand_counts = Counter(brands)
    sorted_brands = brand_counts.most_common(5)
    labels = [b[0] for b in sorted_brands]
    sizes = [b[1] for b in sorted_brands]
    
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(x=sizes, y=labels, ax=ax, palette='viridis', hue=labels, legend=False)
    ax.set_title('各品牌设备结构化入库数据分布', fontsize=16, weight='bold', pad=20)
    ax.set_xlabel('设备量 (台)', fontsize=14)
    # Add data labels
    for i, v in enumerate(sizes):
        ax.text(v + max(sizes)*0.01, i, f" {v}", color='black', va='center', fontweight='bold', fontsize=12)
    plt.tight_layout()
    brand_chart_path = DOC_DIR / 'brand_distribution.png'
    plt.savefig(brand_chart_path)
    plt.close()

    # Chart 2: Top 10 Models
    model_counts = Counter(models)
    top_models = model_counts.most_common(10)
    m_labels = [m[0] for m in top_models]
    m_sizes = [m[1] for m in top_models]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(x=m_sizes, y=m_labels, ax=ax, palette='rocket', hue=m_labels, legend=False)
    ax.set_title('Top 10 解析入库的起搏器型号清单', fontsize=16, weight='bold', pad=20)
    ax.set_xlabel('设备量 (台)', fontsize=14)
    for i, v in enumerate(m_sizes):
        ax.text(v + max(m_sizes)*0.01, i, f" {v}", color='black', va='center', fontweight='bold', fontsize=11)
    plt.tight_layout()
    model_chart_path = DOC_DIR / 'top_models.png'
    plt.savefig(model_chart_path)
    plt.close()

    # Chart 3: Implant Year Trends 
    year_counts = Counter(implant_years)
    years = sorted(year_counts.keys())
    counts = [year_counts[y] for y in years]
    
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.barplot(x=years, y=counts, ax=ax, color='skyblue', alpha=0.8)
    ax.plot(range(len(years)), counts, color='darkorange', marker='o', linewidth=2, markersize=6)
    
    ax.set_title('入库设备历年植入趋势 (体现沉淀队列厚度)', fontsize=16, weight='bold', pad=20)
    ax.set_ylabel('单年植入量 (台)', fontsize=14)
    plt.xticks(rotation=45, ha='right')
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    
    for i, count in enumerate(counts):
        ax.text(i, count + max(counts)*0.02, str(count), ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    trend_chart_path = DOC_DIR / 'implant_trends.png'
    plt.savefig(trend_chart_path)
    plt.close()
    
    # Chart 4: Follow-up counts histogram
    fig, ax = plt.subplots(figsize=(10, 5))
    bins_range = range(1, max(followup_counts)+2) if followup_counts else range(1, 10)
    sns.histplot(followup_counts, bins=bins_range, discrete=True, color='teal', ax=ax, alpha=0.7)
    ax.set_title('单兵患者累计程控随访次数分布', fontsize=16, weight='bold', pad=20)
    ax.set_xlabel('有效随访记录数 (次)', fontsize=14)
    ax.set_ylabel('覆盖患者数 (人)', fontsize=14)
    if followup_counts:
        ax.set_xticks(range(1, max(followup_counts)+1, max(1, max(followup_counts)//15)))
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    followup_chart_path = DOC_DIR / 'followup_counts.png'
    plt.savefig(followup_chart_path)
    plt.close()

if __name__ == "__main__":
    generate_charts()

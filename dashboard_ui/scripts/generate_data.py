
import os
import json
import glob
from pathlib import Path

# Paths
# .../dashboard_ui/scripts/generate_data.py -> .../Pacemarker_Dashboard
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PATIENT_RECORDS_DIR = BASE_DIR / 'patient_records'
OUTPUT_DIR = BASE_DIR / 'dashboard_ui' / 'data'
OUTPUT_FILE = OUTPUT_DIR / 'data_bundle.js'

def generate_bundle():
    print(f"Base Dir: {BASE_DIR}")
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True)

    patient_files = glob.glob(str(PATIENT_RECORDS_DIR / '*.json'))
    
    index_data = []
    records_map = {}

    print(f"Scanning {len(patient_files)} files in {PATIENT_RECORDS_DIR}...")

    for file_path in patient_files:
        try:
            filename = os.path.basename(file_path)
            if filename == 'processed_files.json' or filename == 'matching_report.csv':
                continue
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Store full record
                records_map[filename] = data
                
                # Extract Index Info
                registration_id = data.get('登记号', 'Unknown')
                name = data.get('姓名', 'Unknown')
                record_count = data.get('程控次数', 0)
                
                latest_record = {}
                if data.get('程控记录'):
                    latest_record = data['程控记录'][-1]
                
                header = latest_record.get('header', {})
                brand = header.get('品牌', 'Unknown')
                model = header.get('型号', 'Unknown')
                implant_date = header.get('植入日期', '')
                
                index_data.append({
                    'id': str(registration_id), # Ensure string
                    'name': name,
                    'count': record_count,
                    'brand': brand,
                    'model': model,
                    'implant_date': implant_date,
                    'file_name': filename
                })
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    # Sort Index
    index_data.sort(key=lambda x: x['id'])

    # Create JS Bundle Content
    # We assign to a global variable window.PACEMAKER_DATA
    bundle_content = {
        "index": index_data,
        "records": records_map
    }
    
    js_content = f"window.PACEMAKER_DATA = {json.dumps(bundle_content, ensure_ascii=False)};"

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(js_content)

    print(f"Successfully generated data bundle with {len(index_data)} patients at: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_bundle()

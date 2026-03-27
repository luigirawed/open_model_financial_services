import os
import json
import pandas as pd

OUTPUT_DIR = 'output'
PREBUILT_DIR = 'dist'

REQUIRED_FILES = [
    'boe_base_rate.csv',
    'ons_cpi_inflation.csv',
    'boe_IUMTLMV.csv',
    'uk_hpi_data.csv',
    'ons_earn05_regional_earnings.csv',
    'ons_gdhi_regional.csv',
    'imd_2019_regional.csv',
    'imd_2025_regional.csv',
    'ons_ashe_occupation_raw.csv',
    'uk_lad_centroids.csv',
    'boe_gilt_yields_raw.csv',
]

def csv_to_jsonl(csv_path, jsonl_path, filters=None, preprocessor=None):
    df = pd.read_csv(csv_path, low_memory=False)
    
    if preprocessor:
        df = preprocessor(df)
    
    if filters:
        for col, condition in filters.items():
            if col in df.columns:
                df = df[condition(df[col])]
    
    df = df.where(pd.notnull, None)
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for record in df.to_dict(orient='records'):
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    return len(df)

def preprocess_cpi(df):
    if 'CPI ANNUAL RATE 00: ALL ITEMS 2015=100' in df.columns:
        df = df.rename(columns={'Title': 'Date', 'CPI ANNUAL RATE 00: ALL ITEMS 2015=100': 'CPI_Rate'})
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.strftime('%Y-%m-%d')
    return df.dropna(subset=['Date'])

def main():
    os.makedirs(PREBUILT_DIR, exist_ok=True)
    
    print("Converting CSV files to JSONL format...")
    total_records = 0
    
    for csv_file in REQUIRED_FILES:
        csv_path = os.path.join(OUTPUT_DIR, csv_file)
        jsonl_file = csv_file.replace('.csv', '.jsonl')
        jsonl_path = os.path.join(PREBUILT_DIR, jsonl_file)
        
        filters = None
        preprocessor = None
        
        if csv_file == 'uk_hpi_data.csv':
            filters = {'Date': lambda d: pd.to_datetime(d, format='%d/%m/%Y', errors='coerce') >= '2019-01-01'}
        elif csv_file == 'ons_cpi_inflation.csv':
            preprocessor = preprocess_cpi
        
        if os.path.exists(csv_path):
            count = csv_to_jsonl(csv_path, jsonl_path, filters, preprocessor)
            print(f"  {csv_file} -> {jsonl_file} ({count} records)")
            total_records += count
        else:
            print(f"  [SKIP] {csv_file} not found")
    
    print(f"\nTotal records: {total_records}")
    
    total_size = sum(os.path.getsize(os.path.join(PREBUILT_DIR, f)) 
                     for f in os.listdir(PREBUILT_DIR))
    print(f"Total prebuilt size: {total_size / 1024 / 1024:.2f} MB")
    print(f"\nPrebuilt files saved to {PREBUILT_DIR}/")

if __name__ == '__main__':
    main()
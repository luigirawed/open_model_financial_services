"""
Stage 1b: Retry GDHI and ASHE downloads with verified URLs
"""
import pandas as pd
import requests
import os
import io
import time
import zipfile

OUTPUT_DIR = 'output'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def download_file(url, local_path, delay=3):
    time.sleep(delay)
    print(f"  Downloading: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    with open(local_path, 'wb') as f:
        f.write(resp.content)
    size_kb = len(resp.content) / 1024
    print(f"  Saved: {local_path} ({size_kb:.1f} KB)")
    return resp.content

# =============================================================================
# 1. ONS GDHI — confirmed URL from browser
# =============================================================================
print("=" * 60)
print("1. ONS GDHI — Regional Disposable Income (verified URL)")
print("=" * 60)

gdhi_url = "https://www.ons.gov.uk/file?uri=/economy/regionalaccounts/grossdisposablehouseholdincome/datasets/regionalgrossdisposablehouseholdincomeallitlregions/1997to2023/regionalgrossdisposablehouseholdincomeallitlregions2023.xlsx"

try:
    content = download_file(gdhi_url, os.path.join(OUTPUT_DIR, 'ons_gdhi_raw.xlsx'))
    
    xls = pd.ExcelFile(io.BytesIO(content))
    print(f"  Sheets: {xls.sheet_names}")
    
    # Look for ITL1 per head sheet
    target_sheet = None
    for s in xls.sheet_names:
        sl = s.lower()
        if 'itl1' in sl and ('per head' in sl or 'perhead' in sl):
            target_sheet = s
            break
    if target_sheet is None:
        for s in xls.sheet_names:
            if 'itl1' in s.lower():
                target_sheet = s
                break
    if target_sheet is None:
        target_sheet = xls.sheet_names[0]
    
    print(f"  Using sheet: '{target_sheet}'")
    df_gdhi = pd.read_excel(xls, sheet_name=target_sheet, header=None)
    df_gdhi.to_csv(os.path.join(OUTPUT_DIR, 'ons_gdhi_raw.csv'), index=False)
    print(f"  Rows: {len(df_gdhi)}, Cols: {len(df_gdhi.columns)}")
    for i in range(min(6, len(df_gdhi))):
        print(f"  Row {i}: {df_gdhi.iloc[i].tolist()[:12]}")
    
    print("  [OK] GDHI downloaded successfully.")
except Exception as e:
    print(f"  [FAIL] GDHI: {e}")

# =============================================================================
# 2. ONS ASHE Table 14 — ZIP archive (verified URL)
# =============================================================================
print("\n" + "=" * 60)
print("2. ONS ASHE Table 14 — Occupation Earnings (ZIP)")
print("=" * 60)

ashe_url = "https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/occupation4digitsoc2010ashetable14/2025provisional/ashetable142025provisional.zip"

try:
    content = download_file(ashe_url, os.path.join(OUTPUT_DIR, 'ons_ashe_table14.zip'), delay=5)
    
    # Extract and inspect the ZIP
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        names = z.namelist()
        print(f"  ZIP contents ({len(names)} files):")
        for n in names:
            info = z.getinfo(n)
            print(f"    {n} ({info.file_size / 1024:.1f} KB)")
        
        # Find the annual pay XLSX (typically Table 14.5a or similar)
        target_file = None
        for n in names:
            nl = n.lower()
            if 'annual' in nl and '.xlsx' in nl:
                target_file = n
                break
        if target_file is None:
            # Just grab the first xlsx
            for n in names:
                if n.endswith('.xlsx') and 'note' not in n.lower():
                    target_file = n
                    break
        
        if target_file:
            print(f"\n  Extracting: '{target_file}'")
            with z.open(target_file) as f:
                xlsx_bytes = f.read()
            
            xls = pd.ExcelFile(io.BytesIO(xlsx_bytes))
            print(f"  Sub-sheets: {xls.sheet_names}")
            
            # Use the 'All' tab if available
            target_sheet = xls.sheet_names[0]
            for s in xls.sheet_names:
                if 'all' in s.lower():
                    target_sheet = s
                    break
            
            print(f"  Using sheet: '{target_sheet}'")
            df_ashe = pd.read_excel(xls, sheet_name=target_sheet, header=None)
            df_ashe.to_csv(os.path.join(OUTPUT_DIR, 'ons_ashe_occupation_raw.csv'), index=False)
            print(f"  Rows: {len(df_ashe)}, Cols: {len(df_ashe.columns)}")
            for i in range(min(6, len(df_ashe))):
                print(f"  Row {i}: {df_ashe.iloc[i].tolist()[:8]}")
            
            print("  [OK] ASHE downloaded successfully.")
        else:
            print("  [WARN] No suitable XLSX found in ZIP.")
            
except Exception as e:
    print(f"  [FAIL] ASHE: {e}")

# =============================================================================
# 3. Also process EARN05 raw data (already downloaded)
# =============================================================================
print("\n" + "=" * 60)
print("3. Processing EARN05 raw data (already downloaded)")
print("=" * 60)

earn_path = os.path.join(OUTPUT_DIR, 'ons_earn05_raw.xls')
if os.path.exists(earn_path):
    xls = pd.ExcelFile(earn_path)
    print(f"  Sheets: {xls.sheet_names}")
    for s in xls.sheet_names:
        print(f"    - '{s}'")
    
    # Read first sheet that looks data-like
    for s in xls.sheet_names:
        if 'note' not in s.lower() and 'content' not in s.lower():
            df = pd.read_excel(xls, sheet_name=s, header=None)
            print(f"\n  Sheet '{s}': {len(df)} rows x {len(df.columns)} cols")
            for i in range(min(8, len(df))):
                print(f"  Row {i}: {df.iloc[i].tolist()[:10]}")
            break
else:
    print("  EARN05 raw file not found.")

# =============================================================================
# Summary
# =============================================================================
print("\n" + "=" * 60)
print("FINAL DOWNLOAD SUMMARY")
print("=" * 60)
for f in ['ons_earn05_raw.xls', 'ons_earn05_raw.csv', 
          'imd_2019_lad_raw.xlsx', 'imd_2019_lad_raw.csv', 
          'ons_gdhi_raw.xlsx', 'ons_gdhi_raw.csv',
          'ons_ashe_table14.zip', 'ons_ashe_occupation_raw.csv']:
    path = os.path.join(OUTPUT_DIR, f)
    if os.path.exists(path):
        size = os.path.getsize(path) / 1024
        print(f"  [EXISTS] {f} ({size:.1f} KB)")
    else:
        print(f"  [MISSING] {f}")

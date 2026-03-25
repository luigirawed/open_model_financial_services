"""
Stage 1: Data Acquisition — Earnings, GDHI, and Deprivation
Downloads and processes ONS EARN05, ASHE, GDHI, and IMD datasets.
Updated with verified download URLs.
"""
import pandas as pd
import requests
import os
import io
import time

OUTPUT_DIR = 'output'
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def download_file(url, local_path, delay=2):
    """Download a file with retry and delay to avoid rate limiting."""
    time.sleep(delay)
    print(f"  Downloading: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
    resp.raise_for_status()
    with open(local_path, 'wb') as f:
        f.write(resp.content)
    size_kb = len(resp.content) / 1024
    print(f"  Saved: {local_path} ({size_kb:.1f} KB)")
    return resp.content

# =============================================================================
# 1. ONS EARN05 — Regional Gross Weekly Earnings
# =============================================================================
print("=" * 60)
print("1. ONS EARN05 — Regional Gross Weekly Earnings")
print("=" * 60)

earn05_url = "https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/grossweeklyearningsoffulltimeemployeesbyregionearn05/current/earn05feb2026.xls"

try:
    content = download_file(earn05_url, os.path.join(OUTPUT_DIR, 'ons_earn05_raw.xls'))
    
    xls = pd.ExcelFile(io.BytesIO(content))
    print(f"  Sheets: {xls.sheet_names}")
    
    # Find the median weekly pay sheet
    target_sheet = None
    for s in xls.sheet_names:
        sl = s.lower()
        if 'median' in sl or ('weekly' in sl and 'gross' in sl):
            target_sheet = s
            break
    if target_sheet is None:
        # Try first non-notes sheet
        for s in xls.sheet_names:
            if 'note' not in s.lower() and 'content' not in s.lower():
                target_sheet = s
                break
    
    print(f"  Using sheet: '{target_sheet}'")
    df_earn = pd.read_excel(xls, sheet_name=target_sheet, header=None)
    df_earn.to_csv(os.path.join(OUTPUT_DIR, 'ons_earn05_raw.csv'), index=False)
    print(f"  Rows: {len(df_earn)}, Cols: {len(df_earn.columns)}")
    for i in range(min(8, len(df_earn))):
        print(f"  Row {i}: {df_earn.iloc[i].tolist()[:8]}")
    
    print("  [OK] EARN05 downloaded successfully.")
except Exception as e:
    print(f"  [FAIL] EARN05: {e}")

# =============================================================================
# 2. IMD 2019 — Index of Multiple Deprivation (England)
# =============================================================================
print("\n" + "=" * 60)
print("2. IMD 2019 — Index of Multiple Deprivation")
print("=" * 60)

# File 10: Local Authority District Summaries (already aggregated!)
imd_url = "https://assets.publishing.service.gov.uk/media/5d8b3cfbe5274a08be69aa91/File_10_-_IoD2019_Local_Authority_District_Summaries__lower-tier__.xlsx"

try:
    content = download_file(imd_url, os.path.join(OUTPUT_DIR, 'imd_2019_lad_raw.xlsx'))
    
    xls = pd.ExcelFile(io.BytesIO(content))
    print(f"  Sheets: {xls.sheet_names}")
    
    # Use the IMD summary sheet
    target_sheet = xls.sheet_names[0]
    for s in xls.sheet_names:
        if 'imd' in s.lower():
            target_sheet = s
            break
    
    print(f"  Using sheet: '{target_sheet}'")
    df_imd = pd.read_excel(xls, sheet_name=target_sheet, header=0)
    df_imd.to_csv(os.path.join(OUTPUT_DIR, 'imd_2019_lad_raw.csv'), index=False)
    print(f"  Rows: {len(df_imd)}, Cols: {len(df_imd.columns)}")
    print(f"  Columns: {list(df_imd.columns)[:10]}")
    print(f"  First 3 rows:\n{df_imd.head(3)}")
    
    print("  [OK] IMD 2019 downloaded successfully.")
except Exception as e:
    print(f"  [FAIL] IMD 2019: {e}")

# =============================================================================
# 3. ONS GDHI — Gross Disposable Household Income
# =============================================================================
print("\n" + "=" * 60)
print("3. ONS GDHI — Regional Disposable Income")
print("=" * 60)

# Try multiple possible URL patterns for the GDHI ITL regions data
gdhi_urls = [
    "https://www.ons.gov.uk/file?uri=/economy/regionalaccounts/grossdisposablehouseholdincome/datasets/regionalgrossdisposablehouseholdincomeallitlregions/1997to2023revised/regionalgrossdisposablehouseholdincomegdhiallitlregions.xlsx",
    "https://www.ons.gov.uk/file?uri=/economy/regionalaccounts/grossdisposablehouseholdincome/datasets/regionalgrossdisposablehouseholdincomeallitlregions/1997to2023/gdhiallitlregions.xlsx",
    "https://www.ons.gov.uk/file?uri=/economy/regionalaccounts/grossdisposablehouseholdincome/datasets/regionalgrossdisposablehouseholdincomeallitlregions/current/regionalgrossdisposablehouseholdincomegdhiallitlregions.xlsx",
]

gdhi_ok = False
for url in gdhi_urls:
    try:
        content = download_file(url, os.path.join(OUTPUT_DIR, 'ons_gdhi_raw.xlsx'))
        
        xls = pd.ExcelFile(io.BytesIO(content))
        print(f"  Sheets: {xls.sheet_names}")
        
        target_sheet = None
        for s in xls.sheet_names:
            sl = s.lower()
            if 'itl1' in sl and 'per' in sl:
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
        for i in range(min(5, len(df_gdhi))):
            print(f"  Row {i}: {df_gdhi.iloc[i].tolist()[:10]}")
        
        print("  [OK] GDHI downloaded successfully.")
        gdhi_ok = True
        break
    except Exception as e:
        print(f"  [SKIP] {url}: {e}")

if not gdhi_ok:
    print("  [FAIL] All GDHI URLs failed. Will need manual download.")

# =============================================================================
# 4. ONS ASHE — Occupation Earnings
# =============================================================================
print("\n" + "=" * 60)
print("4. ONS ASHE — Occupation Earnings")
print("=" * 60)

# ASHE Table 14 - try multiple edition patterns
ashe_urls = [
    "https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/occupation4digitsoc2010702socialoccupationclassification/revised2024/ashetable142024revised.xlsx",
    "https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/occupation4digitsoc2010702socialoccupationclassification/current/table14.xlsx",
    # ASHE Table 2 (2-digit SOC) as fallback
    "https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/occupation2digitsoc2010ashetable2/revised2024/ashetable22024revised.xlsx",
    "https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/occupation2digitsoc2010ashetable2/current/table2.xlsx",
]

ashe_ok = False
for url in ashe_urls:
    try:
        content = download_file(url, os.path.join(OUTPUT_DIR, 'ons_ashe_occupation_raw.xlsx'))
        
        xls = pd.ExcelFile(io.BytesIO(content))
        print(f"  Sheets: {xls.sheet_names}")
        
        target_sheet = xls.sheet_names[0]
        for s in xls.sheet_names:
            sl = s.lower()
            if ('annual' in sl or 'weekly' in sl) and 'note' not in sl:
                target_sheet = s
                break
        
        print(f"  Using sheet: '{target_sheet}'")
        df_ashe = pd.read_excel(xls, sheet_name=target_sheet, header=None)
        df_ashe.to_csv(os.path.join(OUTPUT_DIR, 'ons_ashe_occupation_raw.csv'), index=False)
        print(f"  Rows: {len(df_ashe)}, Cols: {len(df_ashe.columns)}")
        for i in range(min(6, len(df_ashe))):
            print(f"  Row {i}: {df_ashe.iloc[i].tolist()[:6]}")
        
        print("  [OK] ASHE downloaded successfully.")
        ashe_ok = True
        break
    except Exception as e:
        print(f"  [SKIP] {url}: {e}")

if not ashe_ok:
    print("  [FAIL] All ASHE URLs failed. Will need manual download.")

# =============================================================================
# Summary
# =============================================================================
print("\n" + "=" * 60)
print("DOWNLOAD SUMMARY")
print("=" * 60)
for f in ['ons_earn05_raw.xls', 'ons_earn05_raw.csv', 'imd_2019_lad_raw.xlsx', 
          'imd_2019_lad_raw.csv', 'ons_gdhi_raw.xlsx', 'ons_gdhi_raw.csv',
          'ons_ashe_occupation_raw.xlsx', 'ons_ashe_occupation_raw.csv']:
    path = os.path.join(OUTPUT_DIR, f)
    if os.path.exists(path):
        size = os.path.getsize(path) / 1024
        print(f"  [EXISTS] {f} ({size:.1f} KB)")
    else:
        print(f"  [MISSING] {f}")

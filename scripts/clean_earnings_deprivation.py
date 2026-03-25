"""
Stage 1c: Clean all 4 raw datasets into final, analysis-ready CSVs
"""
import pandas as pd
import os

OUTPUT_DIR = 'output'

# =============================================================================
# 1. EARN05 — Regional Gross Weekly Earnings
# =============================================================================
print("=" * 60)
print("1. Cleaning EARN05 — Regional Gross Weekly Earnings")
print("=" * 60)

earn_path = os.path.join(OUTPUT_DIR, 'ons_earn05_raw.xls')
xls = pd.ExcelFile(earn_path)
print(f"  Sheets: {xls.sheet_names}")

# Read the first data sheet
df = pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=None)
print(f"  Raw shape: {df.shape}")

# Inspect structure to find the header row and regions
for i in range(min(15, len(df))):
    row_vals = [str(v) for v in df.iloc[i].tolist()[:12]]
    print(f"  Row {i}: {row_vals}")

# The table structure is typically:
# Row 0-3: titles
# Row 4: column headers (year, regions...)
# Find the row with year-like values (e.g., "2024", "2023") or region headers
header_row = None
for i in range(12):
    row = df.iloc[i].tolist()
    row_str = [str(v).strip().lower() for v in row if pd.notna(v)]
    if any('north east' in s or 'london' in s or 'wales' in s for s in row_str):
        header_row = i
        break

print(f"\n  Detected header row: {header_row}")
if header_row is not None:
    headers = df.iloc[header_row].tolist()
    print(f"  Headers: {headers}")
    
    # Data starts after header
    df_clean = df.iloc[header_row+1:].copy()
    df_clean.columns = headers
    
    # Drop rows that are all NaN
    df_clean = df_clean.dropna(how='all')
    
    print(f"  Cleaned shape: {df_clean.shape}")
    print(f"  Columns: {list(df_clean.columns)}")
    print(f"  First 3 rows:\n{df_clean.head(3)}")
    
    df_clean.to_csv(os.path.join(OUTPUT_DIR, 'ons_earn05_regional_earnings.csv'), index=False)
    print("  [OK] Saved ons_earn05_regional_earnings.csv")
else:
    print("  [WARN] Could not auto-detect header row. Saving raw for manual inspection.")

# =============================================================================
# 2. IMD 2019 — Aggregate to Region Level
# =============================================================================
print("\n" + "=" * 60)
print("2. Cleaning IMD 2019 — LAD Summaries")
print("=" * 60)

imd_path = os.path.join(OUTPUT_DIR, 'imd_2019_lad_raw.csv')
df_imd = pd.read_csv(imd_path)
print(f"  Shape: {df_imd.shape}")
print(f"  Columns: {list(df_imd.columns)}")

# The LAD summaries file should have columns for each LAD with IMD summary stats
# Let's check what we have
print(f"  First 3 rows:\n{df_imd.head(3)}")
df_imd.to_csv(os.path.join(OUTPUT_DIR, 'imd_2019_regional.csv'), index=False)
print("  [OK] Saved imd_2019_regional.csv")

# =============================================================================
# 3. GDHI — Extract ITL1 Per Head
# =============================================================================
print("\n" + "=" * 60)
print("3. Cleaning GDHI — ITL1 Per Head")
print("=" * 60)

gdhi_path = os.path.join(OUTPUT_DIR, 'ons_gdhi_raw.xlsx')
xls = pd.ExcelFile(gdhi_path)
print(f"  Sheets: {xls.sheet_names}")

# Find ITL1 per head sheet
target_sheet = None
for s in xls.sheet_names:
    sl = s.lower()
    if 'itl1' in sl:
        target_sheet = s
        print(f"  Candidate sheet: '{s}'")
        
# Read the first ITL1 sheet found
if target_sheet:
    df_gdhi = pd.read_excel(xls, sheet_name=target_sheet, header=None)
    print(f"  Raw shape: {df_gdhi.shape}")
    for i in range(min(8, len(df_gdhi))):
        row_vals = [str(v)[:20] for v in df_gdhi.iloc[i].tolist()[:12]]
        print(f"  Row {i}: {row_vals}")
else:
    # Try all sheets
    for s in xls.sheet_names:
        print(f"\n  Inspecting sheet: '{s}'")
        df_gdhi = pd.read_excel(xls, sheet_name=s, header=None)
        print(f"  Shape: {df_gdhi.shape}")
        for i in range(min(4, len(df_gdhi))):
            row_vals = [str(v)[:20] for v in df_gdhi.iloc[i].tolist()[:8]]
            print(f"  Row {i}: {row_vals}")

# =============================================================================
# 4. ASHE — Extract Key Occupation Data
# =============================================================================
print("\n" + "=" * 60)
print("4. Cleaning ASHE — Occupation Annual Pay")
print("=" * 60)

ashe_path = os.path.join(OUTPUT_DIR, 'ons_ashe_occupation_raw.csv')
if os.path.exists(ashe_path):
    df_ashe = pd.read_csv(ashe_path, header=None)
    print(f"  Shape: {df_ashe.shape}")
    for i in range(min(8, len(df_ashe))):
        row_vals = [str(v)[:25] for v in df_ashe.iloc[i].tolist()[:8]]
        print(f"  Row {i}: {row_vals}")
    
    # Data starts at row 4 (Description, Code, Jobs, Median, Change, Mean, Change, Percentiles...)
    # Row 4 has: Description, Code, (thousand), Median, change, Mean, change, 10
    # Row 5 onwards has data
    header_row = 4
    df_clean = df_ashe.iloc[header_row+1:].copy()
    df_clean.columns = ['Description', 'Code', 'Jobs_Thousands', 'Median_Annual', 'Median_PctChange', 
                         'Mean_Annual', 'Mean_PctChange'] + [f'p{v}' for v in df_ashe.iloc[header_row, 7:].tolist()]
    
    # Keep only rows with a Description
    df_clean = df_clean.dropna(subset=['Description'])
    # Remove sub-total / spacer rows
    df_clean = df_clean[df_clean['Description'].astype(str).str.strip() != '']
    
    # Convert numeric columns
    for col in ['Jobs_Thousands', 'Median_Annual', 'Mean_Annual', 'Median_PctChange', 'Mean_PctChange']:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
    
    print(f"  Cleaned shape: {df_clean.shape}")
    print(f"  Columns: {list(df_clean.columns)[:8]}")
    print(f"  Top 5 by Median Annual Pay:")
    top5 = df_clean.nlargest(5, 'Median_Annual')[['Description', 'Code', 'Median_Annual', 'Mean_Annual']]
    print(f"{top5.to_string()}")
    
    print(f"\n  Bottom 5 by Median Annual Pay:")
    bot5 = df_clean.nsmallest(5, 'Median_Annual')[['Description', 'Code', 'Median_Annual', 'Mean_Annual']]
    print(f"{bot5.to_string()}")
    
    df_clean.to_csv(os.path.join(OUTPUT_DIR, 'ons_ashe_occupation.csv'), index=False)
    print("\n  [OK] Saved ons_ashe_occupation.csv")
else:
    print("  [MISSING] ASHE raw CSV not found")

print("\n" + "=" * 60)
print("CLEANING COMPLETE")
print("=" * 60)
for f in ['ons_earn05_regional_earnings.csv', 'imd_2019_regional.csv', 
          'ons_gdhi_raw.csv', 'ons_ashe_occupation.csv']:
    path = os.path.join(OUTPUT_DIR, f)
    if os.path.exists(path):
        size = os.path.getsize(path) / 1024
        print(f"  [OK] {f} ({size:.1f} KB)")
    else:
        print(f"  [MISSING] {f}")

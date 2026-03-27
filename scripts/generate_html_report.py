import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import json
import os

PREBUILT_DIR = 'dist'
OUTPUT_DIR = 'output'

def load_data_jsonl(csv_name, jsonl_name=None, numeric_cols=None, **csv_kwargs):
    if jsonl_name is None:
        jsonl_name = csv_name.replace('.csv', '.jsonl')
    jsonl_path = os.path.join(PREBUILT_DIR, jsonl_name)
    csv_path = os.path.join(OUTPUT_DIR, csv_name)
    
    if os.path.exists(jsonl_path):
        records = []
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                records.append(json.loads(line))
        df = pd.DataFrame(records)
        if numeric_cols:
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    elif os.path.exists(csv_path):
        return pd.read_csv(csv_path, **csv_kwargs)
    else:
        raise FileNotFoundError(f"Data file not found: {csv_path} or {jsonl_path}")

# 1. Load Data
df_boe = load_data_jsonl('boe_base_rate.csv')
df_boe['Date'] = pd.to_datetime(df_boe['DATE'])
df_boe = df_boe.set_index('Date').resample('ME').last()

df_inf = load_data_jsonl('ons_cpi_inflation.csv', numeric_cols=['CPI_Rate'])
df_inf['Date'] = pd.to_datetime(df_inf['Date'], errors='coerce')
df_inf = df_inf.dropna(subset=['Date'])
df_inf = df_inf.set_index('Date').resample('ME').last()

df_mort2 = load_data_jsonl('boe_IUMTLMV.csv')
df_mort2['Date'] = pd.to_datetime(df_mort2['DATE'])
df_mort2 = df_mort2.set_index('Date').resample('ME').last()

df_hpi = load_data_jsonl('uk_hpi_data.csv', low_memory=False)
df_hpi['Date'] = pd.to_datetime(df_hpi['Date'], format='%d/%m/%Y')
df_hpi_agg = df_hpi.groupby('Date')[['AveragePrice', '12m%Change']].mean().resample('ME').last()

# New Socioeconomic Data
df_earn = load_data_jsonl('ons_earn05_regional_earnings.csv')
df_gdhi = load_data_jsonl('ons_gdhi_regional.csv')
df_imd = load_data_jsonl('imd_2019_regional.csv')
df_ashe = load_data_jsonl('ons_ashe_occupation_raw.csv')

# Master DF (2019+)
df = pd.concat([
    df_boe['IUDBEDR'].rename('BaseRate'),
    df_inf['CPI_Rate'],
    df_mort2['IUMTLMV'].rename('Mortgage2Y'),
    df_hpi_agg['AveragePrice'],
    df_hpi_agg['12m%Change'].rename('HPI_growth')
], axis=1)
df = df['2019-01-01':].ffill()

# 1b. Process Affordability Ratios
# Map Earnings quarters to monthly HPI dates
target_regions = ['London', 'South East', 'North East', 'Scotland', 'Wales']
# Map EARN05 names to HPI names if different
earn_map = {'London': 'London', 'South East': 'South East', 'North East': 'North East', 
            'Scotland': 'Scotland', 'Wales': 'Wales'}

# Create a monthly earnings dataframe
earn_long = df_earn.melt(id_vars='Period', var_name='Region', value_name='WeeklyPay')
# Convert 'Jan-Mar 2024' to '2024-03-31'
def parse_period(p):
    try:
        parts = str(p).split(' ')
        if len(parts) != 2: return pd.NaT
        q, year = parts[0], parts[1]
        m = {'Jan-Mar': 3, 'Apr-Jun': 6, 'Jul-Sep': 9, 'Oct-Dec': 12}.get(q, 1)
        return pd.Timestamp(year=int(year), month=m, day=1) + pd.offsets.MonthEnd(0)
    except: return pd.NaT

earn_long['Date'] = earn_long['Period'].apply(parse_period)
earn_monthly = earn_long.dropna(subset=['Date']).pivot(index='Date', columns='Region', values='WeeklyPay').resample('ME').ffill()

# Calculate Affordability Ratio = AvgPrice / (WeeklyPay * 52)
afford_data = []
for region in target_regions:
    hpi_reg = df_hpi[df_hpi['RegionName'] == region].set_index('Date')['AveragePrice'].resample('ME').last()
    earn_reg = earn_monthly[region] if region in earn_monthly.columns else pd.Series(dtype=float)
    
    # Combine
    combined = pd.concat([hpi_reg, earn_reg.rename('WeeklyPay')], axis=1)
    combined['AveragePrice'] = pd.to_numeric(combined['AveragePrice'], errors='coerce')
    combined['WeeklyPay'] = pd.to_numeric(combined['WeeklyPay'], errors='coerce')
    combined = combined.dropna()
    
    combined['Ratio'] = combined['AveragePrice'] / (combined['WeeklyPay'] * 52)
    combined['Region'] = region
    afford_data.append(combined)

df_afford = pd.concat(afford_data)
# Latest affordability summary
latest_afford = df_afford.groupby('Region').last().reset_index()
latest_afford = latest_afford.sort_values('Ratio', ascending=False)


# 2. Build Interactive Charts (Plotly)
layout_args = dict(
    paper_bgcolor='rgba(0,0,0,0)', 
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family="Inter, sans-serif"),
    margin=dict(l=40, r=40, t=50, b=40),
    hovermode='x unified'
)

# Chart 1: Inflation vs Base Rate
dates_str1 = [d.strftime('%Y-%m-%d') for d in df.index]
fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=dates_str1, y=df['CPI_Rate'].tolist(), name='CPI Inflation (%)', line=dict(color='#ef4444', width=3)))
fig1.add_trace(go.Scatter(x=dates_str1, y=df['BaseRate'].tolist(), name='BoE Base Rate (%)', line=dict(color='#3b82f6', width=3)))
fig1.update_layout(title="The Inflation Shock & Base Rate Response", yaxis_title="Percentage (%)", **layout_args)
html_chart1 = fig1.to_html(full_html=False, include_plotlyjs=False)

# Chart 2: Mortgages vs HPI Growth
fig2 = make_subplots(specs=[[{"secondary_y": True}]])
fig2.add_trace(go.Scatter(x=dates_str1, y=df['Mortgage2Y'].tolist(), name='2Y Mortgage Fixed (75% LTV)', line=dict(color='#10b981', width=3)), secondary_y=False)
fig2.add_trace(go.Scatter(x=dates_str1, y=df['BaseRate'].tolist(), name='BoE Base Rate (%)', line=dict(color='#9ca3af', width=2, dash='dash')), secondary_y=False)
fig2.add_trace(go.Bar(x=dates_str1, y=df['HPI_growth'].tolist(), name='HPI YoY Growth (%)', marker_color='rgba(139, 92, 246, 0.4)'), secondary_y=True)
fig2.update_layout(title="Mortgage Chaos & Housing Slowdown", **layout_args)
fig2.update_yaxes(title_text="Interest Rate (%)", secondary_y=False)
fig2.update_yaxes(title_text="HPI Growth (%)", secondary_y=True)
html_chart2 = fig2.to_html(full_html=False, include_plotlyjs=False)

# Chart 3: Regional HPI Disparity — ensure each region has its OWN distinct data
target_regions = ['London', 'South East', 'North East', 'Scotland', 'Wales']
df_hpi_filtered = df_hpi[df_hpi['RegionName'].isin(target_regions)].copy()
pivot_prices = df_hpi_filtered.pivot_table(index='Date', columns='RegionName', values='AveragePrice', aggfunc='mean').resample('ME').last()['2019-01-01':]
pivot_returns = (pivot_prices / pivot_prices.iloc[0]) * 100 - 100

# Debug print to verify diverging data
for r in target_regions:
    if r in pivot_returns.columns:
        vals = pivot_returns[r].dropna()
        print(f"  {r}: first={vals.iloc[0]:.2f}, last={vals.iloc[-1]:.2f}, count={len(vals)}")

fig3 = go.Figure()
colors = {'London': '#ef4444', 'South East': '#f59e0b', 'North East': '#3b82f6', 'Scotland': '#10b981', 'Wales': '#8b5cf6'}
for col in target_regions:
    if col in pivot_returns.columns:
        series = pivot_returns[col].dropna()
        x_dates = [d.strftime('%Y-%m-%d') for d in series.index]
        y_vals = series.round(2).tolist()
        fig3.add_trace(go.Scatter(x=x_dates, y=y_vals, name=col, line=dict(color=colors[col], width=2.5)))

fig3.update_layout(title="Regional Housing Inequality (Cumulative % Growth From 2019)", yaxis_title="% Growth", **layout_args)
html_chart3 = fig3.to_html(full_html=False, include_plotlyjs=False)

# Chart 6: Affordability Ratio Over Time
fig6 = go.Figure()
for region in target_regions:
    reg_data = df_afford[df_afford['Region'] == region].sort_index()
    if not reg_data.empty:
        x_dates = [d.strftime('%Y-%m-%d') for d in reg_data.index]
        fig6.add_trace(go.Scatter(x=x_dates, y=reg_data['Ratio'].round(2).tolist(), 
                                 name=region, line=dict(color=colors[region], width=3)))

fig6.update_layout(title="Housing Affordability Ratio (House Price / Annual Earnings)", 
                  yaxis_title="Ratio (Years of Salary)", **layout_args)
html_chart6 = fig6.to_html(full_html=False, include_plotlyjs=False)

# Chart 7: GDHI Per Head Trends
fig7 = go.Figure()
gdhi_colors = {'London': '#ef4444', 'South East': '#f59e0b', 'North West': '#3b82f6', 
               'Scotland': '#10b981', 'Wales': '#8b5cf6', 'North East': '#0ea5e9'}
# Filter GDHI for ITL1 regions
itl1_regions = ['London', 'South East', 'North East', 'North West', 'Scotland', 'Wales']
for region in itl1_regions:
    reg_gdhi = df_gdhi[df_gdhi['Region'] == region].sort_values('Year')
    if not reg_gdhi.empty:
        fig7.add_trace(go.Scatter(x=reg_gdhi['Year'].tolist(), y=reg_gdhi['GDHI_PerHead'].tolist(), 
                                 name=region, line=dict(color=gdhi_colors.get(region, '#94a3b8'), width=3)))

fig7.update_layout(title="Gross Disposable Household Income (GDHI) Per Head", 
                  yaxis_title="£ Per Head", **layout_args)
html_chart7 = fig7.to_html(full_html=False, include_plotlyjs=False)

# Chart 8: IMD Deprivation Heatmap & Bar (Trend Support)
# Load IMD 2019 and 2025
df_imd_2019 = load_data_jsonl('imd_2019_regional.csv')
df_imd_2025 = load_data_jsonl('imd_2025_regional.csv')

# Pre-process columns
df_imd_2019.columns = [c.strip() for c in df_imd_2019.columns]
df_imd_2025.columns = [c.strip() for c in df_imd_2025.columns]

prop_2019_col = [c for c in df_imd_2019.columns if 'Proportion of LSOAs in most deprived 10%' in c][0]
prop_2025_col = [c for c in df_imd_2025.columns if 'Proportion of LSOAs in most deprived 10%' in c][0]
score_2019_col = [c for c in df_imd_2019.columns if 'Average score' in c][0]
score_2025_col = [c for c in df_imd_2025.columns if 'Average score' in c][0]
name_2019_col = [c for c in df_imd_2019.columns if 'name' in c.lower()][0]
name_2025_col = [c for c in df_imd_2025.columns if 'name' in c.lower()][0]
code_2025_col = 'Local Authority District code (2024)' # Based on inspected header

# Merge for Trends Table (on Name to handle code changes)
df_trends = pd.merge(
    df_imd_2019[[name_2019_col, prop_2019_col, score_2019_col]],
    df_imd_2025[[name_2025_col, prop_2025_col, score_2025_col]],
    left_on=name_2019_col, right_on=name_2025_col,
    how='outer', suffixes=('_2019', '_2025')
)
df_trends['Shift'] = df_trends[f'{prop_2025_col}_2025'] - df_trends[f'{prop_2019_col}_2019']
df_trends = df_trends.sort_values('Shift', ascending=False)

# Bar Chart 8: Toggleable Top 15
top15_2025 = df_imd_2025.nlargest(15, score_2025_col)
top15_2019 = df_imd_2019.nlargest(15, score_2019_col)

fig8_bar = go.Figure()
fig8_bar.add_trace(go.Bar(
    name="2025 (Latest)",
    x=top15_2025[score_2025_col].tolist(),
    y=top15_2025[name_2025_col].tolist(),
    orientation='h',
    marker=dict(color=top15_2025[score_2025_col].tolist(), colorscale='Reds'),
    visible=True
))
fig8_bar.add_trace(go.Bar(
    name="2019 (Baseline)",
    x=top15_2019[score_2019_col].tolist(),
    y=top15_2019[name_2019_col].tolist(),
    orientation='h',
    marker=dict(color=top15_2019[score_2019_col].tolist(), colorscale='Greys'),
    visible=False
))

fig8_bar.update_layout(
    **layout_args
)
html_chart8_bar = fig8_bar.to_html(full_html=False, include_plotlyjs=False, div_id="chart8_bar")

# Chart 8b: Toggleable Density Heatmap
df_centroids = load_data_jsonl('uk_lad_centroids.csv')
code_2019_col = [c for c in df_imd_2019.columns if 'code' in c.lower()][0]
df_map_2025 = pd.merge(df_imd_2025, df_centroids, left_on=code_2025_col, right_on='code', how='inner')
df_map_2019 = pd.merge(df_imd_2019, df_centroids, left_on=code_2019_col, right_on='code', how='inner')

fig8_map = go.Figure()
# 2025 Trace
fig8_map.add_trace(go.Densitymapbox(
    name="2025 Data",
    lat=df_map_2025['lat'].tolist(),
    lon=df_map_2025['lon'].tolist(),
    z=df_map_2025[prop_2025_col].tolist(),
    radius=40, opacity=0.9, colorscale='RdYlGn', reversescale=True, zmin=0, zmax=0.5,
    colorbar_title="Deprivation % (2025)",
    hovertemplate="<b>%{text} (2025)</b><br>Concentration: %{z:.1%}<extra></extra>",
    text=df_map_2025[name_2025_col].tolist(),
    visible=True
))
# 2019 Trace
fig8_map.add_trace(go.Densitymapbox(
    name="2019 Data",
    lat=df_map_2019['lat'].tolist(),
    lon=df_map_2019['lon'].tolist(),
    z=df_map_2019[prop_2019_col].tolist(),
    radius=40, opacity=0.9, colorscale='RdYlGn', reversescale=True, zmin=0, zmax=0.5,
    colorbar_title="Deprivation % (2019)",
    hovertemplate="<b>%{text} (2019)</b><br>Concentration: %{z:.1%}<extra></extra>",
    text=df_map_2019[name_2019_col].tolist(),
    visible=False
))
fig8_map.update_layout(
    mapbox=dict(
        style="carto-positron",
        center=dict(lat=55.0, lon=-3.0),
        zoom=4.5,
        bounds={"west": -12, "east": 4, "south": 48, "north": 62}
    ),
    height=850,
    **layout_args
)
html_chart8_map = fig8_map.to_html(full_html=False, include_plotlyjs=True, div_id="chart8_map")

# Trend Table HTML
def shift_color(val):
    if pd.isna(val): return "inherit"
    if val > 0.02: return "rgba(239, 68, 68, 0.1)" # Worsening
    if val < -0.02: return "rgba(16, 185, 129, 0.1)" # Improving
    return "inherit"

trend_rows = []
for _, row in df_trends.head(100).iterrows(): # Top 100 shifts
    l_name = row[name_2025_col] if pd.notna(row[name_2025_col]) else row[name_2019_col]
    val19 = row[f'{prop_2019_col}_2019']
    val25 = row[f'{prop_2025_col}_2025']
    shift = row['Shift']
    
    val19_str = f"{val19:.1%}" if pd.notna(val19) else 'N/A'
    val25_str = f"{val25:.1%}" if pd.notna(val25) else 'N/A'
    shift_str = f"{shift:+.1%}" if pd.notna(shift) else 'N/A'
    
    color = shift_color(shift)
    trend_rows.append(f"""<tr style='background-color:{color};'>
        <td>{l_name}</td>
        <td>{val19_str}</td>
        <td>{val25_str}</td>
        <td style='font-weight:600; color:{"#ef4444" if shift > 0 else "#10b981"};'>
            {shift_str}
        </td>
    </tr>""")

trend_table_html = f"""<table class='custom-table'>
<thead><tr><th>Location</th><th>2019 %</th><th>2025 %</th><th>Shift</th></tr></thead>
<tbody>{"".join(trend_rows)}</tbody>
</table>"""

# 3. Helper for table heatmaps
def heatmap_color(val, min_v, max_v):
    if pd.isna(val) or max_v == min_v: return "inherit"
    ratio = (val - min_v) / (max_v - min_v)
    # Pastel green (144, 238, 144) to pastel red (255, 160, 160)
    r = int(144 + (255 - 144) * ratio)
    g = int(238 + (160 - 238) * ratio)
    b = int(144 + (160 - 144) * ratio)
    return f"rgb({r},{g},{b})"

# Affordability Table
afford_pivot = df_afford.pivot_table(index=df_afford.index, columns='Region', values='Ratio').resample('YE').last().sort_index(ascending=False)
afford_pivot.index = afford_pivot.index.year

afford_table_html = "<table class='custom-table'><thead><tr><th>Year</th>"
for r in target_regions: afford_table_html += f"<th>{r}</th>"
afford_table_html += "</tr></thead><tbody>"

for year, row in afford_pivot.iterrows():
    afford_table_html += f"<tr><td>{year}</td>"
    for r in target_regions:
        val = row[r]
        color = heatmap_color(val, afford_pivot.min().min(), afford_pivot.max().max())
        afford_table_html += f"<td style='background-color:{color}; font-weight:500;'>{val:.2f}</td>"
    afford_table_html += "</tr>"
afford_table_html += "</tbody></table>"


# Chart 4: Absolute Average House Prices per Region + Mortgage/Base Rate overlay
fig4 = make_subplots(specs=[[{"secondary_y": True}]])
for col in target_regions:
    if col in pivot_prices.columns:
        series = pivot_prices[col].dropna()
        x_dates = [d.strftime('%Y-%m-%d') for d in series.index]
        y_vals = series.round(0).tolist()
        fig4.add_trace(go.Scatter(x=x_dates, y=y_vals, name=col, line=dict(color=colors[col], width=2.5)), secondary_y=False)

# Overlay mortgage & base rate on secondary axis
df_rates = df[['Mortgage2Y', 'BaseRate']].dropna()
rates_dates = [d.strftime('%Y-%m-%d') for d in df_rates.index]
fig4.add_trace(go.Scatter(x=rates_dates, y=df_rates['Mortgage2Y'].tolist(), name='2Y Fixed Mortgage (%)', line=dict(color='#f97316', width=2, dash='dot')), secondary_y=True)
fig4.add_trace(go.Scatter(x=rates_dates, y=df_rates['BaseRate'].tolist(), name='BoE Base Rate (%)', line=dict(color='#6b7280', width=2, dash='dash')), secondary_y=True)

fig4.update_layout(title="Regional Average House Prices vs Borrowing Costs (2019-2026)", **layout_args)
fig4.update_yaxes(title_text="Average House Price (GBP)", tickprefix="\u00a3", secondary_y=False)
fig4.update_yaxes(title_text="Interest Rate (%)", secondary_y=True)
html_chart4 = fig4.to_html(full_html=False, include_plotlyjs=False)

# Regional Price Table — with per-column pastel heatmap
pivot_table = pivot_prices.copy()
pivot_table.columns.name = None  # Remove "RegionName" header
pivot_table = pivot_table.sort_index(ascending=False)
pivot_table.index = pivot_table.index.strftime('%Y-%m')
# Keep only target regions
region_cols = [c for c in target_regions if c in pivot_table.columns]
pivot_table = pivot_table[region_cols]

# Compute per-column min/max for heatmap normalisation
col_mins = {}
col_maxs = {}
for c in region_cols:
    vals = pivot_table[c].dropna()
    col_mins[c] = vals.min()
    col_maxs[c] = vals.max()

def heatmap_color(val, col_min, col_max):
    """Returns a pastel green-to-red background. Green=lower, Red=higher."""
    if pd.isna(val) or col_max == col_min:
        return ''
    ratio = (val - col_min) / (col_max - col_min)  # 0=lowest, 1=highest
    # Pastel green (144,238,144) -> pastel red (255,160,160)
    r = int(144 + (255 - 144) * ratio)
    g = int(238 + (160 - 238) * ratio)
    b = int(144 + (160 - 144) * ratio)
    return f'background-color: rgb({r},{g},{b});'

# Build custom HTML table with inline heatmap styles
rows_html = []
for idx, row in pivot_table.iterrows():
    cells = f'<td>{idx}</td>'
    for c in region_cols:
        val = row[c]
        style = heatmap_color(val, col_mins[c], col_maxs[c])
        formatted = f'\u00a3{val:,.0f}' if pd.notna(val) else ''
        cells += f'<td style="{style}">{formatted}</td>'
    rows_html.append(f'<tr>{cells}</tr>')

header_cells = '<th>Month</th>' + ''.join(f'<th>{c}</th>' for c in region_cols)
regional_table_html = f'''<table class="custom-table">
<thead><tr>{header_cells}</tr></thead>
<tbody>{"".join(rows_html)}</tbody>
</table>'''

# 3. Create Inline Data Table — full timeline, sorted newest first
df_table = df.copy()
df_table = df_table.sort_index(ascending=False)
df_table = df_table.drop(columns=['AveragePrice'], errors='ignore')
df_table.index = df_table.index.strftime('%Y-%m')
df_table = df_table.reset_index().rename(columns={
    'Date': 'Month', 
    'BaseRate': 'BoE Base Rate (%)',
    'Mortgage2Y': '2Y Fixed Mortgage (%)',
    'CPI_Rate': 'CPI Inflation (%)',
    'HPI_growth': 'House Price YoY Growth (%)'
}).round(2)
table_html = df_table.to_html(index=False, classes="custom-table")

# Chart 5: Spiral Heatmap — Regional Average House Prices
import numpy as np

# Build the spiral data
month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
years = sorted(pivot_prices.index.year.unique())
n_regions = len(region_cols)
segment_h = 0.9      # radial height per region segment
year_gap = 0.6       # white gap between year rings
year_ring = n_regions * segment_h  # total radial height per year

# Per-region min/max for colour scale (each region scales independently)
region_mins = {}
region_maxs = {}
for rc in region_cols:
    vals = pivot_prices[rc].dropna()
    region_mins[rc] = vals.min()
    region_maxs[rc] = vals.max()

# Pre-build a lookup: for each (year, month) -> all region values (for hover)
def get_month_hover(yr, mo):
    try:
        row = pivot_prices.loc[(pivot_prices.index.year == yr) & (pivot_prices.index.month == mo)]
        if row.empty:
            return ''
        row = row.iloc[0]
        lines = [f'{mo:02d}/{yr}']
        for rc in region_cols:
            val = row[rc]
            lines.append(f'{rc}: \u00a3{val:,.0f}' if pd.notna(val) else f'{rc}: N/A')
        return '<br>'.join(lines)
    except:
        return ''

fig5 = go.Figure()

for ri, region in enumerate(region_cols):
    thetas = []
    rs = []
    bases = []
    colors_list = []
    hovertexts = []
    
    for yi, yr in enumerate(years):
        for mo in range(1, 13):
            # Get data
            mask = (pivot_prices.index.year == yr) & (pivot_prices.index.month == mo)
            subset = pivot_prices.loc[mask]
            if subset.empty:
                continue
            val = subset[region].iloc[0]
            if pd.isna(val):
                continue
            
            # Angular position: Jan=90 (top), going clockwise
            theta = (90 - (mo - 1) * 30) % 360
            
            # Spiral radius: base increases with year AND month progression
            base_r = yi * (year_ring + year_gap) + ((mo - 1) / 12) * (year_ring + year_gap) + ri * segment_h + 2
            
            thetas.append(theta)
            rs.append(segment_h)
            bases.append(base_r)
            colors_list.append(val)
            hovertexts.append(get_month_hover(yr, mo))
    
    fig5.add_trace(go.Barpolar(
        r=rs,
        theta=thetas,
        width=[30] * len(thetas),
        base=bases,
        marker=dict(
            color=colors_list,
            colorscale=[[0, 'rgb(144,238,144)'], [0.5, 'rgb(255,255,180)'], [1, 'rgb(255,160,160)']],
            cmin=region_mins[region],
            cmax=region_maxs[region],
            showscale=(ri == n_regions - 1),
            colorbar=dict(title='Price Trend', tickvals=[], ticktext=[]) if ri == n_regions - 1 else None,
            line=dict(color='white', width=0.5)
        ),
        name=region,
        hovertext=hovertexts,
        hoverinfo='text',
    ))

# Add year labels as annotations at the spiral start points
for yi, yr in enumerate(years):
    base_r = yi * (year_ring + year_gap) + 2 + year_ring / 2
    fig5.add_annotation(
        x=0, y=0,
        text=f'<b>{yr}</b>',
        showarrow=False,
        font=dict(size=9, color='var(--text-color)'),
        xref='paper', yref='paper',
        # Position will be approximate - use polar annotations
    )

max_r = len(years) * (year_ring + year_gap) + 4
fig5.update_layout(
    title='Spiral Heatmap: Regional Average House Prices Over Time',
    polar=dict(
        angularaxis=dict(
            tickvals=[(90 - i * 30) % 360 for i in range(12)],
            ticktext=month_names,
            direction='clockwise',
            rotation=90,
            gridcolor='rgba(200,200,200,0.3)'
        ),
        radialaxis=dict(
            visible=False,
            range=[0, max_r]
        ),
        bgcolor='rgba(0,0,0,0)'
    ),
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Inter, sans-serif'),
    showlegend=True,
    legend=dict(orientation='h', yanchor='bottom', y=-0.15),
    height=700,
    margin=dict(l=60, r=60, t=60, b=80)
)
html_chart5 = fig5.to_html(full_html=False, include_plotlyjs=False)

# --------------------------------------------------------------------------------------------------------------------
# 4. PREPARE HERO SECTION & STAT HIGHLIGHTS (2019 vs 2026)
# --------------------------------------------------------------------------------------------------------------------
df_gilt_raw = load_data_jsonl('boe_gilt_yields_raw.csv')
df_gilt_raw['observation_date'] = pd.to_datetime(df_gilt_raw.iloc[:,0])
df_gilt_raw = df_gilt_raw.sort_values('observation_date')

def get_h_stat(df, d_col, v_col, yr, is_latest=False):
    try:
        if is_latest: return df.iloc[-1][v_col]
        return df[df[d_col] >= f'{yr}-01-01'].iloc[0][v_col]
    except: return 0

b19 = get_h_stat(df_boe.reset_index(), 'Date', 'IUDBEDR', 2019)
b26 = get_h_stat(df_boe.reset_index(), 'Date', 'IUDBEDR', 2026, True)
c19 = get_h_stat(df_inf.reset_index(), 'Date', 'CPI_Rate', 2019)
c26 = get_h_stat(df_inf.reset_index(), 'Date', 'CPI_Rate', 2026, True)
g19 = get_h_stat(df_gilt_raw, 'observation_date', 'IRLTLT01GBM156N', 2019)
g26 = get_h_stat(df_gilt_raw, 'observation_date', 'IRLTLT01GBM156N', 2026, True)
h19 = 235000 # Benchmark 2019
h26 = df['AveragePrice'].iloc[-1]

hero_html = f"""
    <div class="hero">
        <div class="hero-inner">
            <div class="theme-toggle-icon" onclick="toggleTheme()" title="Toggle Dark/Light Mode">◑</div>
            <div class="header-meta">Financial Services Market Insights | {datetime.now().strftime('%B %Y')}</div>
            <h1>Macroeconomic Insights &amp; Affordability</h1>
        </div>
    </div>

    <div class="insights-card">
        <h2>Crude awakening for central banks</h2>
        <ul class="insights-list">
            <li><strong>Bond Market Volatility:</strong> Global bonds fall as UK 10-year yields hit 15-year highs ({g26:.1f}%) for the first time since the 2008 financial crisis. <a class="source-ref" title="Bank of England - Gilt Yields" href="#s1">[1]</a></li>
            <li><strong>Inflation Resilience:</strong> BoE and global central banks stress readiness to act as "second-round" inflation risks from the Iran-USA geopolitical tension disrupt energy supply chains. <a class="source-ref" title="Bank of England - Monetary Policy Report" href="#s1">[1]</a><a class="source-ref" title="Reuters/Bloomberg - Energy Market Analysis" href="#news">[5]</a></li>
            <li><strong>Activity & Sentiment:</strong> Flash PMIs continue to reflect a high-interest rate environment where activity is constrained by "higher for longer" policy anchoring. <a class="source-ref" title="Reuters/Bloomberg - PMI Reports" href="#news">[5]</a></li>
            <li><strong>Inflation Outlook:</strong> Latest CPI data suggests inflation is unlikely to return to the 2% target in Q2, with persistent services-led pressure. <a class="source-ref" title="ONS - CPI Inflation" href="#s2">[2]</a><a class="source-ref" title="Financial Times - Economic Forecast" href="#news">[6]</a></li>
        </ul>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">BoE Base Rate <a class="source-ref" title="Bank of England" href="#s1">[1]</a></div>
            <div class="stat-main">
                <div class="stat-value">{b26:.2f}%</div>
                <div class="stat-trend trend-up">+{b26-b19:.2f}%</div>
            </div>
            <div class="stat-baseline">vs {b19:.2f}% in 2019</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">CPI Inflation <a class="source-ref" title="ONS - CPI" href="#s2">[2]</a></div>
            <div class="stat-main">
                <div class="stat-value">{c26:.1f}%</div>
                <div class="stat-trend trend-up">+{c26-c19:.1f}%</div>
            </div>
            <div class="stat-baseline">vs {c19:.1f}% in 2019</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">10Y Gilt Yield <a class="source-ref" title="Bank of England" href="#s1">[1]</a></div>
            <div class="stat-main">
                <div class="stat-value">{g26:.1f}%</div>
                <div class="stat-trend trend-up">+{g26-g19:.1f}%</div>
            </div>
            <div class="stat-baseline">vs {g19:.1f}% in 2019</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Avg House Price <a class="source-ref" title="Land Registry - UK HPI" href="#s4">[4]</a></div>
            <div class="stat-main">
                <div class="stat-value">£{h26/1000:.0f}k</div>
                <div class="stat-trend trend-up">+{(h26/h19 - 1):.1%}</div>
            </div>
            <div class="stat-baseline">vs £{h19/1000:.0f}k in 2019</div>
        </div>
    </div>
"""

# 5. Generate Final HTML File
html_template = f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UK Macroeconomic Deep Dive (2019-2026)</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #ffffff;
            --text-color: #111827;
            --card-bg: #f9fafb;
            --border-color: #e5e7eb;
            --accent-color: #3b82f6;
            --accent-hover: #2563eb;
            --table-header: #f3f4f6;
        }}
        [data-theme="dark"] {{
            --bg-color: #0f172a;
            --text-color: #f8fafc;
            --card-bg: #1e293b;
            --border-color: #334155;
            --accent-color: #3b82f6;
            --accent-hover: #60a5fa;
            --table-header: #0f172a;
        }}
        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            transition: background-color 0.3s, color 0.3s;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 20px;
            margin-bottom: 40px;
        }}
        h1 {{ font-size: 2.5rem; font-weight: 700; background: linear-gradient(to right, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin:0;}}
        .theme-toggle {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-color);
            padding: 10px 20px;
            border-radius: 20px;
            cursor: pointer;
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            transition: all 0.2s;
        }}
        .theme-toggle:hover {{ background-color: var(--accent-color); color: white; }}
        .section {{ margin-bottom: 60px; }}
        .text-box {{
            padding: 24px;
            background-color: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            margin-bottom: 24px;
            line-height: 1.6;
        }}
        .chart-container {{
            background-color: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            padding: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .table-wrapper {{
            max-height: 480px;
            overflow-y: auto;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            margin: 20px 0;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .custom-table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            background-color: var(--card-bg);
        }}
        .custom-table th {{
            position: sticky;
            top: 0;
            background-color: var(--table-header);
            color: var(--text-color);
            font-weight: 600;
            padding: 16px;
            border-bottom: 2px solid var(--border-color);
            z-index: 10;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .custom-table th:hover {{ background-color: var(--border-color); }}
        .custom-table th::after {{ content: ' ↕'; opacity: 0.3; font-size: 0.8em; }}
        
        .custom-table td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-color);
        }}
        .custom-table tr:hover {{ background-color: rgba(59, 130, 246, 0.05); }}
        
        /* Term & Source Hovers */
        .term-hover {{
            border-bottom: 1px dotted var(--accent-color);
            cursor: help;
            color: var(--accent-color);
            font-weight: 500;
        }}
        .source-ref {{
            font-size: 0.8em;
            vertical-align: super;
            color: var(--accent-color);
            cursor: pointer;
            text-decoration: none;
            margin-left: 2px;
            font-weight: 600;
        }}
        .source-ref:hover {{ text-decoration: underline; }}

        /* Accordions */
        details {{
            margin-bottom: 16px;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: var(--card-bg);
            overflow: hidden;
        }}
        summary {{
            padding: 16px;
            font-weight: 600;
            cursor: pointer;
            background: var(--table-header);
            list-style: none;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        summary::after {{ content: '▼'; font-size: 0.8em; transition: transform 0.2s; }}
        details[open] summary::after {{ transform: rotate(180deg); }}
        .details-content {{ padding: 20px; border-top: 1px solid var(--border-color); }}

        /* Hero Section */
        .hero {{
            background: #674fb0;
            color: white;
            padding: 60px 0 100px 0;
            text-align: left;
            position: relative;
            margin-bottom: -60px;
        }}
        .hero-inner {{ max-width: 1200px; margin: 0 auto; padding: 0 40px; position: relative; }}
        .header-meta {{ font-size: 1.1rem; opacity: 0.9; margin-bottom: 8px; font-weight: 500; }}
        .hero h1 {{ font-size: 3.5rem; margin: 0; font-weight: 800; letter-spacing: -0.02em; max-width: 800px; }}

        .theme-toggle-icon {{
            position: absolute;
            top: 0;
            right: 40px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: white;
            width: 44px;
            height: 44px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 1.2rem;
            transition: all 0.2s;
            z-index: 100;
            backdrop-filter: blur(10px);
        }}
        .theme-toggle-icon:hover {{ background: rgba(255, 255, 255, 0.2); transform: scale(1.05); }}

        /* Insights Card */
        .insights-card {{
            background: var(--card-bg);
            border-radius: 16px;
            padding: 32px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            margin: 0 auto 40px auto;
            max-width: 1120px;
            position: relative;
            z-index: 5;
            border: 1px solid var(--border-color);
        }}
        .insights-card h2 {{ color: var(--text-color); margin-top: 0; font-size: 1.8rem; border:none; padding:0; }}
        .insights-list {{ list-style: none; padding: 0; margin-top: 24px; }}
        .insights-list li {{
            margin-bottom: 16px;
            padding-left: 28px;
            position: relative;
            line-height: 1.6;
            color: var(--text-color);
            font-size: 1.05rem;
        }}
        .insights-list li::before {{
            content: "•";
            position: absolute;
            left: 0;
            color: #674fb0;
            font-size: 1.5rem;
            line-height: 1;
        }}

        /* Key Facts Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            max-width: 1120px;
            margin: 0 auto 60px auto;
        }}
        .stat-card {{
            background: var(--card-bg);
            padding: 24px;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            transition: transform 0.2s;
        }}
        .stat-card:hover {{ transform: translateY(-4px); }}
        .stat-label {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 12px; font-weight: 600; }}
        .stat-main {{ display: flex; align-items: baseline; gap: 8px; }}
        .stat-value {{ font-size: 2rem; font-weight: 700; color: var(--text-color); }}
        .stat-trend {{ font-size: 0.95rem; font-weight: 600; padding: 2px 8px; border-radius: 4px; }}
        .trend-up {{ background: rgba(239, 68, 68, 0.1); color: #ef4444; }}
        .stat-baseline {{ font-size: 0.85rem; color: #94a3b8; margin-top: 4px; }}

        .notification-box {{
            padding: 16px;
            background-color: rgba(59, 130, 246, 0.1);
            border-left: 4px solid var(--accent-color);
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.95rem;
            color: var(--text-color);
        }}

        /* Sidebar Navigation Layout */
        .chart-layout-with-sidebar {{
            display: flex;
            gap: 24px;
            align-items: flex-start;
            margin-bottom: 24px;
        }}
        .chart-main-content {{
            flex: 1;
            min-width: 0;
        }}
        .sidebar-nav {{
            width: 140px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            padding: 16px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            position: sticky;
            top: 20px;
        }}
        .nav-label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #94a3b8;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .sidebar-link {{
            color: var(--text-color);
            text-decoration: none;
            font-size: 0.95rem;
            font-weight: 500;
            padding: 8px 12px;
            border-radius: 6px;
            transition: all 0.2s;
            cursor: pointer;
            border: 1px solid transparent;
        }}
        .sidebar-link:hover {{
            background: rgba(59, 130, 246, 0.05);
            color: var(--accent-color);
        }}
        .sidebar-link.active {{
            background: rgba(59, 130, 246, 0.1);
            color: var(--accent-color);
            border-color: rgba(59, 130, 246, 0.3);
            font-weight: 700;
        }}
    </style>
</head>
<body>
    <div class="hero-wrapper">
        {hero_html}
    </div>

    <div class="container">
        <header style="display:none;">
            <h1>UK Macroeconomic Context (2019-2026)</h1>
        </header>

        <div style="height: 20px;"></div>

        <div class="section">
            <div class="text-box">
                <h2>1. The First Shock: Inflation &amp; Monetary Tightening</h2>
                <p>The post-pandemic reopening coupled with the outbreak of the war in Ukraine triggered an immediate energy crisis across Europe. International wholesale gas prices violently surged, forcing UK <span class="term-hover" title="Consumer Price Index: The headline measure of inflation in the UK.">CPI</span> to a 41-year peak of 11.1% by late 2022. To combat this imported cost-of-living crisis, the Bank of England engaged in a massive hiking sprint, dragging the <span class="term-hover" title="Bank of England Base Rate: The key interest rate set by the BoE.">Base Rate</span> from 0.1% to a 15-year high of 5.25%.</p>
            </div>
            <div class="chart-container">
                {html_chart1}
            </div>
        </div>

        <div class="section">
            <div class="text-box">
                <h2>2. Mortgage Chaos &amp; The Housing Cooldown</h2>
                <p>While the <span class="term-hover" title="Base Rate: Determines the cost of borrowing and reward for saving.">Base Rate</span> marched upwards to fight inflation, mortgage rates spiked violently in Autumn 2022. The catalyst was the September "Mini-Budget" which terrified bond markets and caused lenders to pull thousands of products, resetting 2-year fixed mortgages from ~4% to over 6% instantly. This credit tightening ultimately suppressed the runaway House Price growth originally sparked by the 2020 Stamp Duty Holiday.</p>
            </div>
            <div class="table-wrapper">
                {table_html}
            </div>
            <div class="chart-container">
                {html_chart2}
            </div>
        </div>

        <div class="section">
            <div class="text-box">
                <h2>3. The Second Shock: Regional Inequality &amp; Geopolitics</h2>
                <p>High borrowing costs disproportionally decimated housing momentum in expensive regions (like London) where high entry-prices mandate larger mortgages. Historically cheaper regions (North East, Scotland) displayed longer resilience. However, a "second-round" inflationary anchor fueled by hostilities involving Iran, Israel, and the USA disrupting oil in the Strait of Hormuz has maintained persistent consumer price pressures, forcing Central Banks to hold rates "higher for longer".</p>
            </div>
            <div class="chart-container">
                {html_chart3}
            </div>
        </div>

        <div class="section">
            <div class="text-box">
                <h2>4. Regional Average House Prices &amp; The Affordability Squeeze</h2>
                <p>While cumulative growth rates tell us which regions outpaced others, absolute average prices reveal the true scale of affordability divergence. London averages consistently dwarf the North East by a factor of 3-4x. When overlaid with borrowing costs, a critical pattern emerges: the rapid rise in mortgage rates from 2022 onwards had a compounding effect on monthly repayments in high-price regions. A 2% rate hike on a &pound;500,000 London mortgage adds roughly &pound;580/month, whereas the same hike on a &pound;170,000 North East property adds just &pound;200/month. This asymmetry is a primary driver of the regional growth divergence seen in Section 3.</p>
            </div>
            <div class="table-wrapper">
                {regional_table_html}
            </div>
            <div class="chart-container">
                {html_chart4}
            </div>
        </div>

        <div class="section">
            <div class="text-box">
                <h2>5. Spiral Heatmap: Regional House Prices Over Time</h2>
                <p>This spiral heatmap visualizes the same regional price data in a cyclical format, making it easier to identify seasonal patterns and long-term trends across all five regions simultaneously. Each ring represents a year, and each segment within a ring represents a month. The color intensity shows the price level relative to each region's own history - green indicates lower prices, while red indicates higher prices. This view reveals how regional price cycles diverge even as they share common seasonal rhythms.</p>
            </div>
            <div class="chart-container">
                {html_chart5}
            </div>
        </div>

        <div class="section">
            <div class="text-box">
                <h2>6. Regional Earnings vs House Prices: The Affordability Frontier</h2>
                <p>By comparing average house prices against median annual earnings, we can calculate the <span class="term-hover" title="Affordability Ratio: House Price divided by Annual Earnings (higher = less affordable).">Affordability Ratio</span> (the number of full-salary years needed to buy a home). While the national average has drifted, the regional disparity is stark. In London, the ratio often exceeds 12-14x, whereas in the North East, it remains closer to 5-6x. This "Affordability Frontier" determines regional mobility; as the ratio climbs in the South, we see increased "priced-out" migration toward more affordable northern hubs, which in turn begins to inflate those local markets.</p>
            </div>
            <div class="table-wrapper">
                {afford_table_html}
            </div>
            <div class="chart-container">
                {html_chart6}
            </div>
        </div>

        <div class="section">
            <div class="text-box">
                <h2>7. Disposable Income &amp; The "Real" Squeeze</h2>
                <p><span class="term-hover" title="Gross Disposable Household Income: The money available to households for spending after taxes and benefits.">Gross Disposable Household Income (GDHI)</span> represents the amount of money individuals have available for spending or saving after income distribution measures (e.g. taxes, social contributions). While nominal GDHI per head has grown since 2019, much of this gain has been offset by the inflationary shocks from the Ukraine and Middle East conflicts. High-energy costs and food inflation act as a "stealth tax" on disposable income, particularly in regions where earnings growth has lagged behind the national average.</p>
            </div>
            <div class="chart-container">
                {html_chart7}
            </div>
        </div>

        <div class="section">
            <div class="text-box">
                <h2>8. The Deprivation Landscape &amp; Trends (2019-2025) [3]</h2>
                <p>The <span class="term-hover" title="Index of Multiple Deprivation: The official measure of relative deprivation for small areas.">Index of Multiple Deprivation (IMD)</span> provides a relative measure of deprivation across England. The interactive heatmap below illustrates the <strong>Proportion of LSOAs in the most deprived 10% nationally</strong> per district. You can toggle between the 2019 baseline and the newly released 2025 update using the buttons on the map.</p>
                
                <div class="notification-box">
                    <strong>Important Information:</strong> These deprivation metrics are currently concentrated on **England**. While the map displays full UK boundaries for context, deprivation data for Scotland (SIMD), Wales (WIMD), and NI (NIMD) is pending future integration.
                </div>
            </div>

            <div class="chart-layout-with-sidebar">
                <div class="chart-main-content">
                    <div class="chart-container" style="margin-bottom: 24px;">
                        {html_chart8_map}
                    </div>

                    <div class="chart-container" style="margin-bottom: 24px;">
                        {html_chart8_bar}
                    </div>
                </div>

                <div class="sidebar-nav">
                    <div class="nav-label">Select Year</div>
                    <a class="sidebar-link active" onclick="switchYear('2025')" id="link-2025">2025 Snapshot</a>
                    <a class="sidebar-link" onclick="switchYear('2019')" id="link-2019">2019 Baseline</a>
                </div>
            </div>

            <div class="text-box">
                <h3>IMD Deprivation Trends: 2019 vs 2025</h3>
                <p>This table highlights the shift in deprivation concentration over the last six years. <span style="background-color:rgba(239, 68, 68, 0.1); padding:2px 4px; border-radius:4px;">Red-tinted rows</span> indicate areas where the concentration of deprivation has intensified (more LSOAs in the bottom 10%), while <span style="background-color:rgba(16, 185, 129, 0.1); padding:2px 4px; border-radius:4px;">green-tinted rows</span> indicate relative improvement.</p>
                <div class="table-wrapper">
                    {trend_table_html}
                </div>
            </div>
        </div>

        <details id="terms">
            <summary>Key of Terms &amp; Definitions</summary>
            <div class="details-content">
                <ul>
                    <li><strong>BoE Base Rate:</strong> The interest rate the Bank of England charges other banks. Influences mortgage and savings rates.</li>
                    <li><strong>CPI Inflation:</strong> Consumer Price Index. Measures the average change over time in the prices paid by consumers for a market basket of goods and services.</li>
                    <li><strong>10Y Gilt Yield:</strong> The return on 10-year UK Government bonds. A benchmark for long-term borrowing costs.</li>
                    <li><strong>GDHI:</strong> Gross Disposable Household Income. The money available to households for spending or saving after taxes and benefits.</li>
                    <li><strong>IMD:</strong> Index of Multiple Deprivation. The official measure of relative deprivation for small areas in England.</li>
                </ul>
            </div>
        </details>

        <details id="news">
            <summary>News &amp; Contextual Sources</summary>
            <div class="details-content">
                <ul>
                    <li><strong>[5] Reuters / S&amp;P Global</strong> — PMI Indices and Global Supply Chain sentiment: <a href="https://www.reuters.com" target="_blank">Reuters.com</a></li>
                    <li><strong>[6] Goldman Sachs / Financial Times</strong> — Energy Market Analysis and Regional Geopolitics: <a href="https://www.ft.com" target="_blank">FT.com</a></li>
                </ul>
            </div>
        </details>

        <details id="sources">
            <summary>Data Sources &amp; Citations</summary>
            <div class="details-content">
                <ul>
                    <li><strong>[1] Bank of England</strong> (s1) — <a href="https://www.bankofengland.co.uk" target="_blank">bankofengland.co.uk</a></li>
                    <li><strong>[2] ONS</strong> (s2) — <a href="https://www.ons.gov.uk" target="_blank">ons.gov.uk</a></li>
                    <li><strong>[3] MHCLG</strong> (s3) — <a href="https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025" target="_blank">IMD Report</a></li>
                    <li><strong>[4] Land Registry</strong> (s4) — <a href="https://www.gov.uk/government/organisations/land-registry" target="_blank">gov.uk</a></li>
                </ul>
            </div>
        </details>
    </div>

    <script>
        function toggleTheme() {{
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            html.setAttribute('data-theme', newTheme);
            
            const mainIcon = document.querySelector('.theme-toggle-icon');
            mainIcon.textContent = newTheme === 'light' ? '◑' : '☼';
            
            const fontColor = newTheme === 'light' ? '#333' : '#e2e8f0';
            const gridColor = newTheme === 'light' ? '#e2e8f0' : '#334155';
            
            const update = {{
                'font.color': fontColor,
                'xaxis.gridcolor': gridColor,
                'yaxis.gridcolor': gridColor,
                'xaxis.tickfont.color': fontColor,
                'yaxis.tickfont.color': fontColor
            }};
            
            const charts = document.querySelectorAll('.js-plotly-plot');
            charts.forEach(function(chart) {{
                Plotly.relayout(chart, update);
            }});
        }}

        // Client-side Table Sorting
        document.querySelectorAll('.custom-table th').forEach(headerCell => {{
            headerCell.addEventListener('click', () => {{
                const table = headerCell.closest('table');
                const tbody = table.querySelector('tbody');
                const index = Array.from(headerCell.parentNode.children).indexOf(headerCell);
                const rows = Array.from(tbody.querySelectorAll('tr'));
                const isAscending = headerCell.classList.contains('th-sort-asc');
                
                rows.sort((a, b) => {{
                    const aText = a.children[index].textContent.trim();
                    const bText = b.children[index].textContent.trim();
                    
                    // Parse numbers/percents
                    const aNum = parseFloat(aText.replace(/[&pound;%,]/g, ''));
                    const bNum = parseFloat(bText.replace(/[&pound;%,]/g, ''));
                    
                    if (!isNaN(aNum) && !isNaN(bNum)) {{
                        return isAscending ? bNum - aNum : aNum - bNum;
                    }}
                    
                    // Handle Dates (YYYY-MM or YYYY)
                    const aDate = Date.parse(aText);
                    const bDate = Date.parse(bText);
                    if (!isNaN(aDate) && !isNaN(bDate)) {{
                        return isAscending ? bDate - aDate : aDate - bDate;
                    }}

                    return isAscending ? bText.localeCompare(aText) : aText.localeCompare(bText);
                }});

                tbody.append(...rows);
                table.querySelectorAll('th').forEach(th => th.classList.remove('th-sort-asc', 'th-sort-desc'));
                headerCell.classList.toggle('th-sort-asc', !isAscending);
                headerCell.classList.toggle('th-sort-desc', isAscending);
            }});
        }});

        // Trigger default sort on load
        document.querySelectorAll('.custom-table').forEach(table => {{
            const firstHeader = table.querySelector('th');
            if (firstHeader) {{
                const text = firstHeader.textContent.toLowerCase();
                // If it's a date/year, we want Recent first (Descending in our toggle logic starts Asc but we can force it)
                if (text.includes('month') || text.includes('year')) {{
                    firstHeader.click(); // First click -> usually Asc
                    if (firstHeader.classList.contains('th-sort-asc')) {{
                        firstHeader.click(); // Second click -> Desc
                    }}
                }} else {{
                    firstHeader.click(); // Default Asc
                }}
            }}
        }});

        // Year Switching Logic for Section 8
        function switchYear(year) {{
            const is2025 = year === '2025';
            const mapDiv = document.getElementById('chart8_map');
            const barDiv = document.getElementById('chart8_bar');

            // Update Map
            Plotly.update(mapDiv, {{visible: [is2025, !is2025]}}, {{
                title: is2025 ? "National Deprivation Heatmap (2025 Latest)" : "National Deprivation Heatmap (2019 Baseline)"
            }});

            // Update Bar Chart
            Plotly.update(barDiv, {{visible: [is2025, !is2025]}}, {{
                title: is2025 ? "Top 15 Most Deprived Districts (IMD 2025)" : "Top 15 Most Deprived Districts (IMD 2019)"
            }});

            // Update Sidebar Links
            document.querySelectorAll('.sidebar-link').forEach(link => link.classList.remove('active'));
            document.getElementById('link-' + year).classList.add('active');
        }}
    </script>
</body>
</html>
"""

with open('dist/macro_analysis_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html_template)
    
print("Dashboard regenerated successfully.")


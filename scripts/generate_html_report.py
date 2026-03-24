import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. Load Data
df_boe = pd.read_csv('output/boe_base_rate.csv')
df_boe['Date'] = pd.to_datetime(df_boe['DATE'])
df_boe = df_boe.set_index('Date').resample('ME').last()

df_inf = pd.read_csv('output/ons_cpi_inflation.csv', skiprows=8, names=['Date', 'CPI_Rate'])
df_inf['Date'] = pd.to_datetime(df_inf['Date'], errors='coerce')
df_inf = df_inf.dropna(subset=['Date'])
df_inf = df_inf.set_index('Date').resample('ME').last()

df_mort2 = pd.read_csv('output/boe_IUMTLMV.csv')
df_mort2['Date'] = pd.to_datetime(df_mort2['DATE'])
df_mort2 = df_mort2.set_index('Date').resample('ME').last()

df_hpi = pd.read_csv('output/uk_hpi_data.csv', low_memory=False)
df_hpi['Date'] = pd.to_datetime(df_hpi['Date'], format='%d/%m/%Y')
df_hpi_agg = df_hpi.groupby('Date')[['AveragePrice', '12m%Change']].mean().resample('ME').last()

# Master DF (2019+)
df = pd.concat([
    df_boe['IUDBEDR'].rename('BaseRate'),
    df_inf['CPI_Rate'],
    df_mort2['IUMTLMV'].rename('Mortgage2Y'),
    df_hpi_agg['AveragePrice'],
    df_hpi_agg['12m%Change'].rename('HPI_growth')
], axis=1)
df = df['2019-01-01':].ffill()

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

# 4. Generate Final HTML File
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
        }}
        .custom-table td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-color);
        }}
        .custom-table tr:hover {{ background-color: rgba(59, 130, 246, 0.05); }}
        .sources {{
            margin-top: 80px;
            padding-top: 40px;
            border-top: 1px solid var(--border-color);
            font-size: 0.9rem;
        }}
        .sources a {{ color: var(--accent-color); text-decoration: none; }}
        .sources a:hover {{ text-decoration: underline; }}
        .sources li {{ margin-bottom: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>UK Macroeconomic Context (2019-2026)</h1>
            <button class="theme-toggle" onclick="toggleTheme()">Toggle Dark Mode</button>
        </header>

        <div class="section">
            <div class="text-box">
                <h2>1. The First Shock: Inflation &amp; Monetary Tightening</h2>
                <p>The post-pandemic reopening coupled with the outbreak of the war in Ukraine triggered an immediate energy crisis across Europe. International wholesale gas prices violently surged, forcing UK CPI to a 41-year peak of 11.1% by late 2022. To combat this imported cost-of-living crisis, the Bank of England engaged in a massive hiking sprint, dragging the Base Rate from 0.1% to a 15-year high of 5.25%.</p>
            </div>
            <div class="chart-container">
                {html_chart1}
            </div>
        </div>

        <div class="section">
            <div class="text-box">
                <h2>2. Mortgage Chaos &amp; The Housing Cooldown</h2>
                <p>While the Base Rate marched upwards to fight inflation, mortgage rates spiked violently in Autumn 2022. The catalyst was the September "Mini-Budget" which terrified bond markets and caused lenders to pull thousands of products, resetting 2-year fixed mortgages from ~4% to over 6% instantly. This credit tightening ultimately suppressed the runaway House Price growth originally sparked by the 2020 Stamp Duty Holiday.</p>
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
                <h2>5. Spiral Heatmap: Average House Prices by Region</h2>
                <p>This spiral visualisation plots regional average house prices over time. Each ring represents one year, spiralling outward from 2019 at the centre to the most recent data at the edge. Months are arranged clockwise from January at the top. Within each month, the 5 concentric segments represent individual regions. Colour intensity reflects the average house price: <span style="color: rgb(144,238,144); font-weight:600;">pastel green</span> for lower values transitioning to <span style="color: rgb(255,160,160); font-weight:600;">pastel red</span> for higher values. Hover over any segment to see the full breakdown.</p>
            </div>
            <div class="chart-container">
                {html_chart5}
            </div>
        </div>

        <div class="sources">
            <h3>Sources &amp; Citations</h3>
            <h4>Data Sources</h4>
            <ul>
                <li><strong>Bank of England</strong> &mdash; Base Rate and Quoted Household MFI Rates: <a href="https://www.bankofengland.co.uk/boeapps/database/" target="_blank">bankofengland.co.uk</a></li>
                <li><strong>Office for National Statistics (ONS)</strong> &mdash; Consumer Price Inflation Time Series: <a href="https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23" target="_blank">ons.gov.uk</a></li>
                <li><strong>HM Land Registry</strong> &mdash; UK House Price Index: <a href="https://www.gov.uk/government/statistical-data-sets/uk-house-price-index-data-downloads-november-2024" target="_blank">gov.uk</a></li>
                <li><strong>FRED (Federal Reserve)</strong> &mdash; 30-Year US Fixed Rate Mortgage Average: <a href="https://fred.stlouisfed.org/series/MORTGAGE30US" target="_blank">fred.stlouisfed.org</a></li>
            </ul>
            <h4>Context &amp; News Sources</h4>
            <ul>
                <li><strong>Ukraine Energy Shock</strong> &mdash; Impact of the war on global energy bills: <a href="https://www.energy.gov" target="_blank">Energy.gov</a>, <a href="https://eciu.net" target="_blank">ECIU</a></li>
                <li><strong>Mini-Budget Mortgage Crash (Sep 2022)</strong> &mdash; Bond market disruption hiking UK mortgages past 6%: <a href="https://www.theguardian.com/business/2022/sep/28/mortgage-lenders-pull-products-amid-market-turmoil-truss-mini-budget" target="_blank">The Guardian</a>, <a href="https://moneyweek.com/personal-finance/mortgages/605204/average-mortgage-rates" target="_blank">MoneyWeek</a></li>
                <li><strong>Middle East Oil Disruption (2024-2026)</strong> &mdash; Strait of Hormuz supply threats holding inflation higher: <a href="https://www.goldmansachs.com/insights/articles/what-the-middle-east-conflict-could-mean-for-oil-prices" target="_blank">Goldman Sachs</a>, <a href="https://www.al-monitor.com" target="_blank">Al-Monitor</a></li>
                <li><strong>Stamp Duty Holiday (2020-2021)</strong> &mdash; Pandemic housing boom driver: <a href="https://www.unbiased.co.uk" target="_blank">Unbiased.co.uk</a>, <a href="https://www.cbre.co.uk" target="_blank">CBRE</a></li>
                <li><strong>Bank of England Monetary Policy</strong> &mdash; MPC decisions and forward guidance: <a href="https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2023/august-2023" target="_blank">BoE MPC August 2023</a></li>
                <li><strong>UK Parliament</strong> &mdash; Inflation research briefings: <a href="https://commonslibrary.parliament.uk/research-briefings/cbp-9428/" target="_blank">parliament.uk</a></li>
            </ul>
        </div>
    </div>

    <script>
        function toggleTheme() {{
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            html.setAttribute('data-theme', newTheme);
            
            const btn = document.querySelector('.theme-toggle');
            btn.textContent = newTheme === 'light' ? 'Toggle Dark Mode' : 'Toggle Light Mode';
            
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
    </script>
</body>
</html>
"""

with open('output/macro_analysis_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html_template)
    
print("Dashboard regenerated successfully.")

"""
Shared library functions for generate_html_report.py

Contains:
- Data loading functions
- Column validation helpers
- Date processing utilities
- Centralized color constants
"""

import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any


# =============================================================================
# CENTRALIZED COLOR CONSTANTS (Phase 5.1)
# =============================================================================

CHART_COLORS = {
    # Primary colors
    'primary_red': '#ef4444',
    'primary_blue': '#3b82f6',
    'success_green': '#10b981',
    'warning_amber': '#f59e0b',
    'neutral_gray': '#6b7280',
    
    # Extended palette
    'purple': '#8b5cf6',
    'cyan': '#0ea5e9',
    'orange': '#f97316',
    'pink': '#ec4899',
    'lime': '#84cc16',
    
    # Region-specific colors
    'region_london': '#ef4444',
    'region_south_east': '#f59e0b',
    'region_north_east': '#3b82f6',
    'region_scotland': '#10b981',
    'region_wales': '#8b5cf6',
    'region_north_west': '#0ea5e9',
}

# Layout defaults for Plotly charts
LAYOUT_ARGS = dict(
    paper_bgcolor='rgba(0,0,0,0)', 
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family="Inter, sans-serif"),
    margin=dict(l=40, r=40, t=50, b=40),
    hovermode='x unified'
)


# =============================================================================
# DATA LOADING FUNCTIONS
# =============================================================================

def load_boe_base_rate(filepath: str = 'output/boe_base_rate.csv') -> pd.DataFrame:
    """Load and process Bank of England base rate data."""
    df = pd.read_csv(filepath)
    df['Date'] = pd.to_datetime(df['DATE'])
    df = df.set_index('Date').resample('ME').last()
    return df


def load_cpi_inflation(filepath: str = 'output/ons_cpi_inflation.csv') -> pd.DataFrame:
    """Load and process ONS CPI inflation data."""
    df = pd.read_csv(filepath, skiprows=8, names=['Date', 'CPI_Rate'])
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])
    df = df.set_index('Date').resample('ME').last()
    return df


def load_mortgage_data(filepath: str = 'output/boe_IUMTLMV.csv') -> pd.DataFrame:
    """Load and process mortgage rate data."""
    df = pd.read_csv(filepath)
    df['Date'] = pd.to_datetime(df['DATE'])
    df = df.set_index('Date').resample('ME').last()
    return df


def load_hpi_data(filepath: str = 'output/uk_hpi_data.csv') -> pd.DataFrame:
    """Load and process UK House Price Index data."""
    df = pd.read_csv(filepath, low_memory=False)
    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y')
    return df


def load_earnings_data(filepath: str = 'output/ons_earn05_regional_earnings.csv') -> pd.DataFrame:
    """Load and process regional earnings data."""
    return pd.read_csv(filepath)


def load_gdhi_data(filepath: str = 'output/ons_gdhi_regional.csv') -> pd.DataFrame:
    """Load and process Gross Disposable Household Income data."""
    return pd.read_csv(filepath)


def load_imd_data(filepath: str) -> pd.DataFrame:
    """Load and process Index of Multiple Deprivation data."""
    df = pd.read_csv(filepath)
    df.columns = [c.strip() for c in df.columns]
    return df


def load_all_macro_data() -> pd.DataFrame:
    """Load all macro economic data and combine into single DataFrame (2019+)."""
    df_boe = load_boe_base_rate()
    df_inf = load_cpi_inflation()
    df_mort = load_mortgage_data()
    df_hpi = load_hpi_data()
    
    df_hpi_agg = df_hpi.groupby('Date')[['AveragePrice', '12m%Change']].mean().resample('ME').last()
    
    df = pd.concat([
        df_boe['IUDBEDR'].rename('BaseRate'),
        df_inf['CPI_Rate'],
        df_mort['IUMTLMV'].rename('Mortgage2Y'),
        df_hpi_agg['AveragePrice'],
        df_hpi_agg['12m%Change'].rename('HPI_growth')
    ], axis=1)
    
    df = df['2019-01-01':].ffill()
    return df


# =============================================================================
# DATE PROCESSING UTILITIES
# =============================================================================

def parse_quarter_period(p: str) -> Optional[pd.Timestamp]:
    """
    Convert quarter period string (e.g., 'Jan-Mar 2024') to end of quarter date.
    
    Args:
        p: Quarter string like 'Jan-Mar 2024'
    
    Returns:
        Timestamp at end of quarter or NaT if parsing fails
    """
    try:
        parts = str(p).split(' ')
        if len(parts) != 2:
            return pd.NaT
        q, year = parts[0], parts[1]
        month_map = {'Jan-Mar': 3, 'Apr-Jun': 6, 'Jul-Sep': 9, 'Oct-Dec': 12}
        m = month_map.get(q, 1)
        return pd.Timestamp(year=int(year), month=m, day=1) + pd.offsets.MonthEnd(0)
    except:
        return pd.NaT


def dates_to_strings(dates: pd.DatetimeIndex) -> List[str]:
    """Convert DatetimeIndex to list of date strings."""
    return [d.strftime('%Y-%m-%d') for d in dates]


# =============================================================================
# AFFORDABILITY CALCULATION
# =============================================================================

def calculate_affordability_ratio(
    df_hpi: pd.DataFrame,
    df_earnings: pd.DataFrame,
    target_regions: List[str] = None
) -> pd.DataFrame:
    """
    Calculate housing affordability ratio (House Price / Annual Earnings).
    
    Args:
        df_hpi: House Price Index data
        df_earnings: Earnings data
        target_regions: List of regions to include
    
    Returns:
        DataFrame with affordability ratios by region and date
    """
    if target_regions is None:
        target_regions = ['London', 'South East', 'North East', 'Scotland', 'Wales']
    
    # Process earnings to monthly
    earn_long = df_earnings.melt(id_vars='Period', var_name='Region', value_name='WeeklyPay')
    earn_long['Date'] = earn_long['Period'].apply(parse_quarter_period)
    earn_monthly = earn_long.dropna(subset=['Date']).pivot(
        index='Date', columns='Region', values='WeeklyPay'
    ).resample('ME').ffill()
    
    # Calculate ratios for each region
    afford_data = []
    for region in target_regions:
        hpi_reg = df_hpi[df_hpi['RegionName'] == region].set_index('Date')['AveragePrice'].resample('ME').last()
        earn_reg = earn_monthly[region] if region in earn_monthly.columns else pd.Series(dtype=float)
        
        combined = pd.concat([hpi_reg, earn_reg.rename('WeeklyPay')], axis=1)
        combined['AveragePrice'] = pd.to_numeric(combined['AveragePrice'], errors='coerce')
        combined['WeeklyPay'] = pd.to_numeric(combined['WeeklyPay'], errors='coerce')
        combined = combined.dropna()
        
        combined['Ratio'] = combined['AveragePrice'] / (combined['WeeklyPay'] * 52)
        combined['Region'] = region
        afford_data.append(combined)
    
    return pd.concat(afford_data)


# =============================================================================
# TABLE HELPER FUNCTIONS
# =============================================================================

def heatmap_color(val: Any, min_v: float, max_v: float) -> str:
    """
    Generate pastel heatmap color based on value position.
    
    Args:
        val: Value to color
        min_v: Minimum value in range
        max_v: Maximum value in range
    
    Returns:
        CSS background-color string
    """
    if pd.isna(val) or max_v == min_v:
        return "inherit"
    ratio = (val - min_v) / (max_v - min_v)
    # Pastel green (144, 238, 144) to pastel red (255, 160, 160)
    r = int(144 + (255 - 144) * ratio)
    g = int(238 + (160 - 238) * ratio)
    b = int(144 + (160 - 144) * ratio)
    return f"rgb({r},{g},{b})"


def shift_color(val: float) -> str:
    """
    Determine background color based on shift value (positive/negative).
    
    Args:
        val: Shift value to evaluate
    
    Returns:
        CSS background-color string
    """
    if pd.isna(val):
        return "inherit"
    if val > 0.02:
        return "rgba(239, 68, 68, 0.1)"  # Worsening (red tint)
    if val < -0.02:
        return "rgba(16, 185, 129, 0.1)"  # Improving (green tint)
    return "inherit"


# =============================================================================
# REGIONAL DATA PROCESSING
# =============================================================================

def process_regional_hpi(
    df_hpi: pd.DataFrame,
    target_regions: List[str] = None,
    start_date: str = '2019-01-01'
) -> pd.DataFrame:
    """
    Process regional HPI data into pivot table.
    
    Args:
        df_hpi: Raw HPI data
        target_regions: Regions to include
        start_date: Start date filter
    
    Returns:
        Pivot table with dates as index and regions as columns
    """
    if target_regions is None:
        target_regions = ['London', 'South East', 'North East', 'Scotland', 'Wales']
    
    df_filtered = df_hpi[df_hpi['RegionName'].isin(target_regions)].copy()
    pivot_prices = df_filtered.pivot_table(
        index='Date', 
        columns='RegionName', 
        values='AveragePrice', 
        aggfunc='mean'
    ).resample('ME').last()[start_date:]
    
    return pivot_prices


def calculate_cumulative_returns(pivot_prices: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate cumulative percentage returns from base period.
    
    Args:
        pivot_prices: Pivot table of prices by region
    
    Returns:
        DataFrame with cumulative % returns
    """
    return (pivot_prices / pivot_prices.iloc[0]) * 100 - 100


# =============================================================================
# IMD DATA PROCESSING
# =============================================================================

def find_imd_columns(df: pd.DataFrame) -> Dict[str, str]:
    """
    Find IMD column names dynamically.
    
    Args:
        df: IMD DataFrame
    
    Returns:
        Dictionary mapping logical names to actual column names
    """
    cols = df.columns.tolist()
    return {
        'proportion': [c for c in cols if 'Proportion of LSOAs in most deprived 10%' in c][0],
        'score': [c for c in cols if 'Average score' in c][0],
        'name': [c for c in cols if 'name' in c.lower()][0],
        'code': [c for c in cols if 'code' in c.lower()][0]
    }


def merge_imd_trends(
    df_2019: pd.DataFrame,
    df_2025: pd.DataFrame
) -> pd.DataFrame:
    """
    Merge IMD data from 2019 and 2025 to show trends.
    
    Args:
        df_2019: 2019 IMD data
        df_2025: 2025 IMD data
    
    Returns:
        Merged DataFrame with shift calculations
    """
    cols_2019 = find_imd_columns(df_2019)
    cols_2025 = find_imd_columns(df_2025)
    
    df_trends = pd.merge(
        df_2019[[cols_2019['name'], cols_2019['proportion'], cols_2019['score']]],
        df_2025[[cols_2025['name'], cols_2025['proportion'], cols_2025['score']]],
        left_on=cols_2019['name'], right_on=cols_2025['name'],
        how='outer', suffixes=('_2019', '_2025')
    )
    
    prop_2025_col = f"{cols_2025['proportion']}_2025"
    prop_2019_col = f"{cols_2019['proportion']}_2019"
    
    df_trends['Shift'] = df_trends[prop_2025_col] - df_trends[prop_2019_col]
    df_trends = df_trends.sort_values('Shift', ascending=False)
    
    return df_trends
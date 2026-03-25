import pandas as pd
import requests
import os
from io import StringIO

# FRED Series GBMT10UK: 10-Year Government Bond Yields in the United Kingdom
url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GBMT10UK"

def pull_gilt_yields():
    print(f"Fetching UK 10-year Gilt Yield data from FRED (GBMT10UK)...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        df = pd.read_csv(StringIO(response.text))
        
        # Strip potential spaces and ensure numeric
        df.columns = [c.strip() for c in df.columns]
        df['GBMT10UK'] = pd.to_numeric(df['GBMT10UK'], errors='coerce')
        
        # Filter for 2019 onwards
        df['DATE'] = pd.to_datetime(df['DATE'])
        df = df[df['DATE'] >= '2019-01-01']
        
        os.makedirs('output', exist_ok=True)
        df.to_csv('output/boe_gilt_yields.csv', index=False)
        print(f"Successfully saved {len(df)} records of Gilt Yield data to output/boe_gilt_yields.csv")
        return df
    except Exception as e:
        print(f"Error pulling Gilt Yields from FRED: {e}")
        return None

if __name__ == "__main__":
    pull_gilt_yields()

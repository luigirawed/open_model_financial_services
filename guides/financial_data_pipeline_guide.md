# Financial Data Pipeline Guide

This guide explains how to use the automated UK financial data pull pipeline. The pipeline currently extracts the Bank of England Base Rate, the UK HM Land Registry House Price Index, and the US FRED 30-Year Mortgage Rate (as an external reference).

## Repository Structure
- `notebooks/financial_data_pull.ipynb`: The main Jupyter Notebook that contains the extraction logic.
- `output/`: Directory where the raw `.csv` files are saved.
- `guides/`: Documentation folder.
- `_agents/skills/`: Holds the SKILL for the agent to replicate this pipeline.

## Running the Pipeline
You can run the pipeline locally using Jupyter Notebook:
1. Ensure your environment has the required packages (`pandas`, `requests`, `jupyter`, `lxml`, `pandas-datareader`, `openpyxl`):
   ```bash
   pip install pandas requests jupyter lxml pandas-datareader openpyxl
   ```
2. Run the notebook from the terminal without opening the UI:
   ```bash
   jupyter nbconvert --execute notebooks/financial_data_pull.ipynb --to notebook --inplace
   ```
3. Alternatively, launch Jupyter and run the cells individually:
   ```bash
   jupyter notebook notebooks/financial_data_pull.ipynb
   ```

## Fallback Mechanisms
The pipeline is designed with fault tolerance. It uses `try...except` blocks with configurable timeouts (default 15s) for API calls. If an online source is unreachable, the script will automatically check the `output/` directory for an existing version of that CSV and gracefully fall back to it, allowing downstream tasks to continue unhindered.

## Adding New Data Sources
To add a new data source:
1. Open the `financial_data_pull.ipynb` notebook.
2. Create a new markdown and code cell at the bottom.
3. Use the `fetch_and_save_csv(url, filename)` helper function for standard CSV endpoints.
   *Example:*
   ```python
   # Example: ONS CPI (Inflation)
   cpi_url = 'https://example.ons.gov.uk/cpi.csv'
   df_cpi = fetch_and_save_csv(cpi_url, 'uk_cpi_inflation.csv')
   ```
4. If a source requires HTML scraping (like the BoE Base Rate), use the `pd.read_html()` methodology as demonstrated in the notebook.

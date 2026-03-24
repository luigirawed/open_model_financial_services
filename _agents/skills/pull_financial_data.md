---
name: pull_financial_data
description: Extracts and standardizes open financial data relevant to UK wealth management safely using Python Jupyter Notebooks.
---

# `pull_financial_data` SKILL

## Description
This skill provides the automated data extraction pipeline used for retrieving crucial macroeconomic indicators (Bank of England rates, HM Land Registry HPI, FRED data). It relies on Jupyter Notebooks to orchestrate the fetching, saving, and graceful fallback behaviors for open financial data.

## Relevant Files
- `notebooks/financial_data_pull.ipynb`: The orchestration script.
- `output/` *: The destination folder for all raw parsed datasets.
- `guides/financial_data_pipeline_guide.md`: Human reference guide.

## Design Philosophy & Standard Operating Procedures
1. **Never mutate old datasets without a fallback**: The architecture must prioritize the survival of the downstream analysis. If a data source becomes unreachable, the fallback mechanism (using previously downloaded local CSV files) MUST activate.
2. **Prioritize Open/Free Data**: Data sources must not compel the user to authenticate manually (unless a free API key is configured). Default priority is always Open Government Data (e.g., ONS, BoE, HM Land Registry).
3. **UK Core, Global Context**: While the explicit focus is the UK market, US/Global metrics (like FRED US Treasuries or US Mortgages) can be pulled strictly as reference points for macro shifts affecting the UK.

## How to use this skill
When the User requests a new data point (e.g., "Add the UK Inflation rate"):
1. Research the specific CSV endpoint from the Office for National Statistics (ONS) or equivalent open data portal.
2. If a clean CSV endpoint is found, append a new section to `notebooks/financial_data_pull.ipynb` utilizing the `fetch_and_save_csv(url, filename)` method.
3. If the data is within an HTML table, leverage `pd.read_html(url)`.
4. Always test the implementation by running `jupyter nbconvert --execute notebooks/financial_data_pull.ipynb --to notebook --inplace` inside the workspace.
5. Check `output/` to confirm the successful download of the new dataset.

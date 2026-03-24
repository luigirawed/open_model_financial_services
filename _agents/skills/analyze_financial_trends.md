---
name: analyze_financial_trends
description: Synthesizes macroeconomic data, outputs trend charts via Jupyter Notebooks, and conducts web research to correlate data shifts with real-world events.
---

# `analyze_financial_trends` SKILL

## Description
This skill focuses on taking raw timeline data (e.g., Inflation, Base Rates, Mortgage Rates, House Prices) from the `output/` directory, identifying structural anomalies or shifts, and performing external internet research to determine the fundamental root causes of those anomalies. Finally, it presents these findings cohesively with inline visual tables and citations.

## Relevant Files
- `notebooks/financial_data_analysis.ipynb`: The analysis engine that merges the timelines and plots the correlation charts.
- `output/chart_*.png`: The resulting visual pngs.
- `analysis_results.md`: The culminating macroeconomic report (or equivalent target walkthrough file).

## Design Philosophy & Standard Operating Procedures
1. **Always Cite Sources**: When providing commentary on significant economic shifts or trend breaks, the agent MUST use the `search_web` tool to find contemporary financial press and formally embed the links inline within the final reports (e.g., `[Source: BBC News](URL)`).
2. **Visual Evidence**: Any major structural claims ("Mortgages rose faster than Base Rates") must be accompanied by inline markdown tables or Jupyter-generated chart exports proving the mathematical disparity.
3. **Macro Constraints**: Ensure data is properly merged across differing time horizons. The preferred path is to resample all daily/weekly inputs to **Monthly (`'M'`)** averages for a smooth, comparable timeline. 
4. **Internet Autonomy**: The agent is granted full autonomy to query macroeconomic events as long as stringently referenced. Ensure search queries are specific, using the year, month, and exact dataset in question (e.g., "UK mortgage rate spike September 2022 mini-budget").

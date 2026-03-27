# Open Model Financial Services

A series of scripts to easily build data models for the UK financial services sector. Provides interactive dashboards for analyzing UK economic indicators including House Price Index (HPI), earnings deprivation, and gilt yields.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Required packages: `pandas`, `plotly`

### Installation

```bash
git clone https://github.com/luigi-enjoy-digital/open_model_financial_services.git
cd open_model_financial_services
pip install pandas plotly
```

### Generate Dashboard

```bash
python scripts/generate_html_report.py
```

The dashboard will be generated in the `output/` directory.

## 📊 Live Dashboard

View the latest dashboard deployed to GitHub Pages:
**<https://luigi-enjoy-digital.github.io/open_model_financial_services/>**

## 📁 Project Structure

```
open_model_financial_services/
├── _agents/              # AI agent configurations
│   └── skills/          # Specialized skills for data analysis
├── guides/              # Documentation and guides
│   ├── data_explainer.md
│   └── financial_data_pipeline_guide.md
├── notebooks/           # Jupyter notebooks for data analysis
│   ├── financial_data_analysis.ipynb
│   ├── financial_data_pull.ipynb
│   └── regional_hpi_analysis.ipynb
├── plans/               # Project planning
│   ├── TODO.md          # Project roadmap
│   └── REVIEW.md        # Technical decisions and notes
├── scripts/             # Data processing and report generation
│   ├── generate_html_report.py      # Main dashboard generator
│   ├── generate_html_report_lib.py  # Shared library functions
│   └── *.py            # Data cleaning scripts
├── .gitignore          # Excludes data/ and output/
└── README.md           # This file
```

## 🔧 Available Scripts

| Script | Description |
|--------|-------------|
| `generate_html_report.py` | Generates interactive HTML dashboard |
| `generate_html_report_lib.py` | Shared library with data loading functions |
| `pull_earnings_deprivation.py` | Pulls ONS earnings and deprivation data |
| `pull_gilt_yields.py` | Pulls UK gilt yield data |
| `clean_all_datasets.py` | Cleans and standardizes all datasets |

## 📈 Data Sources

- **Bank of England**: Base rates, mortgage rates
- **ONS (Office for National Statistics)**: CPI inflation, House Price Index, regional earnings, GDHI
- **English Indices of Deprivation**: IMD scores by local authority

## 🏗️ Architecture

### Data Flow

1. **Data Pull**: External data fetched via pull scripts (`scripts/pull_*.py`)
2. **Data Clean**: Raw data cleaned and standardized (`scripts/clean_*.py`)
3. **Analysis**: Jupyter notebooks for exploratory analysis
4. **Dashboard**: HTML report generated (`scripts/generate_html_report.py`)
5. **Deploy**: GitHub Actions automated deployment to GitHub Pages

### Technology Stack

- **Language**: Python 3.11+
- **Visualization**: Plotly.js (interactive charts)
- **Deployment**: GitHub Pages with GitHub Actions
- **Offline Support**: Service worker for offline viewing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Notes

- Data files are stored in `data/` and excluded from git
- Output files are generated in `output/` and excluded from git
- Use the shared library (`generate_html_report_lib.py`) for common functions

## 📋 TODO

See [`plans/TODO.md`](plans/TODO.md) for the full project roadmap and current status.

## 📖 Documentation

- [Data Explainer](guides/data_explainer.md) - Understanding the data sources
- [Financial Data Pipeline Guide](guides/financial_data_pipeline_guide.md) - How the pipeline works

## ⚖️ License

This project is for educational and research purposes. Data sources are subject to their respective licenses.

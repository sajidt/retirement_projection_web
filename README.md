# Retirement Projection Web

A browser-based retirement projection app built with Streamlit and Plotly. It reproduces the same portfolio analysis and projections as the original `retirement_projection` project, with modern charts and interactive UI.

## Features

- Portfolio total value and asset allocation analysis
- Expense ratio and portfolio allocation breakdown
- Future value projection with consumption scenarios
- Annual expense capacity chart
- Investment table with per-holding values
- Toggle between production and demo mode

## Run locally

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the app:
   ```bash
   streamlit run app.py
   ```

## Notes

- The app uses `yfinance` to fetch the latest security prices and USD/CAD conversion.
- Demo mode uses a fixed sample portfolio and local defaults.

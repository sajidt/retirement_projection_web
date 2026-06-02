import os
import re
from datetime import datetime, date

import streamlit as st
import plotly.graph_objects as go
import pandas as pd


def load_portfolio_history(directory: str) -> list:
    pattern = r'portfolio_output_(\d{8}_\d{6})\.txt'
    data = []

    if os.path.exists(directory):
        for filename in os.listdir(directory):
            match = re.match(pattern, filename)
            if match:
                filepath = os.path.join(directory, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        match_value = re.search(r'Total Investments = ([0-9,]+\.[0-9]{2})', content)
                        if match_value:
                            value_str = match_value.group(1).replace(',', '')
                            value = float(value_str)
                            date_str = match.group(1)
                            date_obj = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                            data.append((date_obj, value))
                except Exception as e:
                    st.error(f"Error reading {filename}: {e}")

    data.sort(key=lambda x: x[0])
    return data


def load_individual_investment_history(directory: str) -> dict:
    pattern = r'portfolio_output_(\d{8}_\d{6})\.txt'
    data_by_investment = {}

    if os.path.exists(directory):
        for filename in os.listdir(directory):
            match = re.match(pattern, filename)
            if match:
                filepath = os.path.join(directory, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        date_str = match.group(1)
                        date_obj = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                        investment_pattern = r'(.+?)\s+([A-Z0-9=\.]+):\s+(?:.*?)Market Value=\$([0-9,]+\.[0-9]{2})\s+CAD'
                        for inv_match in re.finditer(investment_pattern, content):
                            inv_name = inv_match.group(1).strip()
                            inv_ticker = inv_match.group(2).strip()
                            inv_value_str = inv_match.group(3).replace(',', '')
                            inv_value = float(inv_value_str)
                            inv_key = f"{inv_name} ({inv_ticker})"
                            if inv_key not in data_by_investment:
                                data_by_investment[inv_key] = []
                            data_by_investment[inv_key].append((date_obj, inv_value))
                except Exception as e:
                    st.error(f"Error reading {filename}: {e}")

    for inv_name in data_by_investment:
        data_by_investment[inv_name].sort(key=lambda x: x[0])

    return data_by_investment


def load_swr_history(directory: str) -> list:
    pattern = r'portfolio_output_(\d{8}_\d{6})\.txt'
    data = []

    if os.path.exists(directory):
        for filename in os.listdir(directory):
            match = re.match(pattern, filename)
            if match:
                filepath = os.path.join(directory, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        match_swr = re.search(r'125k with investment expenses = ([0-9,]+\.[0-9]{2})', content)
                        if match_swr:
                            swr_value_str = match_swr.group(1).replace(',', '')
                            swr_value = float(swr_value_str)
                            date_str = match.group(1)
                            date_obj = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                            data.append((date_obj, swr_value))
                except Exception as e:
                    st.error(f"Error reading {filename}: {e}")

    data.sort(key=lambda x: x[0])
    return data


def find_latest_prior_record(records: list[tuple[datetime, float]], cutoff_date: date):
    for dt, value in reversed(records):
        if dt.date() < cutoff_date:
            return dt, value
    return None


def build_holdings_previous_day_changes(holdings_df: pd.DataFrame, history_dir: str) -> pd.DataFrame:
    data_by_investment = load_individual_investment_history(history_dir)
    today = datetime.now().date()

    change_labels = []
    for _, row in holdings_df.iterrows():
        key = f"{row['Name']} ({row['Ticker']})"
        records = data_by_investment.get(key, [])
        prior_record = find_latest_prior_record(records, today)

        if prior_record is not None:
            _, prev_value = prior_record
            change = row['MarketValueCAD'] - prev_value
            pct = (change / prev_value * 100) if prev_value else 0.0
            sign = '+' if change > 0 else ''
            change_labels.append(f"{sign}${change:,.2f} ({sign}{pct:.2f}%)")
        else:
            change_labels.append("N/A")

    result = holdings_df.copy()
    result['Change vs Prior Day'] = change_labels
    return result


def render_investment_history_chart(directory: str) -> None:
    data = load_portfolio_history(directory)
    if not data:
        st.warning("No portfolio history data found.")
        return

    dates = [item[0] for item in data]
    values = [item[1] for item in data]
    initial_value = values[0]
    gains = [(v - initial_value) / initial_value * 100 for v in values]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=values,
        mode='lines+markers',
        name='Total Investments',
        line=dict(color='blue', width=2),
        marker=dict(size=6),
        hovertemplate='Date: %{x}<br>Value: %{y:,.2f} CAD<br>Gain: %{customdata:.2f}%<extra></extra>',
        customdata=gains
    ))
    fig.update_layout(
        title="Investment History",
        xaxis_title="Date",
        yaxis_title="Total Investments (CAD)",
        template="plotly_white"
    )
    st.plotly_chart(fig)


def render_individual_performance_chart(directory: str) -> None:
    data_by_investment = load_individual_investment_history(directory)
    if not data_by_investment:
        st.warning("No individual investment data found.")
        return

    investment = st.selectbox("Select Investment", sorted(data_by_investment.keys()), key="individual_inv")
    data = data_by_investment[investment]
    if not data:
        st.warning(f"No data for {investment}.")
        return

    dates = [item[0] for item in data]
    values = [item[1] for item in data]
    initial_value = values[0]
    gains = [(v - initial_value) / initial_value * 100 for v in values]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=values,
        mode='lines+markers',
        name=investment,
        line=dict(color='blue', width=2),
        marker=dict(size=6),
        hovertemplate=f'{investment}<br>Date: %{{x}}<br>Value: %{{y:,.2f}} CAD<br>Gain: %{{customdata:.2f}}%<extra></extra>',
        customdata=gains
    ))
    fig.update_layout(
        title=f"{investment} - Performance Over Time",
        xaxis_title="Date",
        yaxis_title="Investment Value (CAD)",
        template="plotly_white"
    )
    st.plotly_chart(fig)


def render_swr_trends_chart(directory: str, annual_spend: float) -> None:
    data = load_portfolio_history(directory)
    if not data:
        st.warning("No portfolio history data found.")
        return

    dates = [item[0] for item in data]
    swr_values = [(annual_spend / item[1]) * 100 for item in data]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=swr_values,
        mode='lines+markers',
        name='Safe Withdrawal Rate (%)',
        line=dict(color='blue', width=2),
        marker=dict(size=6)
    ))
    fig.add_hline(y=4.0, line_dash="dash", line_color="red", annotation_text="4% Rule")
    fig.add_hline(y=3.0, line_dash="dash", line_color="orange", annotation_text="3% Rule")

    fig.update_layout(
        title="Safe Withdrawal Rate Trends Over Time",
        xaxis_title="Date",
        yaxis_title="Safe Withdrawal Rate (%)",
        template="plotly_white"
    )
    st.plotly_chart(fig)


def render_history_tab(history_dir: str, annual_spend: float) -> None:
    st.markdown("### Historical Trend Charts")
    render_investment_history_chart(history_dir)
    render_individual_performance_chart(history_dir)
    render_swr_trends_chart(history_dir, annual_spend)

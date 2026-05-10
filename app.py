import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import re
from datetime import datetime, date
from pathlib import Path

from business_logic import (
    build_future_projection,
    calculate_allocations,
    calculate_projection_values,
    calculate_projection_values_80_percent,
    get_holdings_dataframe,
    get_currency_conversion,
    load_portfolio,
)
from ai import render_chat_interface, clear_chat_history


# Cache market data for 10 minutes to prevent refetches on every chat message
@st.cache_data(ttl=600)
def cached_get_currency_conversion(ticker: str) -> float:
    """Cached currency conversion with 10-minute TTL."""
    return get_currency_conversion(ticker)


@st.cache_data(ttl=600)
def cached_get_holdings_dataframe(portfolio_tuple: tuple, usd_cad: float, demo_mode: bool) -> pd.DataFrame:
    """Cached holdings dataframe with 10-minute TTL."""
    # Convert tuple of tuples back to list of dicts
    portfolio = [dict(item) for item in portfolio_tuple]
    return get_holdings_dataframe(portfolio, usd_cad)


def format_currency(value: float, currency: str = "CAD") -> str:
    return f"${value:,.2f} {currency}"


def render_summary_cards(portfolio_data: dict, usd_cad: float, delta: float = None) -> None:
    col1, col2, col3 = st.columns(3)
    col1.metric("Portfolio Value", format_currency(portfolio_data["total_investments"]), delta=delta)
    col2.metric("Net Expense Ratio", f"{portfolio_data['expense_ratio_net']:.2f}%")
    col3.metric("Weighted Return", f"{portfolio_data['weighted_average'] * 100:.2f}%")

    st.markdown(
        f"**USD/CAD Exchange Rate:** {usd_cad:.4f}  \
**Cash Total (CAD):** {format_currency(portfolio_data['total_cash'])}"
    )


def render_allocation_chart(portfolio_data: dict) -> None:
    allocation_labels = ["Cash", "US Stock", "Canadian Stock", "International Stock", "Bonds"]
    allocation_values = [
        portfolio_data["total_cash"],
        portfolio_data["total_domestic_stock"],
        portfolio_data["total_canadian_stock"],
        portfolio_data["total_intl_stock"],
        portfolio_data["total_bond"],
    ]
    fig = px.pie(
        values=allocation_values,
        names=allocation_labels,
        title="Asset Allocation",
        hole=0.45,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)


def render_projection_chart(portfolio_data: dict, years: int) -> None:
    start_value = portfolio_data["total_investments"]
    annual_return = portfolio_data["weighted_average"]
    years_index, no_withdrawal, consumption, pessimistic = build_future_projection(
        start_value, annual_return, years
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=years_index, y=no_withdrawal, mode="lines+markers", name="No Withdrawals"))
    fig.add_trace(
        go.Scatter(
            x=years_index,
            y=consumption,
            mode="lines+markers",
            name="2.5% Spending + 3% Inflation",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=years_index,
            y=pessimistic,
            mode="lines+markers",
            name="Pessimistic Return Scenario",
        )
    )
    fig.update_layout(
        title="Future Portfolio Value Projection",
        xaxis_title="Year",
        yaxis_title="Portfolio Value (CAD)",
        template="plotly_white",
        legend_title="Scenario",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_withdrawal_table(portfolio_data: dict) -> None:
    values = calculate_projection_values(portfolio_data["total_investments"], portfolio_data["expense_ratio_net"])
    values_80 = calculate_projection_values_80_percent(portfolio_data["total_investments"], portfolio_data["expense_ratio_net"])

    scenarios = ["2.0%", "2.5%", "3.0%", "3.5%", "4.0%", "125k%"]
    annual_amounts = [
        values["2.0%"],
        values["2.5%"],
        values["3.0%"],
        values["3.5%"],
        values["4.0%"],
        values["125k"],
    ]
    eighty_percent_amounts = [
        values_80["2.5%"],
        values_80["3.0%"],
        values_80["3.5%"],
        values_80["4.0%"],
        None,
        values_80["125k"],
    ]

    show_80 = st.checkbox("Show 80% Portfolio Annual Amount", value=False)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=scenarios,
        y=annual_amounts,
        name="Annual Amount (CAD)",
        marker_color='blue',
        hovertemplate='%{y:,.2f} CAD<extra></extra>'
    ))

    if show_80:
        # Filter out None values for 80%
        eighty_scenarios = [s for s, v in zip(scenarios, eighty_percent_amounts) if v is not None]
        eighty_values = [v for v in eighty_percent_amounts if v is not None]

        fig.add_trace(go.Bar(
            x=eighty_scenarios,
            y=eighty_values,
            name="80% Portfolio Annual Amount (CAD)",
            marker_color='orange',
            hovertemplate='%{y:,.2f} CAD<extra></extra>'
        ))

    fig.update_layout(
        title="Withdrawal Capacity and Portfolio Efficiency",
        xaxis_title="Scenario",
        yaxis_title="Amount (CAD)",
        barmode='group'
    )
    st.plotly_chart(fig)


def format_holdings_df(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    formatted["Price"] = formatted["Price"].map(lambda x: f"${x:,.2f}")
    formatted["MarketValueCAD"] = formatted["MarketValueCAD"].map(lambda x: f"${x:,.2f}")
    formatted["MarketValueUSD"] = formatted["MarketValueUSD"].map(lambda x: f"${x:,.2f}")
    if "Change vs Prior Day" in formatted.columns:
        formatted["Change vs Prior Day"] = formatted["Change vs Prior Day"].fillna("N/A")
    formatted["ExpenseRatio"] = formatted["ExpenseRatio"].map(lambda x: f"{x:.2f}%")
    formatted["LTReturn"] = formatted["LTReturn"].map(lambda x: f"{x:.2f}%")
    return formatted


def render_holdings_table(df: pd.DataFrame) -> None:
    formatted = format_holdings_df(df)
    if "Change vs Prior Day" in formatted.columns:
        def color_change(value):
            if isinstance(value, str):
                if value.startswith("+"):
                    return f"<span style='color:green'>{value}</span>"
                if value.startswith("$-") or value.strip().startswith("-"):
                    return f"<span style='color:red'>{value}</span>"
            return value

        formatted["Change vs Prior Day"] = formatted["Change vs Prior Day"].map(color_change)
        st.markdown(formatted.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.dataframe(formatted)


def get_default_history_directory(demo_mode: bool) -> str:
    """Get the default history directory based on demo_mode."""
    if demo_mode:
        demo_data_dir = Path(__file__).resolve().parent.parent / "retirement_projection" / "demo_data"
        demo_data_dir.mkdir(parents=True, exist_ok=True)
        return str(demo_data_dir)
    else:
        return r'C:\Personal\personal\Finance and Taxes\investment_saves'


def load_portfolio_history(directory: str) -> list:
    """
    Load all portfolio output files from directory.
    
    Args:
        directory: Path to directory containing portfolio_output_*.txt files
        
    Returns:
        List of tuples (datetime, value) sorted by date
    """
    pattern = r'portfolio_output_(\d{8}_\d{6})\.txt'
    data = []
    
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


def get_previous_portfolio_history_value(history: list[tuple[datetime, float]]) -> tuple[datetime, float] | None:
    """Return the latest prior portfolio history entry, ignoring same-day saves if today has saved data."""
    if not history:
        return None

    today = datetime.now().date()
    if history[-1][0].date() == today:
        for dt, value in reversed(history):
            if dt.date() < today:
                return dt, value
        return None

    return history[-1]


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


def load_individual_investment_history(directory: str) -> dict:
    """
    Load individual investment performance data from history files.
    
    Args:
        directory: Path to portfolio files
        
    Returns:
        Dict mapping investment names with tickers to list of (datetime, value) tuples
    """
    pattern = r'portfolio_output_(\d{8}_\d{6})\.txt'
    data_by_investment = {}
    
    for filename in os.listdir(directory):
        match = re.match(pattern, filename)
        if match:
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    date_str = match.group(1)
                    date_obj = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                    
                    # Extract individual investment values
                    investment_pattern = r'(.+?)\s+([A-Z0-9=\.]+):\s+(?:.*?)Market Value=\$([0-9,]+\.[0-9]{2})\s+CAD'
                    for inv_match in re.finditer(investment_pattern, content):
                        inv_name = inv_match.group(1).strip()
                        inv_ticker = inv_match.group(2).strip()
                        inv_value_str = inv_match.group(3).replace(',', '')
                        inv_value = float(inv_value_str)
                        
                        # Use "Name (TICKER)" as key
                        inv_key = f"{inv_name} ({inv_ticker})"
                        
                        if inv_key not in data_by_investment:
                            data_by_investment[inv_key] = []
                        data_by_investment[inv_key].append((date_obj, inv_value))
            except Exception as e:
                st.error(f"Error reading {filename}: {e}")
    
    # Sort each investment's data by date
    for inv_name in data_by_investment:
        data_by_investment[inv_name].sort(key=lambda x: x[0])
    
    return data_by_investment


def load_swr_history(directory: str) -> list:
    """
    Load SWR data from history files.
    
    Args:
        directory: Path to portfolio files
        
    Returns:
        List of tuples (datetime, swr_value) sorted by date
    """
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
                        # Extract "125k with investment expenses" value
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


def build_portfolio_export_text(
    usd_cad: float,
    usd_cad_ticker: str,
    holdings_df: pd.DataFrame,
    cash_cad: float,
    cash_usd: float,
    portfolio_data: dict,
) -> str:
    """Build the exact portfolio export text in the saved file format."""
    lines = []
    lines.append(f"Currency {usd_cad_ticker} = ${usd_cad:,.2f}")

    for _, row in holdings_df.iterrows():
        lines.append(
            f"{row['Name']} {row['Ticker']}: Price: ${row['Price']:,.2f} {row['Currency']}: "
            f"Market Value=${row['MarketValueCAD']:,.2f} CAD (${row['MarketValueUSD']:,.2f} USD)"
        )

    lines.append("")
    lines.append(f"Cash = ${cash_cad:,.2f} CAD")
    lines.append(f"Cash = ${cash_usd:,.2f} USD")

    for _, row in holdings_df.iterrows():
        lines.append(
            f"{row['Ticker']}: ${row['MarketValueCAD']:,.2f} : {row['ExpenseRatio']:.2f}%"
        )

    lines.append("")
    lines.append(f"Investment Expense = ${portfolio_data['investment_expense']:,.2f} CAD")
    lines.append(f"Net Expense Ratio = {portfolio_data['expense_ratio_net']:.2f}%")
    lines.append("")

    total = portfolio_data['total_investments']
    lines.append(f"Total Investments = {total:,.2f} CAD")
    lines.append("")

    lines.append(
        f"Total Cash = ${portfolio_data['total_cash']:,.2f} CAD : %Cash = "
        f"{(portfolio_data['total_cash'] / total * 100) if total else 0.0:.2f}%"
    )
    lines.append(
        f"Total International Stock = ${portfolio_data['total_intl_stock']:,.2f} CAD : %Intl = "
        f"{(portfolio_data['total_intl_stock'] / total * 100) if total else 0.0:.2f}%"
    )
    lines.append(
        f"Total Canadian Stock = ${portfolio_data['total_canadian_stock']:,.2f} CAD :  %Canada = "
        f"{(portfolio_data['total_canadian_stock'] / total * 100) if total else 0.0:.2f}%"
    )
    lines.append(
        f"Total US Stock = ${portfolio_data['total_domestic_stock']:,.2f} CAD :  %US = "
        f"{(portfolio_data['total_domestic_stock'] / total * 100) if total else 0.0:.2f}%"
    )
    lines.append(
        f"Total Bond = ${portfolio_data['total_bond']:,.2f} CAD : %Bond = "
        f"{(portfolio_data['total_bond'] / total * 100) if total else 0.0:.2f}%"
    )
    lines.append("")

    withdrawal_values = calculate_projection_values(total, portfolio_data['expense_ratio_net'])
    lines.append(f"2.0% of Total = ${withdrawal_values['2.0%']:,.2f} CAD")
    lines.append(f"2.5% of Total = ${withdrawal_values['2.5%']:,.2f} CAD")
    lines.append(f"3.0% of Total = ${withdrawal_values['3.0%']:,.2f} CAD")
    lines.append(f"3.5% of Total = ${withdrawal_values['3.5%']:,.2f} CAD")
    lines.append(f"4.0% of Total = ${withdrawal_values['4.0%']:,.2f} CAD")
    lines.append(f"125k with investment expenses = {withdrawal_values['125k']:.2f}")
    lines.append("")
    lines.append(
        f"Total Expected Weighted Average Return of Investments = "
        f"{portfolio_data['weighted_average'] * 100:.2f}%"
    )
    lines.append("")

    eighty_values = calculate_projection_values_80_percent(total, portfolio_data['expense_ratio_net'])
    lines.append(f"80% of Total = ${total * 0.8:,.2f} CAD")
    lines.append(f"2.5% of Total = ${eighty_values['2.5%']:,.2f} CAD")
    lines.append(f"3.0% of Total = ${eighty_values['3.0%']:,.2f} CAD")
    lines.append(f"3.5% of Total = ${eighty_values['3.5%']:,.2f} CAD")
    lines.append(f"4.0% of Total = ${eighty_values['4.0%']:,.2f} CAD")
    lines.append(f"125k with investment expenses = {eighty_values['125k']:.2f}")

    return "\n".join(lines)


def save_portfolio_export(directory: str, export_text: str) -> str:
    """Save the export text to a timestamped file in the target directory."""
    os.makedirs(directory, exist_ok=True)
    filename = f"portfolio_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(directory, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(export_text)
    return filepath


def render_investment_history_chart(directory: str) -> None:
    """Render the overall investment history chart."""
    data = load_portfolio_history(directory)
    
    if not data:
        st.warning("No portfolio history data found.")
        return
    
    dates = [item[0] for item in data]
    values = [item[1] for item in data]
    
    # Calculate percentage gains
    initial_value = values[0]
    gains = [(v - initial_value) / initial_value * 100 for v in values]
    
    # Create segments for percentage gain coloring
    segments = []
    current_segment = {'dates': [], 'gains': [], 'color': None}
    for i in range(len(gains)):
        color = 'green' if gains[i] >= 0 else 'red'
        if current_segment['color'] != color:
            if current_segment['dates']:
                segments.append(current_segment)
            current_segment = {'dates': [dates[i]], 'gains': [gains[i]], 'color': color}
        else:
            current_segment['dates'].append(dates[i])
            current_segment['gains'].append(gains[i])
    if current_segment['dates']:
        segments.append(current_segment)
    
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
    
    for segment in segments:
        fig.add_trace(go.Scatter(
            x=segment['dates'],
            y=segment['gains'],
            mode='lines',
            line=dict(color=segment['color'], width=2),
            showlegend=False,
            yaxis='y2'
        ))
    
    fig.update_layout(
        title="Investment History",
        xaxis_title="Date",
        yaxis_title="Total Investments (CAD)",
        yaxis2=dict(
            title="Percentage Gain (%)",
            overlaying='y',
            side='right'
        ),
        template="plotly_white"
    )
    st.plotly_chart(fig)


def render_individual_performance_chart(directory: str) -> None:
    """Render individual investment performance chart with selector."""
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
    
    # Calculate percentage gains
    initial_value = values[0]
    gains = [(v - initial_value) / initial_value * 100 for v in values]
    
    # Create segments for percentage gain coloring
    segments = []
    current_segment = {'dates': [], 'gains': [], 'color': None}
    for i in range(len(gains)):
        color = 'green' if gains[i] >= 0 else 'red'
        if current_segment['color'] != color:
            if current_segment['dates']:
                segments.append(current_segment)
            current_segment = {'dates': [dates[i]], 'gains': [gains[i]], 'color': color}
        else:
            current_segment['dates'].append(dates[i])
            current_segment['gains'].append(gains[i])
    if current_segment['dates']:
        segments.append(current_segment)
    
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
    
    for segment in segments:
        fig.add_trace(go.Scatter(
            x=segment['dates'],
            y=segment['gains'],
            mode='lines',
            line=dict(color=segment['color'], width=2),
            showlegend=False,
            yaxis='y2'
        ))
    
    fig.update_layout(
        title=f"{investment} - Performance Over Time",
        xaxis_title="Date",
        yaxis_title="Investment Value (CAD)",
        yaxis2=dict(
            title="Percentage Gain (%)",
            overlaying='y',
            side='right'
        ),
        template="plotly_white"
    )
    st.plotly_chart(fig)


def render_swr_trends_chart(directory: str, annual_spend: float) -> None:
    """Render Safe Withdrawal Rate trends chart based on annual spend."""
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


def render_future_swr_projection_chart(start_value: float, current_annual_spend: float, annual_return: float, years: int) -> None:
    """Render a future annual SWR projection based on projected net worth."""
    if years <= 0:
        st.warning("Projection horizon must be greater than zero.")
        return

    year_labels = [datetime.now().year + i + 1 for i in range(years)]
    annual_spends = []
    future_net_worth = []
    balance = start_value
    spend = current_annual_spend

    for _ in range(years):
        annual_spends.append(spend)
        balance = balance * (1 + annual_return) - spend
        future_net_worth.append(balance)
        spend *= 1.03

    swr_projection = [
        (annual_spends[i] / future_net_worth[i]) * 100 if future_net_worth[i] > 0 else None
        for i in range(years)
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=year_labels,
        y=swr_projection,
        mode='lines+markers',
        name='Future SWR Projection',
        line=dict(color='green', width=2),
        marker=dict(size=6)
    ))
    fig.add_trace(go.Scatter(
        x=year_labels,
        y=future_net_worth,
        mode='lines+markers',
        name='Future Net Worth',
        line=dict(color='blue', width=2, dash='dash'),
        marker=dict(size=6),
        yaxis='y2'
    ))

    fig.update_layout(
        title="Future Annual SWR Projection",
        xaxis_title="Year",
        yaxis=dict(title="Projected SWR (%)"),
        yaxis2=dict(
            title="Future Net Worth (CAD)",
            overlaying='y',
            side='right',
            tickformat=',.0f'
        ),
        template="plotly_white"
    )
    st.plotly_chart(fig)


def main():
    st.set_page_config(page_title="Retirement Projection Web", layout="wide")
    st.title("Retirement Projection Web")
    st.markdown(
        "A browser-based retirement portfolio dashboard with modern analytics, interactive charts, and the same projection logic as the original desktop app."
    )

    aside = st.sidebar
    aside.header("Settings")
    demo_mode = aside.checkbox("Demo mode", value=False)
    use_future = aside.checkbox("Include future cash", value=False)
    future_amount = aside.number_input("Future contribution amount (CAD)", min_value=0.0, value=500000.0, step=10000.0)
    projection_years = aside.slider("Projection horizon (years)", min_value=5, max_value=40, value=20)
    show_investment_details = aside.checkbox("Show investment holdings", value=True)
    annual_spend = aside.number_input("Current Annual Spend (CAD)", min_value=0.0, value=125000.0, step=1000.0)
    age = aside.number_input("Your Age", min_value=18, max_value=120, value=60, step=1)

    holdings, cash_cad, cash_usd, future_value, ticker = load_portfolio(demo_mode)

    if use_future:
        future_value = future_amount

    with st.spinner("Fetching market data..."):
        usd_cad = cached_get_currency_conversion(ticker)
        holdings_df = cached_get_holdings_dataframe(tuple(tuple(d.items()) for d in holdings), usd_cad, demo_mode)
        portfolio_data = calculate_allocations(holdings_df, cash_cad, cash_usd, usd_cad, future_value, use_future)

    history_dir = get_default_history_directory(demo_mode)
    history = load_portfolio_history(history_dir)
    previous_entry = get_previous_portfolio_history_value(history)

    if previous_entry is not None:
        _, previous_value = previous_entry
        diff = portfolio_data["total_investments"] - previous_value
        diff_pct = (diff / previous_value * 100) if previous_value else 0.0
        if diff > 0:
            sign = '+'
            delta = f"{sign}{format_currency(diff)} ({sign}{diff_pct:.2f}%)"
        else:
            delta = f"-{format_currency(abs(diff))} ({diff_pct:.2f}%)"
    else:
        delta = None

    holdings_df = build_holdings_previous_day_changes(holdings_df, history_dir)

    # Create tabs for Dashboard and AI Advisor
    tab_dashboard, tab_ai = st.tabs(["📊 Dashboard", "🤖 AI Financial Advisor"])

    with tab_dashboard:
        render_summary_cards(portfolio_data, usd_cad, delta)
        render_allocation_chart(portfolio_data)
        render_projection_chart(portfolio_data, projection_years)
        render_withdrawal_table(portfolio_data)

        save_dir = history_dir
        if st.sidebar.button("Save Current Values"):
            export_text = build_portfolio_export_text(
                usd_cad,
                ticker,
                holdings_df,
                cash_cad,
                cash_usd,
                portfolio_data,
            )
            saved_path = save_portfolio_export(save_dir, export_text)
            st.sidebar.success(f"Saved portfolio to {saved_path}")

        st.markdown("### Historical Trends")
        render_investment_history_chart(history_dir)
        render_individual_performance_chart(history_dir)
        render_swr_trends_chart(history_dir, annual_spend)
        st.markdown("### Future SWR Projection")
        render_future_swr_projection_chart(
            portfolio_data["total_investments"],
            annual_spend,
            portfolio_data["weighted_average"],
            projection_years,
        )

        if show_investment_details:
            st.markdown("### Investment Holdings")
            render_holdings_table(holdings_df)

    with tab_ai:
        col1, col2 = st.columns([1, 10])
        with col1:
            if st.button("🔄 Clear Chat", key="clear_chat"):
                clear_chat_history()
                st.rerun()
        
        render_chat_interface(
            portfolio_data=portfolio_data,
            cash_cad=cash_cad,
            cash_usd=cash_usd,
            age=age,
            annual_spend=annual_spend,
            holdings_df=holdings_df
        )

    st.sidebar.markdown("---")
    st.sidebar.markdown("Built for browser-first retirement planning.")


if __name__ == "__main__":
    main()

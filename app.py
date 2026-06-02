import streamlit as st
import pandas as pd
import os
from datetime import datetime
from pathlib import Path

from business_logic import (
    calculate_allocations,
    calculate_projection_values,
    calculate_projection_values_80_percent,
    get_holdings_dataframe,
    get_currency_conversion,
    load_portfolio,
)
from ai import render_chat_interface, clear_chat_history
from ui_dashboard import render_dashboard_tab
from ui_allocation import render_allocation_tab
from ui_history import load_portfolio_history, build_holdings_previous_day_changes, render_history_tab
from ui_projection import render_projection_tab


# Cache market data for 10 minutes to prevent refetches on every chat message
@st.cache_data(ttl=600)
def cached_get_currency_conversion(ticker: str) -> float:
    """Cached currency conversion with 10-minute TTL."""
    return get_currency_conversion(ticker)


@st.cache_data(ttl=600)
def cached_get_holdings_dataframe(portfolio_tuple: tuple, usd_cad: float, demo_mode: bool) -> pd.DataFrame:
    """Cached holdings dataframe with 10-minute TTL."""
    portfolio = [dict(item) for item in portfolio_tuple]
    return get_holdings_dataframe(portfolio, usd_cad)


def get_default_history_directory(demo_mode: bool) -> str:
    if demo_mode:
        demo_data_dir = Path(__file__).resolve().parent.parent / "retirement_projection" / "demo_data"
        demo_data_dir.mkdir(parents=True, exist_ok=True)
        return str(demo_data_dir)
    else:
        return r'C:\Personal\personal\Finance and Taxes\investment_saves'


def build_portfolio_export_text(
    usd_cad: float,
    usd_cad_ticker: str,
    holdings_df: pd.DataFrame,
    cash_cad: float,
    cash_usd: float,
    portfolio_data: dict,
) -> str:
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


def get_previous_portfolio_history_value(history: list[tuple[datetime, float]]) -> tuple[datetime, float] | None:
    if not history:
        return None

    today = datetime.now().date()
    latest = history[-1]
    if latest[0].date() < today:
        return latest

    for dt, value in reversed(history[:-1]):
        if dt.date() < today:
            return dt, value

    return None


def save_portfolio_export(directory: str, export_text: str) -> str:
    os.makedirs(directory, exist_ok=True)
    filename = f"portfolio_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(directory, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(export_text)
    return filepath


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
        sign = '+' if diff > 0 else ''
        delta = f"{sign}{diff:,.2f} CAD ({sign}{diff_pct:.2f}%)"
    else:
        delta = None

    holdings_df = build_holdings_previous_day_changes(holdings_df, history_dir)

    tab_dashboard, tab_history, tab_allocation, tab_projection, tab_ai = st.tabs([
        "📊 Dashboard",
        "📈 Historical Trends",
        "🎯 Asset Allocation",
        "🔮 Future Projection",
        "🤖 AI Financial Advisor",
    ])

    with tab_dashboard:
        render_dashboard_tab(
            portfolio_data=portfolio_data,
            usd_cad=usd_cad,
            delta=delta,
            holdings_df=holdings_df,
            show_investment_details=show_investment_details,
        )

        save_dir = history_dir
        if aside.button("Save Current Values"):
            export_text = build_portfolio_export_text(
                usd_cad,
                ticker,
                holdings_df,
                cash_cad,
                cash_usd,
                portfolio_data,
            )
            saved_path = save_portfolio_export(save_dir, export_text)
            aside.success(f"Saved portfolio to {saved_path}")

    with tab_history:
        render_history_tab(history_dir, annual_spend)

    with tab_allocation:
        render_allocation_tab(portfolio_data)

    with tab_projection:
        render_projection_tab(portfolio_data, projection_years, annual_spend)

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
            holdings_df=holdings_df,
        )

    st.sidebar.markdown("---")
    st.sidebar.markdown("Built for browser-first retirement planning.")


if __name__ == "__main__":
    main()

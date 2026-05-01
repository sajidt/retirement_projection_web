import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from business_logic import (
    build_future_projection,
    calculate_allocations,
    calculate_projection_values,
    calculate_projection_values_80_percent,
    get_holdings_dataframe,
    get_currency_conversion,
    load_portfolio,
)


def format_currency(value: float, currency: str = "CAD") -> str:
    return f"${value:,.2f} {currency}"


def render_summary_cards(portfolio_data: dict, usd_cad: float, use_future: bool, future_amount: float) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Portfolio Value", format_currency(portfolio_data["total_investments"]), delta=None)
    col2.metric("Net Expense Ratio", f"{portfolio_data['expense_ratio_net']:.2f}%")
    col3.metric("Weighted Return", f"{portfolio_data['weighted_average'] * 100:.2f}%")
    delta = format_currency(future_amount) if use_future else "Disabled"
    col4.metric("Future Contributions", delta)

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

    projection_df = pd.DataFrame(
        {
            "Scenario": ["2.0%", "2.5%", "3.0%", "3.5%", "4.0%", "125k%"],
            "Annual Amount (CAD)": [
                values["2.0%"],
                values["2.5%"],
                values["3.0%"],
                values["3.5%"],
                values["4.0%"],
                values["125k"],
            ],
            "80% Portfolio Annual Amount (CAD)": [
                values_80["2.5%"],
                values_80["3.0%"],
                values_80["3.5%"],
                values_80["4.0%"],
                None,
                values_80["125k"],
            ],
        }
    )

    st.markdown("### Withdrawal Capacity and Portfolio Efficiency")
    st.dataframe(projection_df.style.format({"Annual Amount (CAD)": "${:,.2f}", "80% Portfolio Annual Amount (CAD)": "${:,.2f}"}))


def format_holdings_df(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    formatted["Price"] = formatted["Price"].map(lambda x: f"${x:,.2f}")
    formatted["MarketValueCAD"] = formatted["MarketValueCAD"].map(lambda x: f"${x:,.2f}")
    formatted["MarketValueUSD"] = formatted["MarketValueUSD"].map(lambda x: f"${x:,.2f}")
    formatted["ExpenseRatio"] = formatted["ExpenseRatio"].map(lambda x: f"{x:.2f}%")
    formatted["LTReturn"] = formatted["LTReturn"].map(lambda x: f"{x:.2f}%")
    return formatted


def main():
    st.set_page_config(page_title="Retirement Projection Web", layout="wide")
    st.title("Retirement Projection Web")
    st.markdown(
        "A browser-based retirement portfolio dashboard with modern analytics, interactive charts, and the same projection logic as the original desktop app."
    )

    aside = st.sidebar
    aside.header("Settings")
    demo_mode = aside.checkbox("Demo mode", value=False)
    use_future = aside.checkbox("Include future cash", value=True)
    future_amount = aside.number_input("Future contribution amount (CAD)", min_value=0.0, value=500000.0, step=10000.0)
    projection_years = aside.slider("Projection horizon (years)", min_value=5, max_value=40, value=20)
    show_investment_details = aside.checkbox("Show investment holdings", value=True)

    holdings, cash_cad, cash_usd, future_value, ticker = load_portfolio(demo_mode)

    if use_future:
        future_value = future_amount

    with st.spinner("Fetching market data..."):
        usd_cad = get_currency_conversion(ticker)
        holdings_df = get_holdings_dataframe(holdings, usd_cad)
        portfolio_data = calculate_allocations(holdings_df, cash_cad, cash_usd, usd_cad, future_value, use_future)

    render_summary_cards(portfolio_data, usd_cad, use_future, future_value)
    render_allocation_chart(portfolio_data)
    render_projection_chart(portfolio_data, projection_years)
    render_withdrawal_table(portfolio_data)

    if show_investment_details:
        st.markdown("### Investment Holdings")
        st.dataframe(format_holdings_df(holdings_df))

    st.sidebar.markdown("---")
    st.sidebar.markdown("Built for browser-first retirement planning.")


if __name__ == "__main__":
    main()

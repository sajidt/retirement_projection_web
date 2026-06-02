import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Optional

from business_logic import calculate_projection_values, calculate_projection_values_80_percent


def format_currency(value: float, currency: str = "CAD") -> str:
    return f"${value:,.2f} {currency}"


def render_summary_cards(portfolio_data: dict, usd_cad: float, delta: Optional[str] = None) -> None:
    col1, col2, col3 = st.columns(3)
    col1.metric("Portfolio Value", format_currency(portfolio_data["total_investments"]), delta=delta)
    col2.metric("Net Expense Ratio", f"{portfolio_data['expense_ratio_net']:.2f}%")
    col3.metric("Weighted Return", f"{portfolio_data['weighted_average'] * 100:.2f}%")

    st.markdown(
        f"**USD/CAD Exchange Rate:** {usd_cad:.4f}  \\n**Cash Total (CAD):** {format_currency(portfolio_data['total_cash'])}"
    )


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


def render_dashboard_tab(
    portfolio_data: dict,
    usd_cad: float,
    delta: Optional[str],
    holdings_df: pd.DataFrame,
    show_investment_details: bool,
) -> None:
    render_summary_cards(portfolio_data, usd_cad, delta)
    render_withdrawal_table(portfolio_data)

    if show_investment_details:
        st.markdown("### Investment Holdings")
        render_holdings_table(holdings_df)

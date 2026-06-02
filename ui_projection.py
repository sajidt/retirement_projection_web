import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

from business_logic import build_future_projection


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


def render_future_swr_projection_chart(start_value: float, current_annual_spend: float, annual_return: float, years: int) -> None:
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
        mode="lines+markers",
        name="Future SWR Projection",
        line=dict(color="green", width=2),
        marker=dict(size=6)
    ))
    fig.add_trace(go.Scatter(
        x=year_labels,
        y=future_net_worth,
        mode="lines+markers",
        name="Future Net Worth",
        line=dict(color="blue", width=2, dash="dash"),
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
    st.plotly_chart(fig, use_container_width=True)


def render_projection_tab(portfolio_data: dict, projection_years: int, annual_spend: float) -> None:
    render_projection_chart(portfolio_data, projection_years)
    st.markdown("---")
    render_future_swr_projection_chart(
        portfolio_data["total_investments"],
        annual_spend,
        portfolio_data["weighted_average"],
        projection_years,
    )

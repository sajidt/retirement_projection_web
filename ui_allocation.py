import streamlit as st
import plotly.express as px


def render_allocation_tab(portfolio_data: dict) -> None:
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

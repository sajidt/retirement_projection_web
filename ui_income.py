import pandas as pd
import streamlit as st


def build_investment_income_df(
    holdings_df: pd.DataFrame, usd_cad: float, yield_values: pd.Series | None = None
) -> tuple[pd.DataFrame, float, float, dict[str, float]]:
    yield_source = holdings_df["Yield"] if yield_values is None else pd.Series(
        yield_values.to_numpy(), index=holdings_df.index
    )
    dividend_yield = pd.to_numeric(yield_source, errors="coerce")
    prices = pd.to_numeric(holdings_df["Price"], errors="coerce").fillna(0.0)
    quantities = pd.to_numeric(holdings_df["Quantity"], errors="coerce").fillna(0.0)
    income = dividend_yield.fillna(0.0).div(100) * prices * quantities
    is_usd = holdings_df["Currency"].fillna("").str.upper().eq("USD")
    income_cad = income.where(~is_usd, income * usd_cad)
    account_types = holdings_df.get(
        "AccountType", pd.Series("Unassigned", index=holdings_df.index)
    ).fillna("Unassigned")
    income_by_account = income_cad.groupby(account_types).sum().to_dict()

    income_df = pd.DataFrame({
        "Ticker": holdings_df["Ticker"],
        "Name": holdings_df["Name"],
        "Account Type": account_types,
        "Yield": dividend_yield,
        "Qty": quantities,
        "Price": prices,
        "Income (CAD)": income_cad,
        "Currency": holdings_df["Currency"],
    })
    income_df["Price"] = income_df.apply(
        lambda row: f"${row['Price']:,.2f} {row['Currency']}", axis=1
    )
    income_df["Yield"] = income_df["Yield"].map(
        lambda value: f"{value:.2f}%" if pd.notna(value) else "N/A"
    )
    income_df["Income (CAD)"] = income_df["Income (CAD)"].map(
        lambda value: f"${value:,.2f} CAD"
    )
    income_df.drop(columns="Currency", inplace=True)

    total_income = float(income_cad.sum())
    total_market_value = float(holdings_df["MarketValueCAD"].sum())
    weighted_yield = total_income / total_market_value * 100 if total_market_value else 0.0
    return income_df, total_income, weighted_yield, income_by_account


def render_investment_income_tab(holdings_df: pd.DataFrame, usd_cad: float) -> None:
    account_types = holdings_df.get(
        "AccountType", pd.Series("Unassigned", index=holdings_df.index)
    ).fillna("Unassigned")
    yield_editor_df = pd.DataFrame({
        "Ticker": holdings_df["Ticker"],
        "Name": holdings_df["Name"],
        "Account Type": account_types,
        "Yield (%)": pd.to_numeric(holdings_df["Yield"], errors="coerce"),
    })
    edited_yields = st.data_editor(
        yield_editor_df,
        key="investment_income_yields",
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["Ticker", "Name", "Account Type"],
        column_config={
            "Yield (%)": st.column_config.NumberColumn(
                "Yield (%)", min_value=0.0, step=0.01, format="%.2f%%"
            )
        },
    )
    income_df, total_income, weighted_yield, income_by_account = build_investment_income_df(
        holdings_df, usd_cad, edited_yields["Yield (%)"]
    )

    total_column, yield_column = st.columns(2)
    total_column.metric("Annual Investment Income", f"${total_income:,.2f} CAD")
    yield_column.metric("Weighted Portfolio Yield", f"{weighted_yield:.2f}%")
    account_columns = st.columns(3)
    for column, account_type in zip(account_columns, ("Non Registered", "RRSP", "401K")):
        column.metric(
            f"{account_type} Income",
            f"${income_by_account.get(account_type, 0.0):,.2f} CAD",
        )
    st.dataframe(income_df, use_container_width=True, hide_index=True)
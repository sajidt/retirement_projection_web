"""Retirement projection business logic for the web app."""

from datetime import datetime
from functools import lru_cache
from typing import List

import numpy as np
import pandas as pd
import yfinance as yf

from constants import CASH_CAD, CASH_USD, FUTURE, currency_ticker, investments
from demo_portfolio import CASH_CAD as DEMO_CASH_CAD, CASH_USD as DEMO_CASH_USD, FUTURE as DEMO_FUTURE, currency_ticker as DEMO_CURRENCY_TICKER, investments as DEMO_INVESTMENTS


@lru_cache(maxsize=16)
def get_currency_conversion(ticker: str) -> float:
    """Return the latest USD/CAD exchange rate."""
    ticker_data = yf.Ticker(ticker)
    info = ticker_data.get_fast_info()
    return float(info.last_price)


def load_portfolio(demo_mode: bool):
    """Return the active portfolio configuration."""
    if demo_mode:
        return DEMO_INVESTMENTS, DEMO_CASH_CAD, DEMO_CASH_USD, DEMO_FUTURE, DEMO_CURRENCY_TICKER

    return investments, CASH_CAD, CASH_USD, FUTURE, currency_ticker


def get_holdings_dataframe(portfolio: List[dict], usd_cad: float) -> pd.DataFrame:
    """Return a DataFrame of holdings with market values in CAD and USD."""
    rows = []
    for investment in portfolio:
        ticker = investment.get("Ticker", "")
        price = 0.0
        currency = investment.get("Currency", "CAD")
        if ticker:
            data = yf.Ticker(ticker)
            price = float(data.get_fast_info().last_price)

        market_value = price * investment.get("Quantity", 0)
        if currency.upper() == "USD":
            market_value_cad = market_value * usd_cad
        else:
            market_value_cad = market_value
        market_value_usd = market_value_cad / usd_cad

        rows.append({
            "Name": investment["Name"],
            "Ticker": ticker,
            "Currency": currency,
            "Quantity": investment["Quantity"],
            "Type": investment["Type"],
            "ExpenseRatio": investment["ExpenseRatio"],
            "LTReturn": investment["LTReturn"],
            "Price": price,
            "MarketValueCAD": market_value_cad,
            "MarketValueUSD": market_value_usd,
        })

    return pd.DataFrame(rows)


def calculate_allocations(df: pd.DataFrame, cash_cad: float, cash_usd: float, usd_cad: float, future_value: float, use_future: bool):
    """Compute allocation totals and portfolio metrics."""
    total_cash_value = cash_cad + cash_usd * usd_cad
    if use_future:
        total_cash_value += future_value

    type_totals = df.groupby("Type").MarketValueCAD.sum().to_dict()
    total_investments = df.MarketValueCAD.sum() + total_cash_value
    weighted_return = (df.MarketValueCAD * df.LTReturn).sum() / total_investments if total_investments else 0.0
    expense_value = (df.MarketValueCAD * df.ExpenseRatio / 100).sum()
    net_expense_ratio = expense_value / total_investments * 100 if total_investments else 0.0

    return {
        "total_investments": total_investments,
        "total_cash": total_cash_value,
        "total_domestic_stock": type_totals.get("StockD", 0.0),
        "total_canadian_stock": type_totals.get("StockC", 0.0),
        "total_intl_stock": type_totals.get("StockI", 0.0),
        "total_bond": type_totals.get("Bond", 0.0),
        "investment_expense": expense_value,
        "expense_ratio_net": net_expense_ratio,
        "weighted_average": weighted_return,
    }


def calculate_projection_values(total_value: float, expense_ratio: float):
    """Return conservative withdrawal values at common safe withdrawal rates."""
    return {
        "2.0%": total_value * 0.02,
        "2.5%": total_value * 0.025,
        "3.0%": total_value * 0.03,
        "3.5%": total_value * 0.035,
        "4.0%": total_value * 0.04,
        "125k": 125000 / total_value * 100 + expense_ratio if total_value else 0.0,
    }


def calculate_projection_values_80_percent(total_value: float, expense_ratio: float):
    """Return the same projection values assuming 80% of total value."""
    eighty_value = total_value * 0.80
    return {
        "80%": eighty_value,
        "2.5%": eighty_value * 0.025,
        "3.0%": eighty_value * 0.03,
        "3.5%": eighty_value * 0.035,
        "4.0%": eighty_value * 0.04,
        "125k": 125000 / eighty_value * 100 + expense_ratio if eighty_value else 0.0,
    }


def build_future_projection(start_value: float, annual_return: float, years: int, consumption_rate: float = 0.025, inflation_rate: float = 0.03):
    """Return future value curves for projection scenarios."""
    start_year = datetime.now().year
    timeline = np.arange(start_year, start_year + years + 1)

    no_withdrawal = start_value * (1 + annual_return) ** np.arange(years + 1)

    consumption_values = [start_value]
    balance = start_value
    annual_consumption = start_value * consumption_rate
    for _ in range(years):
        balance = balance * (1 + annual_return) - annual_consumption
        consumption_values.append(balance)
        annual_consumption *= 1 + inflation_rate

    pessimistic_return = max(annual_return - 0.03, 0.0)
    balance_pessimistic = start_value
    annual_consumption = start_value * consumption_rate
    pessimistic_values = [start_value]
    for _ in range(years):
        balance_pessimistic = balance_pessimistic * (1 + pessimistic_return) - annual_consumption
        pessimistic_values.append(balance_pessimistic)
        annual_consumption *= 1 + inflation_rate

    return timeline, no_withdrawal, consumption_values, pessimistic_values

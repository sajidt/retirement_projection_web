from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

MONTH_ORDER = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
MONTH_MAP = {month.lower(): month for month in MONTH_ORDER}
MONTH_MAP.update({month[:3].lower(): month for month in MONTH_ORDER})
MONTH_MAP["sept"] = "September"


def normalize_label(text: str) -> str:
    normalized = str(text).strip().lower()
    normalized = "".join(ch for ch in normalized if ch.isalnum() or ch.isspace())
    return " ".join(normalized.split())


def get_expense_excel_path() -> Path:
    return Path(r"C:\Personal\personal\Finance and Taxes\Annual Expense Spreadsheets\2026 Expenses.xlsx")


def load_annual_expenses(file_path: Path) -> tuple[pd.DataFrame, dict]:
    if not file_path.exists():
        raise FileNotFoundError(f"Expense workbook not found: {file_path}")

    df = pd.read_excel(file_path, sheet_name=0, header=None, engine="openpyxl")
    rows = []
    summary = {}
    summary_labels = {
        normalize_label("total spent ytd"): "Total Spent YTD",
        normalize_label("average monthly spend"): "Average Monthly Spend",
        normalize_label("average monthly spend remain"): "Average Monthly Spend Remain",
        normalize_label("average monthly spend remaining"): "Average Monthly Spend Remain",
        normalize_label("projected spend 2026"): "Projected Spend 2026",
    }

    for _, row in df.iterrows():
        label = row.iloc[0]
        if pd.isna(label):
            continue

        label = str(label).strip()
        key = label.lower().replace(".", "")
        month_name = MONTH_MAP.get(key)
        if month_name:
            amount = row.iloc[1]
            if pd.notna(amount):
                try:
                    rows.append((month_name, float(amount)))
                except (ValueError, TypeError):
                    continue

        for col_index in range(len(row) - 1):
            cell = row.iloc[col_index]
            if pd.isna(cell):
                continue
            cell_text = normalize_label(cell)
            label_name = summary_labels.get(cell_text)
            if label_name and label_name not in summary:
                # Prefer the first non-empty value to the right of the label cell.
                value = None
                for next_col in range(col_index + 1, len(row)):
                    next_value = row.iloc[next_col]
                    if pd.notna(next_value):
                        value = next_value
                        break

                if value is None:
                    continue

                try:
                    summary[label_name] = float(value)
                except (ValueError, TypeError):
                    summary[label_name] = value

    if not rows:
        raise ValueError("No monthly expense rows were found in the Excel workbook.")

    expense_df = pd.DataFrame(rows, columns=["Month", "Amount"])
    expense_df["Month"] = pd.Categorical(expense_df["Month"], categories=MONTH_ORDER, ordered=True)
    expense_df = expense_df.sort_values("Month").reset_index(drop=True)
    return expense_df, summary


def render_expense_tracker_tab() -> None:
    file_path = get_expense_excel_path()
    st.markdown("## Annual Expense Tracker")
    st.markdown(f"**Source file:** `{file_path}`")

    try:
        expense_df, summary_values = load_annual_expenses(file_path)
    except Exception as exc:
        st.error(str(exc))
        return

    st.metric(
        "Total Spent YTD",
        f"${summary_values.get('Total Spent YTD', 0):,.2f}",
    )
    st.metric(
        "Average Monthly Spend",
        f"${summary_values.get('Average Monthly Spend', 0):,.2f}",
    )
    st.metric(
        "Average Monthly Spend Remaining",
        f"${summary_values.get('Average Monthly Spend Remain', 0):,.2f}",
    )
    if "Projected Spend 2026" in summary_values:
        st.metric(
            "Projected Spend 2026",
            f"${summary_values.get('Projected Spend 2026', 0):,.2f}",
        )

    fig = px.bar(
        expense_df,
        x="Month",
        y="Amount",
        title="Monthly Expense Totals",
        labels={"Amount": "CAD", "Month": "Month"},
    )
    fig.update_layout(xaxis_tickangle=-45, template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

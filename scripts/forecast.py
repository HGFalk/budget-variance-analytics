"""
Revenue forecast for Brightwake Marine, by product line and month.

Reads the dbt output output/fct_pl_monthly.csv and writes
output/fct_revenue_forecast.csv for Power BI.

Two simple, explainable methods:
  seasonal_naive  next year's month = the same month last year
  seasonal_trend  the same month last year x growth of the last 12 months
                  vs the 12 months before

Backtest: train on 2023 to 2024, forecast 2025, compare with 2025 actuals.
The 2025 budget is also scored, because a budget is a forecast too.
Forecast: train on 2023 to 2025, forecast 2026 with the backtest winner.

Accuracy measure: MAPE, the average absolute error per month as a
percentage of actual revenue. Lower is better.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PL = ROOT / "output" / "fct_pl_monthly.csv"
OUT = ROOT / "output" / "fct_revenue_forecast.csv"

pl = pd.read_csv(PL, parse_dates=["month"])
revenue = (
    pl[pl["account_type"] == "Revenue"]
    .groupby(["scenario", "month", "account_name"], as_index=False)["pl_amount_nok"]
    .sum()
    .rename(columns={"account_name": "product_line", "pl_amount_nok": "revenue_nok"})
)
revenue["product_line"] = revenue["product_line"].str.replace("Sales revenue, ", "").str.capitalize()
actual = revenue[revenue["scenario"] == "actual"].drop(columns="scenario")
budget = revenue[revenue["scenario"] == "budget"].drop(columns="scenario")


def forecast(history: pd.DataFrame, year: int) -> pd.DataFrame:
    """Forecast every month of `year` from monthly history up to the year before."""
    rows = []
    for line, h in history.groupby("product_line"):
        h = h.set_index("month")["revenue_nok"].sort_index()
        last_year = h[h.index.year == year - 1]
        year_before = h[h.index.year == year - 2]
        growth = last_year.sum() / year_before.sum()
        for month, value in last_year.items():
            target = month + pd.DateOffset(years=1)
            rows.append((target, line, "seasonal_naive", value))
            rows.append((target, line, "seasonal_trend", value * growth))
    return pd.DataFrame(rows, columns=["month", "product_line", "method", "revenue_nok"])


def mape(pred: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame:
    m = pred.merge(truth, on=["month", "product_line"], suffixes=("", "_actual"))
    m["ape"] = (m["revenue_nok"] - m["revenue_nok_actual"]).abs() / m["revenue_nok_actual"]
    return m.groupby("method")["ape"].mean().rename("mape").reset_index()


# ---------------------------------------------------------------- backtest
history = actual[actual["month"].dt.year <= 2024]
truth_2025 = actual[actual["month"].dt.year == 2025]

backtest = forecast(history, 2025)
budget_as_forecast = budget.assign(method="budget")
scores = mape(pd.concat([backtest, budget_as_forecast]), truth_2025).sort_values("mape")

print("Backtest 2025, MAPE by method (lower is better)")
for _, r in scores.iterrows():
    print(f"  {r['method']:15s} {r['mape']:.1%}")

statistical = scores[scores["method"] != "budget"]
best = statistical.iloc[0]["method"]
print(f"\nBest statistical method: {best}")

# ---------------------------------------------------------------- forecast
future = forecast(actual, 2026)
future = future[future["method"] == best]

# ------------------------------------------------------------------- write
out = pd.concat(
    [
        actual.assign(series="Actual", purpose="history"),
        budget.assign(series="Budget", purpose="backtest"),
        backtest.assign(purpose="backtest").rename(columns={"method": "series"}),
        future.assign(purpose="forecast").rename(columns={"method": "series"}),
    ],
    ignore_index=True,
)[["month", "product_line", "series", "purpose", "revenue_nok"]]
out["revenue_nok"] = out["revenue_nok"].round(0).astype("int64")
out["month"] = out["month"].dt.strftime("%Y-%m-%d")
out.to_csv(OUT, index=False)

total_2026 = future["revenue_nok"].sum()
total_2025 = truth_2025["revenue_nok"].sum()
print(
    f"2026 revenue forecast: {total_2026 / 1e6:,.1f}M NOK "
    f"({total_2026 / total_2025 - 1:+.1%} vs 2025 actual)"
)
print(f"Wrote {OUT.relative_to(ROOT)} ({len(out):,} rows)")

"""
Generate synthetic finance data for Brightwake Marine AS (fictional).

Brightwake Marine sells marine spare parts, service hours and lubricants
in three regions and reports in NOK. The script writes:

  data/raw/dim_account.csv        chart of accounts
  data/raw/dim_cost_centre.csv    cost centres
  data/raw/dim_product_line.csv   product lines (unit, list price, unit cost)
  data/raw/dim_region.csv         regions
  data/raw/sales_actuals.csv      monthly quantity, revenue, COGS, Jan 2023 to Dec 2025
  data/raw/sales_budget.csv       same grain, budget for 2025
  data/raw/gl_actuals.csv         general ledger postings, Jan 2023 to Dec 2025
  data/raw/gl_budget.csv          general ledger budget, 2025

GL sign convention (as in a real ledger): revenue is a credit and stored
negative, costs are debits and stored positive. Staging flips the sign.

Planted 2025 variances (actual vs budget), the "known answers":
  1. Volume: spare parts quantity 6% below budget
  2. Price: realised prices 3% above budget on all product lines
  3. Mix:   service hours 8% above budget (high-margin line)
  4. Cost:  IT cost centre spend 15% above budget

The budget equals the expected value of the underlying process, so the
analysis should recover the planted effects up to random noise.
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)

OUT = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

MONTHS = pd.date_range("2023-01-01", "2025-12-01", freq="MS")
BUDGET_YEAR = 2025

# ---------------------------------------------------------------- dimensions
regions = pd.DataFrame(
    {
        "region_id": ["NO", "NORDIC", "ROE"],
        "region_name": ["Norway", "Nordics", "Rest of Europe"],
        "scale": [1.0, 0.7, 0.5],
    }
)

product_lines = pd.DataFrame(
    {
        "product_line_id": ["PARTS", "SERVICE", "LUBE"],
        "product_line_name": ["Spare parts", "Service hours", "Lubricants and consumables"],
        "unit": ["unit", "hour", "litre"],
        "base_qty_norway": [400, 2500, 60000],  # per month, 2023
        "list_price_2023": [12000.0, 1800.0, 45.0],  # NOK per unit
        "unit_cost_2023": [7800.0, 900.0, 38.0],  # NOK per unit
        "revenue_account": [3000, 3010, 3020],
        "cogs_account": [4000, 4010, 4020],
    }
)

cost_centres = pd.DataFrame(
    {
        "cost_centre_id": ["CC10", "CC20", "CC30", "CC40"],
        "cost_centre_name": ["Sales", "Service Operations", "Admin", "IT"],
    }
)

accounts = pd.DataFrame(
    [
        (3000, "Sales revenue, spare parts", "Revenue", "Revenue"),
        (3010, "Sales revenue, service hours", "Revenue", "Revenue"),
        (3020, "Sales revenue, lubricants", "Revenue", "Revenue"),
        (4000, "Cost of goods sold, spare parts", "COGS", "Cost of sales"),
        (4010, "Cost of service delivery", "COGS", "Cost of sales"),
        (4020, "Cost of goods sold, lubricants", "COGS", "Cost of sales"),
        (5000, "Salaries and personnel costs", "Opex", "Personnel"),
        (6300, "Rent and premises", "Opex", "Premises"),
        (6550, "Software and licences", "Opex", "IT and software"),
        (6700, "External services and consultants", "Opex", "External services"),
        (7140, "Travel", "Opex", "Travel"),
    ],
    columns=["account_id", "account_name", "account_type", "pl_line"],
)

# Monthly opex base (NOK, 2023) per cost centre and account
OPEX_BASE = {
    ("CC10", 5000): 1_100_000,
    ("CC10", 7140): 180_000,
    ("CC10", 6700): 120_000,
    ("CC20", 5000): 1_600_000,
    ("CC20", 7140): 260_000,
    ("CC30", 5000): 650_000,
    ("CC30", 6300): 420_000,
    ("CC30", 6700): 150_000,
    ("CC40", 5000): 380_000,
    ("CC40", 6550): 300_000,
    ("CC40", 6700): 140_000,
}

# ------------------------------------------------------------ helper curves
# Seasonality: drydock season lifts spring and early autumn, July and
# December are slow.
SEASON = np.array([0.90, 0.95, 1.08, 1.12, 1.10, 1.02, 0.80, 0.95, 1.08, 1.10, 1.02, 0.88])
VOLUME_GROWTH = 0.04  # per year, underlying
PRICE_INCREASE = {2023: 1.000, 2024: 1.025, 2025: 1.025}  # list price index, budget view
COST_INCREASE = {2023: 1.000, 2024: 1.020, 2025: 1.040}  # unit cost index
SALARY_INDEX = {2023: 1.00, 2024: 1.04, 2025: 1.08}
OTHER_OPEX_INDEX = {2023: 1.00, 2024: 1.03, 2025: 1.06}

# Planted 2025 effects (actual vs budget)
PLANT_VOLUME = {"PARTS": 0.94, "SERVICE": 1.08, "LUBE": 1.00}
PLANT_PRICE = 1.03
PLANT_IT_COST = 1.15


def years_since_start(month: pd.Timestamp) -> float:
    return (month.year - 2023) + (month.month - 1) / 12


# ------------------------------------------------------------------- sales
def expected_sales(month: pd.Timestamp) -> pd.DataFrame:
    """Expected (noise-free) sales for one month, budget view."""
    rows = []
    for _, r in regions.iterrows():
        for _, p in product_lines.iterrows():
            qty = (
                p.base_qty_norway
                * r.scale
                * SEASON[month.month - 1]
                * (1 + VOLUME_GROWTH) ** years_since_start(month)
            )
            rows.append(
                {
                    "month": month,
                    "region_id": r.region_id,
                    "product_line_id": p.product_line_id,
                    "quantity": qty,
                    "unit_price": p.list_price_2023 * PRICE_INCREASE[month.year],
                    "unit_cost": p.unit_cost_2023 * COST_INCREASE[month.year],
                }
            )
    return pd.DataFrame(rows)


expected = pd.concat([expected_sales(m) for m in MONTHS], ignore_index=True)

# Actuals: expected x planted effect (2025 only) x noise
actual = expected.copy()
is_2025 = actual["month"].dt.year == BUDGET_YEAR
vol_factor = np.where(is_2025, actual["product_line_id"].map(PLANT_VOLUME), 1.0)
price_factor = np.where(is_2025, PLANT_PRICE, 1.0)

actual["quantity"] = actual["quantity"] * vol_factor * rng.normal(1.0, 0.04, len(actual))
actual["unit_price"] = actual["unit_price"] * price_factor * rng.normal(1.0, 0.01, len(actual))
actual["unit_cost"] = actual["unit_cost"] * rng.normal(1.0, 0.01, len(actual))

budget = expected[expected["month"].dt.year == BUDGET_YEAR].copy()


def finish_sales(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["quantity"] = df["quantity"].round(0).astype(int)
    df["revenue_nok"] = (df["quantity"] * df["unit_price"]).round(0).astype(int)
    df["cogs_nok"] = (df["quantity"] * df["unit_cost"]).round(0).astype(int)
    df["month"] = df["month"].dt.strftime("%Y-%m-%d")
    return df[["month", "region_id", "product_line_id", "quantity", "revenue_nok", "cogs_nok"]]


sales_actuals = finish_sales(actual)
sales_budget = finish_sales(budget)


# --------------------------------------------------------------------- opex
def opex(month: pd.Timestamp, noisy: bool) -> pd.DataFrame:
    rows = []
    for (cc, acc), base in OPEX_BASE.items():
        index = SALARY_INDEX if acc == 5000 else OTHER_OPEX_INDEX
        amount = base * index[month.year]
        if noisy:
            if cc == "CC40" and month.year == BUDGET_YEAR:
                amount *= PLANT_IT_COST
            if acc != 6300:  # rent is fixed
                amount *= rng.normal(1.0, 0.05)
        rows.append({"month": month, "account_id": acc, "cost_centre_id": cc, "amount": amount})
    return pd.DataFrame(rows)


opex_actuals = pd.concat([opex(m, noisy=True) for m in MONTHS], ignore_index=True)
opex_budget = pd.concat(
    [opex(m, noisy=False) for m in MONTHS if m.year == BUDGET_YEAR], ignore_index=True
)


# ----------------------------------------------------------------------- GL
def sales_to_gl(sales: pd.DataFrame) -> pd.DataFrame:
    s = sales.merge(product_lines[["product_line_id", "revenue_account", "cogs_account"]])
    rev = s.assign(account_id=s.revenue_account, amount=-s.revenue_nok)  # credit
    cogs = s.assign(account_id=s.cogs_account, amount=s.cogs_nok)  # debit
    cc = {"PARTS": "CC10", "LUBE": "CC10", "SERVICE": "CC20"}
    out = pd.concat([rev, cogs], ignore_index=True)
    out["cost_centre_id"] = out["product_line_id"].map(cc)
    return out[["month", "account_id", "cost_centre_id", "region_id", "amount"]]


def opex_to_gl(o: pd.DataFrame) -> pd.DataFrame:
    o = o.copy()
    o["month"] = o["month"].dt.strftime("%Y-%m-%d")
    o["region_id"] = ""  # opex is not split by region
    return o[["month", "account_id", "cost_centre_id", "region_id", "amount"]]


def finish_gl(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["amount_nok"] = df.pop("amount").round(0).astype(int)
    return df.sort_values(["month", "account_id", "cost_centre_id", "region_id"]).reset_index(
        drop=True
    )


gl_actuals = finish_gl(pd.concat([sales_to_gl(sales_actuals), opex_to_gl(opex_actuals)]))
gl_budget = finish_gl(pd.concat([sales_to_gl(sales_budget), opex_to_gl(opex_budget)]))

# ------------------------------------------------------------------- write
regions[["region_id", "region_name"]].to_csv(OUT / "dim_region.csv", index=False)
product_lines[
    ["product_line_id", "product_line_name", "unit", "revenue_account", "cogs_account"]
].to_csv(OUT / "dim_product_line.csv", index=False)
cost_centres.to_csv(OUT / "dim_cost_centre.csv", index=False)
accounts.to_csv(OUT / "dim_account.csv", index=False)
sales_actuals.to_csv(OUT / "sales_actuals.csv", index=False)
sales_budget.to_csv(OUT / "sales_budget.csv", index=False)
gl_actuals.to_csv(OUT / "gl_actuals.csv", index=False)
gl_budget.to_csv(OUT / "gl_budget.csv", index=False)

# ------------------------------------------------------------------- check
print("Rows written")
for name in ["sales_actuals", "sales_budget", "gl_actuals", "gl_budget"]:
    print(f"  {name:15s} {len(globals()[name]):>6,}")

a25 = sales_actuals[sales_actuals["month"].str.startswith("2025")]
q = a25.groupby("product_line_id")["quantity"].sum() / sales_budget.groupby(
    "product_line_id"
)["quantity"].sum()
a_price = a25.groupby("product_line_id")["revenue_nok"].sum() / a25.groupby(
    "product_line_id"
)["quantity"].sum()
b_price = sales_budget.groupby("product_line_id")["revenue_nok"].sum() / sales_budget.groupby(
    "product_line_id"
)["quantity"].sum()

print("\n2025 actual vs budget (planted in brackets)")
for pl in ["PARTS", "SERVICE", "LUBE"]:
    print(
        f"  {pl:8s} volume {q[pl] - 1:+.1%} ({PLANT_VOLUME[pl] - 1:+.0%})   "
        f"price {a_price[pl] / b_price[pl] - 1:+.1%} ({PLANT_PRICE - 1:+.0%})"
    )

ga = gl_actuals[gl_actuals["month"].str.startswith("2025")]
it_a = ga.loc[ga["cost_centre_id"] == "CC40", "amount_nok"].sum()
it_b = gl_budget.loc[gl_budget["cost_centre_id"] == "CC40", "amount_nok"].sum()
print(f"  IT cost centre spend {it_a / it_b - 1:+.1%} ({PLANT_IT_COST - 1:+.0%})")

for label, gl in [("Actual", ga), ("Budget", gl_budget)]:
    g = gl.merge(accounts[["account_id", "account_type"]])
    by = g.groupby("account_type")["amount_nok"].sum()
    rev, cogs, op = -by["Revenue"], by["COGS"], by["Opex"]
    print(
        f"\n{label} 2025: revenue {rev / 1e6:,.1f}M NOK, gross margin {(rev - cogs) / rev:.1%}, "
        f"EBIT {(rev - cogs - op) / 1e6:,.1f}M NOK ({(rev - cogs - op) / rev:.1%})"
    )

"""FY budget (Feb 2024 - Jan 2025): monthly projected cost, revenue and gross margin per item, with
scenarios and a one-at-a-time sensitivity table.

Cost path = deseasonalised recent level x half-strength seasonal index (validated in forecast.py).
Volumes, target margins and the handling allowance are illustrative assumptions from config/basket.csv.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from .market import seasonal_index
from .pricing import HANDLING

SI_YEARS = (2017, 2018, 2019, 2020, 2023)
SHRINK = 0.5
WEEKS_PER_MONTH = 52 / 12
DOMESTIC = {"Canada", "Ontario", "Quebec", "British Columbia", "Canada Ontario"}


def import_share(rows: pd.DataFrame) -> pd.DataFrame:
    """Share of quotes from outside Canada by item and calendar month (2017-2024)."""
    r = rows.assign(month=rows.date.dt.month, imported=~rows.origin.isin(DOMESTIC))
    return r.groupby(["item_id", "month"]).imported.mean().unstack()


def base_levels(panel: pd.DataFrame, si: pd.DataFrame, weeks: int = 8) -> pd.Series:
    p = panel[panel.period == "B_2022_2024"].sort_values("date")
    last = p.groupby("item_id").tail(weeks).copy()
    last["deseason"] = last.apply(lambda r: r.price_cad / si.loc[r.item_id, r.date.month], axis=1)
    return last.groupby("item_id").deseason.mean()


def build_budget(panel, rows, basket, months=None, shrink: float = SHRINK) -> pd.DataFrame:
    if months is None:
        months = pd.period_range("2024-02", "2025-01", freq="M")
    si = 1 + shrink * (seasonal_index(panel, SI_YEARS) - 1)
    lvl = base_levels(panel, si)
    imp = import_share(rows)
    b = basket.set_index("item_id")
    out = []
    for item in b.index:
        if item not in lvl.index:
            continue
        for m in months:
            cost = lvl[item] * si.loc[item, m.month] * (1 + HANDLING)
            cases = b.loc[item, "weekly_cases"] * WEEKS_PER_MONTH
            tm = b.loc[item, "target_margin"]
            out.append(
                {
                    "item_id": item,
                    "display_name": b.loc[item, "display_name"],
                    "category": b.loc[item, "category"],
                    "month": str(m),
                    "terminal_cost": lvl[item] * si.loc[item, m.month],
                    "landed_cost": cost,
                    "sell_price": cost / (1 - tm),
                    "cases": cases,
                    "target_margin": tm,
                    "import_share": imp.loc[item, m.month] if item in imp.index else 0.0,
                }
            )
    d = pd.DataFrame(out)
    d["revenue"] = d.sell_price * d.cases
    d["cogs"] = d.landed_cost * d.cases
    d["gross_margin"] = d.revenue - d.cogs
    return d


def historical_spike_quantiles(panel: pd.DataFrame, cats=("Leafy & lettuce", "Tomatoes")) -> pd.DataFrame:
    """Monthly average price vs the item's trailing 12-month average: how big is a 1-in-10 month?
    Used to size the supply-shock scenario."""
    p = (
        panel.assign(m=panel.date.dt.to_period("M"))
        .groupby(["item_id", "category", "m"])
        .price_cad.mean()
        .reset_index()
    )
    p["trail"] = p.groupby("item_id").price_cad.transform(lambda s: s.rolling(12, min_periods=8).mean().shift(1))
    p["ratio"] = p.price_cad / p.trail
    q = p[p.category.isin(cats)].dropna().groupby("category").ratio.quantile([0.5, 0.9, 0.95]).unstack()
    q.columns = ["p50", "p90", "p95"]
    return q.reset_index()


def apply_scenario(bud: pd.DataFrame, name: str) -> pd.DataFrame:
    d = bud.copy()
    if name == "base":
        pass
    elif name == "cad_weaker_5pct":  # import cost +5% on the imported share from Feb; prices catch up in Mar
        f = 1 + 0.05 * d.import_share
        d["landed_cost"] *= f
        d["sell_price"] *= np.where(d.month == d.month.min(), 1.0, f)
    elif name == "lettuce_tomato_shock":  # +40% cost for Mar-Apr on leafy + tomatoes, prices lag 1 month
        hit = d.category.isin(["Leafy & lettuce", "Tomatoes"]) & d.month.isin(["2024-03", "2024-04"])
        d.loc[hit, "landed_cost"] *= 1.40
        lag = hit & (d.month == "2024-03")  # March priced off February cost; April repriced
        d.loc[hit & ~lag, "sell_price"] *= 1.40
    elif name == "handling_up_10pct":  # freight/fuel allowance +10%, not passed to customers
        d["landed_cost"] *= (1 + HANDLING * 1.10) / (1 + HANDLING)
    elif name == "volume_down_5pct":
        d["cases"] *= 0.95
    else:
        raise ValueError(name)
    d["revenue"] = d.sell_price * d.cases
    d["cogs"] = d.landed_cost * d.cases
    d["gross_margin"] = d.revenue - d.cogs
    return d


SCENARIOS = ["base", "cad_weaker_5pct", "lettuce_tomato_shock", "handling_up_10pct", "volume_down_5pct"]


def scenario_table(bud: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for s in SCENARIOS:
        d = apply_scenario(bud, s)
        rows.append(
            {
                "scenario": s,
                "revenue": d.revenue.sum(),
                "cogs": d.cogs.sum(),
                "gross_margin": d.gross_margin.sum(),
                "gm_pct": d.gross_margin.sum() / d.revenue.sum(),
            }
        )
    t = pd.DataFrame(rows)
    t["gm_vs_base"] = t.gross_margin - t.gross_margin.iloc[0]
    return t


def sensitivity(bud: pd.DataFrame) -> pd.DataFrame:
    """One-at-a-time swings on annual gross margin dollars."""
    base = bud.gross_margin.sum()
    rev, cogs = bud.revenue.sum(), bud.cogs.sum()
    cases_gm = base
    rows = [
        ("Volume +/-10%", cases_gm * 0.10, -cases_gm * 0.10),
        ("Achieved margin +/-2 pts", rev * 0.02, -rev * 0.02),
        ("Produce cost +/-10%, passed through", base * 0.10, -base * 0.10),
        ("Produce cost +/-10%, held 1 month", (cogs * 0.10) / 12, -(cogs * 0.10) / 12),
        ("Handling allowance +/-1 pt, absorbed", (cogs / (1 + HANDLING)) * 0.01, -(cogs / (1 + HANDLING)) * 0.01),
    ]
    t = pd.DataFrame(rows, columns=["driver", "upside", "downside"])
    t["swing"] = t.upside - t.downside
    return t.sort_values("swing", ascending=False)


def custom_scenario(
    bud: pd.DataFrame,
    fx_shock: float = 0.0,
    supply_shock: float = 0.0,
    shock_categories=("Leafy & lettuce", "Tomatoes"),
    shock_months=("2024-03", "2024-04"),
    handling_up: float = 0.0,
    volume_change: float = 0.0,
    price_lag_months: int = 1,
) -> pd.DataFrame:
    """All levers at once. Cost shocks hit immediately; sell prices catch up after price_lag_months
    (0 = same month). Handling increases are absorbed (not priced)."""
    d = bud.copy()
    months = sorted(d.month.unique())
    lagged = set(months[:price_lag_months])
    fx = 1 + fx_shock * d.import_share
    d["landed_cost"] *= fx
    d["sell_price"] *= np.where(d.month.isin(lagged), 1.0, fx)
    if supply_shock:
        sm = sorted(shock_months)
        hit = d.category.isin(shock_categories) & d.month.isin(sm)
        lag = hit & d.month.isin(sm[:price_lag_months])
        d.loc[hit, "landed_cost"] *= 1 + supply_shock
        d.loc[hit & ~lag, "sell_price"] *= 1 + supply_shock
    d["landed_cost"] *= (1 + HANDLING * (1 + handling_up)) / (1 + HANDLING)
    d["cases"] *= 1 + volume_change
    d["revenue"] = d.sell_price * d.cases
    d["cogs"] = d.landed_cost * d.cases
    d["gross_margin"] = d.revenue - d.cogs
    return d

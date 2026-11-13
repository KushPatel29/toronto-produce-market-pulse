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
    p = p[p.item_id.isin(si.index) & (p.date >= panel.date.max() - pd.Timedelta(weeks=weeks))]
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
    # Calendar months, not the last 12 observations: missing periods stay missing.
    p["trail"] = np.nan
    for _, g in p.groupby("item_id"):
        s = g.set_index("m").price_cad
        calendar = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M"))
        trail = calendar.shift(1).rolling(12, min_periods=8).mean()
        p.loc[g.index, "trail"] = g.m.map(trail).to_numpy()
    p["ratio"] = p.price_cad / p.trail
    q = p[p.category.isin(cats)].dropna().groupby("category").ratio.quantile([0.5, 0.9, 0.95]).unstack()
    q.columns = ["p50", "p90", "p95"]
    return q.reset_index()


def apply_scenario(bud: pd.DataFrame, name: str) -> pd.DataFrame:
    if name == "base":
        return custom_scenario(bud)
    elif name == "cad_weaker_5pct":
        return custom_scenario(bud, fx_shock=0.05)
    elif name == "lettuce_tomato_shock":
        return custom_scenario(bud, supply_shock=0.40)
    elif name == "handling_up_10pct":  # freight/fuel allowance +10%, not passed to customers
        return custom_scenario(bud, handling_up=0.10)
    elif name == "volume_down_5pct":
        return custom_scenario(bud, volume_change=-0.05)
    else:
        raise ValueError(name)


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
    """One-at-a-time annual gross-margin deltas, re-evaluated by the scenario engine."""
    base = bud.gross_margin.sum()
    rev, cogs = bud.revenue.sum(), bud.cogs.sum()
    cats = tuple(bud.category.unique())
    months = tuple(bud.month.unique())
    immediate = [custom_scenario(bud, supply_shock=x, shock_categories=cats,
                                shock_months=months, price_lag_months=0).gross_margin.sum() - base
                 for x in [-0.10, 0.10]]
    lagged = [custom_scenario(bud, supply_shock=x, shock_categories=cats,
                             shock_months=months, price_lag_months=1).gross_margin.sum() - base
              for x in [-0.10, 0.10]]
    rows = [
        ("Volume +/-10%", base * 0.10, -base * 0.10),
        ("Achieved margin +/-2 pts", rev * 0.02, -rev * 0.02),
        ("Cost +/-10%, immediate pass-through", max(immediate), min(immediate)),
        ("Cost +/-10%, one-month price lag", max(lagged), min(lagged)),
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
    """Apply shocks and shift their combined price multiplier by calendar months.

    Both the onset AND reversal are delayed. The baseline seasonal price path is
    unchanged; only the scenario multiplier is lagged. Pre-horizon multiplier = 1.
    Handling increases are absorbed and demand is fixed apart from volume_change.
    """
    shocks = [fx_shock, supply_shock, handling_up, volume_change]
    if not np.isfinite(shocks).all() or any(x < -1 for x in shocks):
        raise ValueError("Scenario changes must be finite and at least -100%")
    if not isinstance(price_lag_months, (int, np.integer)) or not 0 <= price_lag_months <= 12:
        raise ValueError("Price lag must be an integer from 0 to 12 months")
    if bud.duplicated(["item_id", "month"]).any():
        raise ValueError("Budget must be unique by item and month")
    d = bud.copy()
    fx = 1 + fx_shock * d.import_share
    hit = d.category.isin(shock_categories) & d.month.isin(shock_months)
    d["cost_multiplier"] = fx * np.where(hit, 1 + supply_shock, 1.0)
    periods = pd.PeriodIndex(d.month, freq="M")
    multipliers = pd.Series(d.cost_multiplier.to_numpy(), index=pd.MultiIndex.from_arrays([d.item_id, periods]))
    lag_keys = pd.MultiIndex.from_arrays([d.item_id, periods - price_lag_months])
    # Missing months inside the supplied horizon cannot silently become a neutral multiplier.
    missing_inside = ~lag_keys.isin(multipliers.index) & ((periods - price_lag_months) >= periods.min())
    if missing_inside.any():
        raise ValueError("Budget has missing item/month history needed for the selected price lag")
    d["price_multiplier"] = multipliers.reindex(lag_keys, fill_value=1.0).to_numpy()
    d["landed_cost"] *= d.cost_multiplier
    d["sell_price"] *= d.price_multiplier
    d["landed_cost"] *= (1 + HANDLING * (1 + handling_up)) / (1 + HANDLING)
    d["cases"] *= 1 + volume_change
    d["revenue"] = d.sell_price * d.cases
    d["cogs"] = d.landed_cost * d.cases
    d["gross_margin"] = d.revenue - d.cogs
    return d

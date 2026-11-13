"""Market intelligence on the weekly item panel: basket index, multi-year price change,
seasonality, volatility and supply (origin) shifts."""

from __future__ import annotations
import numpy as np
import pandas as pd

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def basket_index(panel: pd.DataFrame, base_year: int = 2019) -> pd.DataFrame:
    """Fixed-base monthly basket index (base_year average = 100). For each item, the monthly average
    CAD price is divided by that item's base-year average; the basket index is the geometric mean
    across items quoted that month (Jevons). No week-to-week chaining, so no chain drift, and the
    April 2021-November 2022 source gap is simply left empty."""
    p = panel.assign(month=panel.date.dt.to_period("M"))
    mon = p.groupby(["item_id", "month"]).price_cad.mean().rename("price").reset_index()
    base = p[p.date.dt.year == base_year].groupby("item_id").price_cad.mean().rename("base")
    mon = mon.merge(base, on="item_id")
    mon["lrel"] = np.log(mon.price / mon.base)
    idx = mon.groupby("month").agg(lrel=("lrel", "mean"), n_items=("lrel", "size")).reset_index()
    idx["index"] = 100 * np.exp(idx.lrel)
    idx["month_start"] = idx.month.dt.to_timestamp()
    return idx[["month_start", "index", "n_items"]]


def annual_change(panel: pd.DataFrame, base: int = 2019, comp: int = 2023) -> pd.DataFrame:
    """Average CAD price by item for two full years and the % change (inflation evidence)."""
    p = panel.assign(year=panel.date.dt.year)
    a = (
        p[p.year.isin([base, comp])]
        .pivot_table(index=["item_id", "display_name", "category"], columns="year", values="price_cad", aggfunc="mean")
        .dropna()
    )
    a.columns = [f"avg_{c}" for c in a.columns]
    a["pct_chg"] = a[f"avg_{comp}"] / a[f"avg_{base}"] - 1
    return a.reset_index().sort_values("pct_chg", ascending=False)


def seasonal_index(panel: pd.DataFrame, years=(2017, 2018, 2019, 2020)) -> pd.DataFrame:
    """Monthly seasonal index per item: price relative to that item's own annual average,
    averaged across complete years. 1.20 means the month typically runs 20% above the yearly mean."""
    p = panel[panel.date.dt.year.isin(years)].assign(year=panel.date.dt.year, month=panel.date.dt.month)
    p["rel"] = p.price_cad / p.groupby(["item_id", "year"]).price_cad.transform("mean")
    si = p.groupby(["item_id", "month"]).rel.mean().unstack()
    si = si.div(si.mean(axis=1), axis=0)  # normalise so each item's months average 1.0
    return si


def volatility(panel: pd.DataFrame) -> pd.DataFrame:
    r = panel.dropna(subset=["rel_cad"]).copy()
    r["lr"] = np.log(r.rel_cad.clip(0.2, 5))
    v = (
        r.groupby(["item_id", "display_name", "category"])
        .agg(
            weekly_vol=("lr", "std"),
            share_weeks_move_gt_10pct=("lr", lambda x: float((x.abs() > np.log(1.10)).mean())),
            max_weekly_jump=("rel_cad", "max"),
            max_weekly_drop=("rel_cad", "min"),
            n_weeks=("lr", "size"),
        )
        .reset_index()
    )
    # 4-week moves on the level series (same period, consecutive report weeks only)
    q = panel.sort_values("date").copy()
    q["chg4"] = q.groupby(["item_id", "period"]).price_cad.transform(lambda s: s / s.shift(4) - 1)
    m4 = q.groupby("item_id").chg4.agg(lambda x: float((x.abs() > 0.15).mean())).rename("share_4wk_move_gt_15pct")
    v = v.merge(m4, on="item_id")
    v["volatility_tier"] = pd.cut(v.weekly_vol, [0, 0.06, 0.12, 9], labels=["Stable", "Moderate", "Volatile"])
    return v.sort_values("weekly_vol", ascending=False)


def origin_mix(rows: pd.DataFrame, item_id: str) -> pd.DataFrame:
    """Share of quotes by origin and calendar month for one item (supply calendar)."""
    s = rows[rows.item_id == item_id].assign(month=rows.date.dt.month)
    t = s.groupby(["month", "origin"]).size().unstack(fill_value=0)
    return t.div(t.sum(axis=1), axis=0)


def origin_premium(rows: pd.DataFrame) -> pd.DataFrame:
    """Same week, same item: median price by origin relative to that week's item median."""
    s = rows.copy()
    s["wk_med"] = s.groupby(["item_id", "date"]).mid_cad.transform("median")
    s["rel"] = s.mid_cad / s.wk_med
    g = s.groupby(["item_id", "origin"]).agg(rel_price=("rel", "median"), weeks=("date", "nunique")).reset_index()
    return g[g.weeks >= 26]

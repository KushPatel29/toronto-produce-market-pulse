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


def annual_change(panel: pd.DataFrame, base: int = 2019, comp: int = 2023,
                  min_months: int = 10) -> pd.DataFrame:
    """CAD price change on calendar months observed in both comparison years.

    Each matched month receives equal weight; unmatched months and items with
    fewer than min_months matches are excluded. This is a matched-month comparison,
    not a claim of complete annual coverage. Month support is returned per item.
    """
    if base == comp or not isinstance(min_months, (int, np.integer)) or not 1 <= min_months <= 12:
        raise ValueError("Use two different years and a minimum month count from 1 to 12")
    keys = ["item_id", "display_name", "category"]
    columns = keys + [f"avg_{base}", f"avg_{comp}", "n_months", "compared_months", "pct_chg"]
    p = panel.assign(year=panel.date.dt.year, month=panel.date.dt.month)
    monthly = p[p.year.isin([base, comp])].pivot_table(
        index=keys + ["month"], columns="year", values="price_cad", aggfunc="mean")
    if base not in monthly.columns or comp not in monthly.columns:
        return pd.DataFrame(columns=columns)
    matched = monthly.dropna(subset=[base, comp]).reset_index()
    a = matched.groupby(keys)[[base, comp]].mean().rename(columns={base: f"avg_{base}", comp: f"avg_{comp}"})
    support = matched.groupby(keys).agg(
        n_months=("month", "size"),
        compared_months=("month", lambda months: ",".join(f"{m:02d}" for m in sorted(months))),
    )
    a = a.join(support)
    a = a[a.n_months >= min_months]
    a["pct_chg"] = a[f"avg_{comp}"] / a[f"avg_{base}"] - 1
    return a.reset_index().sort_values("pct_chg", ascending=False)


def seasonal_index(panel: pd.DataFrame, years=(2017, 2018, 2019, 2020)) -> pd.DataFrame:
    """Monthly seasonal index per item: price relative to that item's own annual average,
    averaged across item-years with all 12 calendar months represented.

    Each month has equal weight regardless of quote frequency. Items with no complete
    year are omitted; the twelve month columns are retained even for an empty result.
    1.20 means the month typically runs 20% above the equal-month yearly mean.
    """
    p = panel[panel.date.dt.year.isin(years)].assign(year=panel.date.dt.year, month=panel.date.dt.month)
    monthly = p.groupby(["item_id", "year", "month"]).price_cad.mean().reset_index()
    coverage = monthly.groupby(["item_id", "year"]).month.transform("nunique")
    monthly = monthly[coverage == 12].copy()
    monthly["rel"] = monthly.price_cad / monthly.groupby(["item_id", "year"]).price_cad.transform("mean")
    si = monthly.groupby(["item_id", "month"]).rel.mean().unstack().reindex(columns=range(1, 13))
    si = si.div(si.mean(axis=1), axis=0)  # normalise so each item's months average 1.0
    return si


def volatility(panel: pd.DataFrame) -> pd.DataFrame:
    r = panel.dropna(subset=["rel_cad"]).copy()
    r["lr"] = np.log(r.rel_cad.clip(0.2, 5))
    v = (
        r.groupby(["item_id", "display_name", "category"])
        .agg(
            weekly_vol=("lr", "std"),
            share_weeks_move_gt_10pct=("rel_cad", lambda x: float(((x - 1).abs() > 0.10).mean())),
            max_weekly_jump=("rel_cad", "max"),
            max_weekly_drop=("rel_cad", "min"),
            n_weeks=("lr", "size"),
        )
        .reset_index()
    )
    # Four observations are not necessarily four weeks when reports are missing.
    # Allow a two-day reporting-date shift around 28 days, and score only known
    # four-week comparisons rather than counting unobserved changes as no move.
    q = panel.sort_values("date").copy()
    q["chg4"] = q.groupby(["item_id", "period"]).price_cad.transform(lambda s: s / s.shift(4) - 1)
    elapsed = (q.date - q.groupby(["item_id", "period"]).date.shift(4)).dt.days
    q.loc[~elapsed.between(26, 30), "chg4"] = np.nan
    m4 = q.groupby("item_id").chg4.agg(
        lambda x: float((x.dropna().abs() > 0.15).mean())
    ).rename("share_4wk_move_gt_15pct")
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

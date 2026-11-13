"""Clean raw USDA Toronto terminal prices and build a weekly item-level panel in CAD."""

from __future__ import annotations
import numpy as np
import pandas as pd

RAW = "data/raw/toronto_terminal_prices_2017_2024.csv"
FX = "data/raw/boc_usdcad_on_report_dates.csv"
BASKET = "config/basket.csv"
KEY = ["commodity", "variety", "package", "item_size", "origin", "environment", "properties", "organic", "grade"]


def load_raw(path: str = RAW) -> pd.DataFrame:
    d = pd.read_csv(path, dtype=str)
    d["date"] = pd.to_datetime(d["report_date"], format="%m/%d/%Y")
    for c in ["low_price_usd", "high_price_usd"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["low_price_usd", "high_price_usd"])
    d = d[(d.low_price_usd > 0) & (d.high_price_usd >= d.low_price_usd)]
    d[KEY] = d[KEY].fillna("N/A")
    d["mid_usd"] = (d.low_price_usd + d.high_price_usd) / 2
    return d.drop_duplicates(subset=KEY + ["date"]).reset_index(drop=True)


def attach_fx(d: pd.DataFrame, path: str = FX) -> pd.DataFrame:
    fx = pd.read_csv(path, parse_dates=["report_date"]).rename(columns={"report_date": "date"})
    out = d.merge(fx[["date", "usd_cad"]], on="date", how="left", validate="many_to_one")
    if out.usd_cad.isna().any():
        raise ValueError("missing FX for some report dates")
    out["mid_cad"] = out.mid_usd * out.usd_cad
    out["low_cad"] = out.low_price_usd * out.usd_cad
    out["high_cad"] = out.high_price_usd * out.usd_cad
    return out


def basket_rows(d: pd.DataFrame, basket: pd.DataFrame) -> pd.DataFrame:
    """Conventional (non-organic) quotes for each basket item."""
    b = basket[["item_id", "commodity", "package"]]
    out = d[d.organic == "N"].merge(b, on=["commodity", "package"], how="inner")
    return out


def weekly_panel(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per item-week: median mid price across all quotes (origins/sizes), range, quote count,
    leading origin and its share of quotes."""
    g = rows.groupby(["item_id", "date"])
    p = g.agg(
        price_cad=("mid_cad", "median"),
        low_cad=("low_cad", "min"),
        high_cad=("high_cad", "max"),
        n_quotes=("mid_cad", "size"),
        usd_cad=("usd_cad", "first"),
    ).reset_index()
    o = rows.groupby(["item_id", "date", "origin"]).size().rename("n").reset_index()
    o = o.sort_values(["item_id", "date", "n"], ascending=[True, True, False])
    lead = o.groupby(["item_id", "date"]).head(1).rename(columns={"origin": "lead_origin", "n": "lead_n"})
    p = p.merge(lead, on=["item_id", "date"])
    p["lead_origin_share"] = p.lead_n / p.n_quotes
    k = o.groupby(["item_id", "date"]).size().rename("n_origins").reset_index()
    p = p.merge(k, on=["item_id", "date"])
    return p.drop(columns="lead_n")


def matched_relatives(rows: pd.DataFrame) -> pd.DataFrame:
    """Week-over-week price relative per item using only identical quote series present in both weeks
    (matched-model), so changes in origin/size mix do not show up as price changes. Only consecutive
    report weeks <= 14 days apart are linked (the April 2021-November 2022 source gap is never bridged)."""
    rows = rows.copy()
    rows["skey"] = rows[KEY].agg("|".join, axis=1)
    dates = np.sort(rows.date.unique())
    prev = {
        dates[i]: dates[i - 1] for i in range(1, len(dates)) if (dates[i] - dates[i - 1]) <= np.timedelta64(14, "D")
    }
    cur = rows[["item_id", "date", "skey", "mid_usd"]]
    out = []
    for item, s in cur.groupby("item_id"):
        piv = s.pivot_table(index="date", columns="skey", values="mid_usd", aggfunc="median")
        for t, tp in prev.items():
            if t in piv.index and tp in piv.index:
                a, b = piv.loc[t], piv.loc[tp]
                m = a.notna() & b.notna()
                if m.sum() >= 1:
                    out.append((item, t, float(np.exp(np.median(np.log(a[m] / b[m])))), int(m.sum())))
    return pd.DataFrame(out, columns=["item_id", "date", "rel_usd", "n_matched"])


def detect_conversion_anomalies(panel: pd.DataFrame, fx: pd.DataFrame, tol: float = 0.20) -> pd.DataFrame:
    """Find report weeks where (almost) every item moves together by the same factor versus its own
    neighbouring weeks. In this source that pattern is a currency-conversion error, not a market move:
    the factor matches USD/CAD (prices left in CAD) or USD/CAD squared (converted twice).
    Returns one row per flagged week with the diagnosis."""
    p = panel.sort_values("date").copy()
    p["ref"] = p.groupby(["item_id", "period"]).price_cad.transform(
        lambda s: s.rolling(9, center=True, min_periods=4).median()
    )
    w = (
        p.assign(ratio=p.price_cad / p.ref)
        .groupby("date")
        .agg(
            basket_ratio=("ratio", "median"),
            share_items_up=("ratio", lambda r: float((r > 1.1).mean())),
            n_items=("ratio", "size"),
        )
        .reset_index()
    )
    w = w.merge(fx[["date", "usd_cad"]], on="date")
    flag = w[(w.basket_ratio > 1 + tol) | (w.basket_ratio < 1 / (1 + tol))].copy()

    def diag(r):
        if abs(r.basket_ratio / r.usd_cad - 1) < 0.05:
            return "prices published in CAD but labelled USD (ratio = USD/CAD)"
        if abs(r.basket_ratio / r.usd_cad**2 - 1) < 0.05:
            return "prices converted twice (ratio = USD/CAD squared)"
        return "basket-wide jump; cause unknown"

    flag["diagnosis"] = flag.apply(diag, axis=1)
    return flag


def conversion_factors(raw: pd.DataFrame, min_share: float = 0.15) -> pd.DataFrame:
    """USDA republishes Infohort's CAD prices in USD at its own weekly FX rate. When a seller's CAD price is
    unchanged, its USD quote still moves by that week's FX factor, so the most common week-over-week USD
    ratio across ALL quotes (every commodity) reveals the conversion factor. Dividing quote relatives by it
    gives true local-currency price changes. Falls back to the Bank of Canada FX ratio when no clear mode."""
    r = raw.copy()
    r["skey"] = r[KEY].agg("|".join, axis=1)
    piv = r.pivot_table(index="date", columns="skey", values="mid_usd", aggfunc="median")
    out = []
    for i in range(1, len(piv)):
        t, tp = piv.index[i], piv.index[i - 1]
        if (t - tp).days > 14:
            continue
        a, b = piv.iloc[i], piv.iloc[i - 1]
        m = a.notna() & b.notna()
        if m.sum() < 5:
            continue
        rr = (a[m] / b[m]).round(3)
        mode = float(rr.mode().iloc[0])
        share = float((rr == mode).mean())
        out.append((t, mode, share, int(m.sum())))
    return pd.DataFrame(out, columns=["date", "usd_conversion_factor", "share_unchanged", "n_matched_quotes"])


def build(save: bool = True):
    basket = pd.read_csv(BASKET)
    raw = attach_fx(load_raw())
    rows = basket_rows(raw, basket)
    fx = pd.read_csv(FX, parse_dates=["report_date"]).rename(columns={"report_date": "date"}).sort_values("date")
    first = weekly_panel(rows).assign(period=lambda x: np.where(x.date < "2022-01-01", "A", "B"))
    anomalies = detect_conversion_anomalies(first, fx)
    rows = rows[~rows.date.isin(anomalies.date)]
    panel = weekly_panel(rows)
    rel = matched_relatives(rows)
    fx = fx[~fx.date.isin(anomalies.date)].copy()
    fx["fx_rel"] = fx.usd_cad / fx.usd_cad.shift(1)
    cf = conversion_factors(raw[~raw.date.isin(anomalies.date)])
    rel = rel.merge(fx[["date", "fx_rel"]], on="date", how="left").merge(cf, on="date", how="left")
    use_mode = rel.share_unchanged >= 0.15
    rel["rel_cad"] = np.where(use_mode, rel.rel_usd / rel.usd_conversion_factor, rel.rel_usd * rel.fx_rel)
    panel = panel.merge(rel[["item_id", "date", "rel_cad", "n_matched"]], on=["item_id", "date"], how="left")
    panel = panel.merge(basket[["item_id", "display_name", "category"]], on="item_id")
    panel["period"] = np.where(panel.date < "2022-01-01", "A_2017_2021", "B_2022_2024")
    if save:
        rows.drop(columns=["report_date"]).to_csv("data/processed/basket_quotes.csv", index=False)
        panel.to_csv("data/processed/weekly_item_panel.csv", index=False)
        anomalies.to_csv("data/processed/dq_excluded_weeks.csv", index=False)
        cf.to_csv("data/processed/usd_conversion_factors.csv", index=False)
    return raw, rows, panel, anomalies

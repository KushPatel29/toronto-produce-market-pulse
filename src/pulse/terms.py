"""Customer pricing terms replayed on real costs: profitability and margin variance against target.

Each segment buys a share of the basket at its own target margin and on its own pricing terms
(config/customer_terms.csv - illustrative assumptions, not company data). Prices are replayed on the real
weekly Toronto cost path, so segment profitability differences come from how each set of terms copes
with real market moves.

Margin variance against target splits exactly into two parts per item-week:
  cost timing = cases x (last week's cost - this week's cost)   -> unavoidable: quotes go out a week ahead
  price hold  = cases x (cost the price was set on - last week's cost) -> the cost of holding a price
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from .pricing import FLOOR_GAP, HANDLING, _simulate


def replay(panel: pd.DataFrame, basket: pd.DataFrame, segments: pd.DataFrame, policy_override: dict | None = None):
    """Weekly item x segment detail: price, cost, cases, GM and variance vs target margin."""
    b = basket.set_index("item_id")
    out = []
    for (item, per), s in panel.sort_values("date").groupby(["item_id", "period"]):
        s = s.reset_index(drop=True)
        cost = (s.price_cad * (1 + HANDLING)).to_numpy()
        prev = np.r_[np.nan, cost[:-1]]
        for seg in segments.itertuples():
            m = float(b.loc[item, "target_margin"]) + seg.margin_adj
            pol = (policy_override or {}).get(seg.segment_id, seg.pricing_policy)
            price, changed = _simulate(cost, s.date, m, pol)
            out.append(
                pd.DataFrame(
                    {
                        "item_id": item,
                        "category": b.loc[item, "category"],
                        "period": per,
                        "segment_id": seg.segment_id,
                        "policy": pol,
                        "date": s.date,
                        "cost": cost,
                        "cost_prev": prev,
                        "price": price,
                        "changed": changed,
                        "target": m,
                        "cases": b.loc[item, "weekly_cases"] * seg.volume_share,
                    }
                )
            )
    d = pd.concat(out, ignore_index=True).dropna(subset=["price"])
    d["revenue"] = d.price * d.cases
    d["gm"] = (d.price - d.cost) * d.cases
    d["gm_target"] = d.revenue * d.target
    d["var_total"] = d.gm - d.gm_target
    d["var_cost_timing"] = d.cases * (d.cost_prev - d.cost)
    d["var_price_hold"] = d.cases * (d.price * (1 - d.target) - d.cost_prev)
    d["margin"] = 1 - d.cost / d.price
    d["breach"] = d.margin < d.target - FLOOR_GAP
    return d


def _roll(d: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g = d.groupby(by).agg(
        revenue=("revenue", "sum"),
        gm=("gm", "sum"),
        gm_target=("gm_target", "sum"),
        var_total=("var_total", "sum"),
        var_cost_timing=("var_cost_timing", "sum"),
        var_price_hold=("var_price_hold", "sum"),
        breach_rate=("breach", "mean"),
        price_changes=("changed", "sum"),
        item_weeks=("gm", "size"),
    )
    g["gm_pct"] = g.gm / g.revenue
    g["target_pct"] = g.gm_target / g.revenue
    g["gap_pts"] = (g.gm_pct - g.target_pct) * 100
    return g.reset_index()


def segment_pnl(d: pd.DataFrame) -> pd.DataFrame:
    return _roll(d, ["segment_id"])


def segment_category(d: pd.DataFrame) -> pd.DataFrame:
    return _roll(d, ["segment_id", "category"])


def variance_by(d: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    return _roll(d, by)


def monthly_variance(d: pd.DataFrame) -> pd.DataFrame:
    return _roll(d.assign(month=d.date.dt.to_period("M").astype(str)), ["month"])


def contract_whatif(panel, basket, segments, base: pd.DataFrame, seg_id: str = "contract") -> pd.DataFrame:
    """What the contract segment would have earned on a band-rule escalator clause, by category."""
    alt = replay(panel, basket, segments[segments.segment_id == seg_id], {seg_id: "band"})
    a = _roll(base[base.segment_id == seg_id], ["category"]).set_index("category")
    b = _roll(alt, ["category"]).set_index("category")
    t = pd.DataFrame(
        {
            "gm_pct_monthly": a.gm_pct,
            "gm_pct_band": b.gm_pct,
            "breach_monthly": a.breach_rate,
            "breach_band": b.breach_rate,
            "gm_gain": b.gm - a.gm,
        }
    )
    return t.reset_index().sort_values("breach_monthly", ascending=False)


def monthly_gap_spread(d: pd.DataFrame) -> pd.DataFrame:
    """How far each segment's monthly margin strays from target (points): sd, worst and best month."""
    m = _roll(d.assign(month=d.date.dt.to_period("M").astype(str)), ["segment_id", "month"])
    return m.groupby("segment_id").gap_pts.agg(sd="std", worst="min", best="max").reset_index()


def price_list(d: pd.DataFrame, basket: pd.DataFrame, segments: pd.DataFrame, week: str) -> pd.DataFrame:
    """ERP-style price-list upload for one effective week: one row per item x customer price group."""
    wk = pd.Timestamp(week)
    cur = d[d.date == wk]
    prior = d[d.date < wk].sort_values("date").groupby(["item_id", "segment_id"]).tail(1)
    t = cur.merge(prior[["item_id", "segment_id", "price"]], on=["item_id", "segment_id"], suffixes=("", "_prior"))
    t = t.merge(basket[["item_id", "display_name", "unit_note"]], on="item_id").merge(
        segments[["segment_id", "segment"]], on="segment_id"
    )
    chg = t.price / t.price_prior - 1
    return pd.DataFrame(
        {
            "item_code": t.item_id.str.upper(),
            "description": t.display_name,
            "uom": t.unit_note,
            "price_group": t.segment_id.str.upper(),
            "price_group_name": t.segment,
            "currency": "CAD",
            "unit_price": t.price.round(2),
            "prior_price": t.price_prior.round(2),
            "change_pct": chg.round(4),
            "effective_from": wk.strftime("%Y-%m-%d"),
            "effective_to": (wk + pd.Timedelta(days=6)).strftime("%Y-%m-%d"),
            "reason": np.where(np.isclose(chg, 0), "HELD", np.where(chg > 0, "COST_UP", "COST_DOWN")),
            "landed_cost": t.cost_prev.round(2),
            "target_margin": t.target.round(3),
        }
    ).sort_values(["price_group", "item_code"], ignore_index=True)

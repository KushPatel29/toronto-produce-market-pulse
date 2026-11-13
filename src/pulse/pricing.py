"""Pricing model: replay sell-price policies against the real weekly Toronto terminal cost path.

Cost basis per case = terminal mid price (CAD) x (1 + HANDLING). The terminal price stands in for
replacement cost. Target margins and the handling allowance are assumptions set in config, not
company data. Prices are set from LAST week's cost (quotes go out before the market week is known),
and realised margin is measured against THIS week's cost.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

HANDLING = 0.06  # freight + handling allowance on top of terminal price (assumption)
BAND = 0.05  # band policy: reprice when realised margin drifts > 5 pts from target
FLOOR_GAP = 0.10  # "margin breach": realised margin more than 10 pts below target


def _simulate(cost: np.ndarray, dates: pd.Series, m: float, policy: str) -> tuple[np.ndarray, np.ndarray]:
    n = len(cost)
    price = np.full(n, np.nan)
    changed = np.zeros(n, dtype=bool)
    for t in range(1, n):
        basis = cost[t - 1]  # last known cost
        target = basis / (1 - m)
        if policy == "weekly":
            price[t] = target
        elif policy == "monthly":
            new_month = t == 1 or dates.iloc[t].month != dates.iloc[t - 1].month
            price[t] = target if new_month else price[t - 1]
        elif policy == "band":
            if t == 1:
                price[t] = target
            else:
                held = price[t - 1]
                margin_at_held = 1 - basis / held
                new_month = dates.iloc[t].month != dates.iloc[t - 1].month
                drift = abs(margin_at_held - m) > BAND
                price[t] = target if (drift or (new_month and abs(margin_at_held - m) > BAND / 2)) else held
        else:
            raise ValueError(policy)
        changed[t] = t > 1 and not np.isclose(price[t], price[t - 1])
    return price, changed


def backtest(
    panel: pd.DataFrame, basket: pd.DataFrame, policies=("weekly", "band", "monthly")
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (weekly detail, item x policy summary). Runs separately within each source period so the
    2021-2022 gap is never treated as one week."""
    tgt = basket.set_index("item_id").target_margin
    detail = []
    for (item, per), s in panel.sort_values("date").groupby(["item_id", "period"]):
        s = s.reset_index(drop=True)
        cost = (s.price_cad * (1 + HANDLING)).to_numpy()
        m = float(tgt[item])
        for pol in policies:
            price, changed = _simulate(cost, s.date, m, pol)
            detail.append(
                pd.DataFrame(
                    {
                        "item_id": item,
                        "period": per,
                        "policy": pol,
                        "date": s.date,
                        "cost": cost,
                        "price": price,
                        "changed": changed,
                        "target": m,
                    }
                )
            )
    d = pd.concat(detail, ignore_index=True).dropna(subset=["price"])
    d["margin"] = 1 - d.cost / d.price
    d["breach"] = d.margin < d.target - FLOOR_GAP
    d["years"] = 1 / 52
    s = (
        d.groupby(["item_id", "policy"])
        .agg(
            weeks=("margin", "size"),
            avg_margin=("margin", "mean"),
            margin_sd=("margin", "std"),
            breach_rate=("breach", "mean"),
            price_changes=("changed", "sum"),
            years=("years", "sum"),
            gm_per_case=("price", lambda p: np.nan),
            target=("target", "first"),
        )
        .reset_index()
    )
    gm = d.assign(gm=d.price - d.cost).groupby(["item_id", "policy"]).gm.mean().rename("gm_per_case")
    s = s.drop(columns="gm_per_case").merge(gm, on=["item_id", "policy"])
    s["changes_per_year"] = s.price_changes / s.years
    return d, s


def recommend_cadence(summary: pd.DataFrame, max_breach: float = 0.10) -> pd.DataFrame:
    """Pick the calmest policy (fewest customer price changes) that keeps margin breaches under
    max_breach of weeks; fall back to weekly repricing."""
    order = {"monthly": 0, "band": 1, "weekly": 2}
    rows = []
    for item, s in summary.groupby("item_id"):
        s = s.assign(o=s.policy.map(order)).sort_values("o")
        ok = s[s.breach_rate <= max_breach]
        pick = ok.iloc[0] if len(ok) else s[s.policy == "weekly"].iloc[0]
        mon = s[s.policy == "monthly"].iloc[0]
        rows.append(
            {
                "item_id": item,
                "recommended_policy": pick.policy,
                "breach_rate_monthly_list": mon.breach_rate,
                "breach_rate_recommended": pick.breach_rate,
                "avg_margin_recommended": pick.avg_margin,
                "changes_per_year_recommended": pick.changes_per_year,
                "changes_per_year_weekly": s[s.policy == "weekly"].iloc[0].changes_per_year,
            }
        )
    return pd.DataFrame(rows)

"""Revenue growth management: price-volume-mix margin bridge and promotion evaluation.

Costs are real (Toronto terminal quotes plus the freight and handling allowance). Shipments, channel
discounts and promotions are SYNTHETIC: volumes are simulated around config/basket.csv, and each
promotion carries a planted volume uplift so the evaluation can be checked against a known answer.
Nothing here estimates real demand response or realised savings.

Price-volume-mix (gross margin, year B vs year A, item level):
    volume = (Q_B - Q_A) * GM_A / Q_A
    mix    = sum_i Q_B * (s_Bi - s_Ai) * m_Ai           s = item share of cases, m = margin per case
    list   = sum_i Q_Bi * (L_Bi - L_Ai)                 L = list price per case
    trade  = sum_i Q_Bi * ((P_Bi - L_Bi) - (P_Ai - L_Ai))   P = net price after discounts and promotions
    cost   = -sum_i Q_Bi * (C_Bi - C_Ai)
The five effects sum exactly to GM_B - GM_A.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .pricing import HANDLING

CHANNELS = [  # name, share of item volume, off-list discount (illustrative)
    ("Independent restaurant", 0.50, 0.00),
    ("Restaurant group", 0.30, 0.04),
    ("Catering", 0.20, 0.02),
]
PROMO_FEE = 150.0  # fixed cost per promotion event (flyer, sales incentive), CAD, illustrative
POST_DIP = 0.90  # volume in the week after a promotion, vs baseline (planted pantry-loading effect)


def simulate(
    panel: pd.DataFrame, basket: pd.DataFrame, years=(2019, 2023), seed: int = 7
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Weekly item x channel shipments on real costs, with planted promotions.

    Returns (weekly, events). Prices follow a weekly list built from the prior quoted week's landed cost at the
    item's target margin; channels take fixed discounts; promoted weeks take an extra price cut.
    """
    rng = np.random.default_rng(seed)
    b = basket.set_index("item_id")
    p = panel[panel.date.dt.year.isin(years)].sort_values(["item_id", "date"]).copy()
    keep = p.groupby("item_id").date.apply(lambda d: set(d.dt.year) >= set(years))
    p = p[p.item_id.isin(keep[keep].index)]
    growth = {i: rng.uniform(0.85, 1.15) for i in p.item_id.unique()}  # item mix drift, year B vs A
    rows, events = [], []
    for (item, year), s in p.groupby(["item_id", p.date.dt.year]):
        s = s.reset_index(drop=True)
        cost = (s.price_cad * (1 + HANDLING)).to_numpy()
        gap = s.date.diff().dt.days.fillna(999).to_numpy()
        prev = np.r_[np.nan, cost[:-1]]
        prev[gap > 14] = np.nan  # no list price across a gap in the source
        tm = float(b.loc[item, "target_margin"])
        lst = np.round(prev / (1 - tm) * 4) / 4  # list rounded to $0.25
        season = 1 + 0.08 * np.sin(2 * np.pi * (s.date.dt.dayofyear.to_numpy() - 120) / 365)
        level = growth[item] if year == max(years) else 1.0
        base = float(b.loc[item, "weekly_cases"]) * level * season * rng.lognormal(0, 0.06, len(s))
        promo = np.zeros(len(s))
        uplift = np.ones(len(s))
        depth = np.zeros(len(s))
        # two promotion events a year: 2 consecutive priced weeks, each within 14 days of the previous
        ok = [
            k
            for k in range(1, len(s) - 2)
            if np.isfinite(lst[k]) and np.isfinite(lst[k + 1]) and gap[k + 1] <= 14 and gap[k + 2] <= 14
        ]
        chosen: list[int] = []
        for k in rng.permutation(ok):
            if all(abs(k - c) > 6 for c in chosen):
                chosen.append(int(k))
            if len(chosen) == 2:
                break
        for e, k in enumerate(sorted(chosen)):
            u, d = rng.uniform(1.20, 2.30), rng.choice([0.10, 0.12, 0.15])
            promo[k : k + 2], uplift[k : k + 2], depth[k : k + 2] = 1, u, d
            uplift[k + 2] *= POST_DIP
            events.append(
                dict(
                    item_id=item,
                    year=year,
                    event=f"{item}-{year}-{e + 1}",
                    start=s.date[k],
                    end=s.date[k + 1],
                    dip_week=s.date[k + 2],
                    depth=d,
                    planted_uplift=u,
                )
            )
        for ch, share, disc in CHANNELS:
            q = base * share * uplift
            net = lst * (1 - disc) * (1 - depth)
            rows.append(
                pd.DataFrame(
                    dict(
                        item_id=item,
                        category=b.loc[item, "category"],
                        channel=ch,
                        year=year,
                        date=s.date,
                        cases=np.round(q, 2),
                        list_price=lst,
                        net_price=net,
                        unit_cost=cost,
                        promo=promo.astype(bool),
                        promo_depth=depth,
                        data_status="SYNTHETIC volumes and promotions; real terminal costs",
                    )
                )
            )
    w = pd.concat(rows, ignore_index=True).dropna(subset=["list_price"])
    w["revenue"] = w.cases * w.net_price
    w["list_revenue"] = w.cases * w.list_price
    w["cogs"] = w.cases * w.unit_cost
    w["gm"] = w.revenue - w.cogs
    ev = pd.DataFrame(events)
    ev = ev.merge(
        w.groupby(["item_id", "date"])
        .size()
        .rename("n")
        .reset_index()
        .rename(columns={"date": "start"})[["item_id", "start"]],
        on=["item_id", "start"],
    )  # only events whose first week has a list price
    return w, ev


def item_year(w: pd.DataFrame) -> pd.DataFrame:
    g = (
        w.groupby(["item_id", "category", "year"])[["cases", "revenue", "list_revenue", "cogs", "gm"]]
        .sum()
        .reset_index()
    )
    g["net_price"] = g.revenue / g.cases
    g["list_price"] = g.list_revenue / g.cases
    g["unit_cost"] = g.cogs / g.cases
    g["margin_per_case"] = g.gm / g.cases
    return g


def pvm(w: pd.DataFrame, a: int, b: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Item-level gross-margin bridge from year a to year b. Returns (bridge, item detail)."""
    iy = item_year(w)
    A = iy[iy.year == a].set_index("item_id")
    B = iy[iy.year == b].set_index("item_id")
    items = A.index.intersection(B.index)
    A, B = A.loc[items], B.loc[items]
    qa, qb = A.cases.sum(), B.cases.sum()
    d = pd.DataFrame(index=items)
    d["category"] = A.category
    d["cases_a"], d["cases_b"] = A.cases, B.cases
    d["share_a"], d["share_b"] = A.cases / qa, B.cases / qb
    d["list_a"], d["list_b"] = A.list_price, B.list_price
    d["net_a"], d["net_b"] = A.net_price, B.net_price
    d["cost_a"], d["cost_b"] = A.unit_cost, B.unit_cost
    d["margin_a"] = A.margin_per_case
    d["gm_a"], d["gm_b"] = A.gm, B.gm
    d["volume"] = (qb - qa) * d.share_a * (A.gm.sum() / qa)
    d["mix"] = qb * (d.share_b - d.share_a) * d.margin_a
    d["list_price"] = d.cases_b * (d.list_b - d.list_a)
    d["trade"] = d.cases_b * ((d.net_b - d.list_b) - (d.net_a - d.list_a))
    d["cost"] = -d.cases_b * (d.cost_b - d.cost_a)
    gm_a, gm_b = A.gm.sum(), B.gm.sum()
    bridge = pd.DataFrame(
        {
            "driver": [
                f"Gross margin {a}",
                "Volume",
                "Mix",
                "List price",
                "Discounts & promotions",
                "Cost",
                f"Gross margin {b}",
            ],
            "cad": [gm_a, d.volume.sum(), d.mix.sum(), d.list_price.sum(), d.trade.sum(), d.cost.sum(), gm_b],
        }
    )
    return bridge, d.reset_index()


def promo_eval(w: pd.DataFrame, events: pd.DataFrame, window: int = 4) -> pd.DataFrame:
    """Per event: baseline from up to `window` clean weeks either side, uplift, incremental margin, trade spend, ROI."""
    item_w = (
        w.groupby(["item_id", "date"])
        .agg(
            cases=("cases", "sum"),
            gm=("gm", "sum"),
            revenue=("revenue", "sum"),
            list_revenue=("list_revenue", "sum"),
            cogs=("cogs", "sum"),
            promo=("promo", "max"),
        )
        .reset_index()
    )
    out = []
    for e in events.itertuples():
        s = item_w[item_w.item_id == e.item_id].sort_values("date").reset_index(drop=True)
        s = s[s.date.dt.year == e.year].reset_index(drop=True)
        is_promo = s.date.between(e.start, e.end)
        is_dip = s.date == e.dip_week
        k0, k1 = s.index[is_promo].min(), s.index[is_promo].max()
        other_promo = s.promo & ~is_promo
        clean = ~(is_promo | is_dip | other_promo)
        # a following promotion's own dip week is also excluded
        dips = set(events[(events.item_id == e.item_id) & (events.year == e.year)].dip_week)
        clean &= ~s.date.isin(dips)
        before = s[clean & (s.index < k0)].tail(window)
        after = s[clean & (s.index > k1 + 1)].head(window)
        base = pd.concat([before, after])
        if len(base) < 3:
            continue
        base_cases = float(base.cases.median())
        base_margin_per_case = float((base.gm / base.cases).median())
        pw = s[is_promo]
        dw = s[is_dip]
        inc_cases = float(pw.cases.sum() - base_cases * len(pw))
        dip_cases = float(dw.cases.sum() - base_cases * len(dw)) if len(dw) else 0.0
        # price investment = the promotion's extra cut on every promoted case (channel discounts apply anyway)
        price_investment = float(e.depth / (1 - e.depth) * pw.revenue.sum())
        trade_spend = price_investment + PROMO_FEE
        # incremental margin at regular-price margins on extra cases, net of the price investment and the dip
        inc_margin = (inc_cases + dip_cases) * base_margin_per_case - trade_spend
        base_net = float(base.revenue.sum() / base.cases.sum())
        promo_margin = base_margin_per_case - e.depth * base_net
        # lift U at which net incremental margin is zero, counting the event fee and the post-promotion dip:
        # (U - 1) * B * n * m + dip * m - d * P * U * B * n - fee = 0
        bn = base_cases * len(pw)
        breakeven = (
            (bn * base_margin_per_case - dip_cases * base_margin_per_case + PROMO_FEE) / (bn * promo_margin)
            if promo_margin > 0
            else np.inf
        )
        out.append(
            dict(
                event=e.event,
                item_id=e.item_id,
                year=e.year,
                start=e.start.date(),
                depth=e.depth,
                planted_uplift=e.planted_uplift,
                baseline_cases=base_cases,
                promo_cases=float(pw.cases.sum()),
                est_uplift=float(pw.cases.mean() / base_cases),
                incremental_cases=inc_cases,
                dip_cases=dip_cases,
                breakeven_uplift=breakeven,
                trade_spend=trade_spend,
                net_incremental_margin=inc_margin,
                roi=inc_margin / trade_spend,
            )
        )
    r = pd.DataFrame(out)
    r["uplift_error_pts"] = (r.est_uplift - r.planted_uplift) * 100
    r["verdict"] = np.where(r.roi > 0, "Repeat", np.where(r.roi > -0.5, "Redesign", "Stop"))
    return r

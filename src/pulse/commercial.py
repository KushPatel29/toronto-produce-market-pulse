"""Reproducible commercial case study; customer and competitor records are synthetic.

Public terminal quotes are replacement-cost proxies, never actual ERP purchase costs.
No demand elasticity or realised business benefit is inferred from this simulation.
"""

import numpy as np
import pandas as pd

from .pricing import HANDLING

SEGMENTS = [
    ("Independent restaurant", 0.50, 0.00, 0.01, 1.50),
    ("Restaurant group", 0.30, 0.04, 0.03, 1.00),
    ("Catering", 0.20, 0.02, 0.02, 2.00),
]


def demo_sales(panel, basket, week=None):
    """One item/customer record for a selected historical week and its prior report.

    Seeded variation is illustrative. Omit items without a prior quote within 14 days.
    The budget is a prior-cost planning assumption, not an observed company budget.
    """
    week = pd.Timestamp(week or panel.date.max())
    hist = panel[panel.date <= week].sort_values(["item_id", "date"])
    current = hist[hist.date == week].set_index("item_id")
    prior = hist[hist.date < week].groupby("item_id").tail(1).set_index("item_id")
    rng = np.random.default_rng(29)
    out = []
    for _, b in basket.sort_values("item_id").iterrows():
        if b.item_id not in current.index or b.item_id not in prior.index:
            continue
        cur, prev = current.loc[b.item_id], prior.loc[b.item_id]
        if (week - prev.date).days > 14:
            continue
        for segment, share, discount, rebate, service in SEGMENTS:
            q0 = float(b.weekly_cases * share)
            q1 = float(max(1, round(q0 * rng.uniform(0.80, 1.15))))
            # Baseline all-in variable cost includes delivery and spoilage assumptions.
            c0 = float(prev.price_cad * (1 + HANDLING) / 0.98 + service)
            c1 = float(cur.price_cad * (1 + HANDLING) / 0.98 + service)
            list_price = c0 / (1 - b.target_margin)
            p1 = list_price * (1 - discount) * (1 - rebate)
            out.append(dict(
                date=week, item_id=b.item_id, item=b.display_name, category=b.category,
                unit=b.unit_note, customer=segment, target_margin=b.target_margin,
                budget_cases=q0, actual_cases=q1, budget_net_price=list_price,
                actual_list_price=list_price, discount=discount, rebate=rebate,
                actual_net_price=p1, budget_unit_cost=c0, actual_unit_cost=c1,
                service_cost_per_case=service, spoilage_rate=0.02,
                data_status="SYNTHETIC commercial records; public cost proxy",
            ))
    return pd.DataFrame(out)


def validate_sales(sales):
    """Return a canonical copy; reject unusable keys and financial records.

    Dates are daily UTC-naive keys. Numeric CSV strings are accepted and converted,
    so passing validation also guarantees that subsequent arithmetic is numeric.
    """
    required = {
        "date", "item_id", "customer", "target_margin", "budget_cases", "actual_cases",
        "budget_net_price", "actual_net_price", "budget_unit_cost", "actual_unit_cost",
    }
    missing = required - set(sales.columns)
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")
    d = sales.copy()
    for key in ["item_id", "customer"]:
        if d[key].isna().any() or not d[key].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
            raise ValueError(f"{key} must contain nonempty text keys")
        d[key] = d[key].str.strip()
    d["date"] = pd.to_datetime(d.date, errors="coerce", format="mixed", utc=True).dt.tz_localize(None).dt.normalize()
    if d.date.isna().any():
        raise ValueError("Sales dates must be valid")
    if d.empty or d.duplicated(["date", "item_id", "customer"]).any():
        raise ValueError("Sales must be nonempty and unique by date, item and customer")
    numeric = list(required - {"date", "item_id", "customer"})
    numeric += [c for c in ["discount", "rebate", "spoilage_rate", "actual_list_price", "service_cost_per_case"]
                if c in d.columns]
    try:
        for col in numeric:
            if d[col].map(lambda v: isinstance(v, (bool, np.bool_))).any():
                raise ValueError("Boolean financial values are not valid")
            d[col] = pd.to_numeric(d[col], errors="raise")
        values = d[numeric].to_numpy(dtype=float)
    except (ValueError, TypeError) as exc:
        raise ValueError("Financial fields must be numeric") from exc
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Financial values must be finite and nonnegative")
    if (d[["budget_net_price", "actual_net_price"]] <= 0).any().any():
        raise ValueError("Net prices must be positive")
    if not d.target_margin.between(0, 0.95, inclusive="left").all():
        raise ValueError("Target margin must be at least zero and below 95%")
    for col in ["discount", "rebate", "spoilage_rate"]:
        if col in d.columns and not d[col].between(0, 1, inclusive="left").all():
            raise ValueError(f"{col} must be at least zero and below 100%")
    return d


def profitability(sales):
    """Contribution after illustrative variable delivery/spoilage, before fixed overhead."""
    d = validate_sales(sales)
    d["revenue"] = d.actual_cases * d.actual_net_price
    d["variable_cost"] = d.actual_cases * d.actual_unit_cost
    d["contribution"] = d.revenue - d.variable_cost
    d["margin_pct"] = 1 - d.actual_unit_cost / d.actual_net_price
    d["margin_gap_pp"] = 100 * (d.margin_pct - d.target_margin)
    d["target_gap_dollars"] = (d.revenue * d.target_margin - d.contribution).clip(lower=0)
    d["budget_contribution"] = d.budget_cases * (d.budget_net_price - d.budget_unit_cost)
    return d


def variance_bridge(sales):
    """Exact sequential bridge: volume at budget spread, price at actual volume,
    then cost at actual volume. Row-level aggregation includes mix in volume.
    """
    d = profitability(sales)
    return pd.DataFrame([
        ("Budget contribution", d.budget_contribution.sum()),
        ("Volume & mix", ((d.actual_cases - d.budget_cases) * (d.budget_net_price - d.budget_unit_cost)).sum()),
        ("Net price / discount", ((d.actual_net_price - d.budget_net_price) * d.actual_cases).sum()),
        ("Variable unit cost", (-(d.actual_unit_cost - d.budget_unit_cost) * d.actual_cases).sum()),
        ("Actual contribution", d.contribution.sum()),
    ], columns=["driver", "cad"])


def demo_competitors(sales):
    """Five fictional competitors with segment-specific net quotes, not list prices.

    The same fictional companies quote each customer segment. Comparator prices
    include the simulated customer's discounts/rebates through actual_net_price.
    """
    sales = validate_sales(sales)
    rows = []
    for _, r in sales.sort_values(["date", "item_id", "customer"]).iterrows():
        for i, factor in enumerate([0.94, 0.98, 1.00, 1.03, 1.08], 1):
            rows.append(dict(
                item_id=r.item_id, customer=r.customer, unit=r.unit, currency="CAD", quote_date=r.date,
                competitor=f"Demo comparator {i}", price=r.actual_net_price * factor,
                price_basis="net_after_discounts_rebates",
                data_status="SYNTHETIC; not observed competitor pricing",
            ))
    return pd.DataFrame(rows)


def recommendations(sales, competitors, max_increase=0.10):
    """Cost-plus quote guidance with explicit approvals; no automated price changes.

    Competitor median +5% is an illustrative review threshold, not an optimum.
    Only same-segment, same-unit, net CAD quotes dated within the previous 14 days
    are comparable. One latest quote per competitor is used; contradictory prices
    for the same competitor/date are excluded rather than averaged.
    """
    if not 0 <= max_increase <= 1:
        raise ValueError("Max increase must be between 0 and 100%")
    d = profitability(sales)
    required = {"item_id", "customer", "unit", "currency", "quote_date", "competitor", "price", "price_basis"}
    if missing := required - set(competitors.columns):
        raise ValueError(f"Missing competitor fields: {', '.join(sorted(missing))}")
    competitors = competitors.copy()
    competitors["quote_date"] = pd.to_datetime(competitors.quote_date, errors="coerce", format="mixed", utc=True).dt.tz_localize(None)
    competitors["price"] = pd.to_numeric(competitors.price, errors="coerce")
    competitor_key = competitors.competitor.map(lambda v: isinstance(v, str) and bool(v.strip()))
    competitors = competitors[competitor_key]
    out = []
    for _, r in d.iterrows():
        c = competitors[(competitors.item_id == r.item_id) & (competitors.unit == r.unit)
                        & (competitors.customer == r.customer) & (competitors.currency == "CAD")
                        & (competitors.price_basis == "net_after_discounts_rebates")].copy()
        age = (r.date - c.quote_date).dt.days
        c = c[age.between(0, 14) & np.isfinite(c.price) & (c.price > 0)]
        c = c.drop_duplicates(["competitor", "quote_date", "price"])
        # Do not fall back to an older quote when the latest date has conflicting
        # prices: that supplier's current price is ambiguous and needs review.
        c = c[c.quote_date == c.groupby("competitor").quote_date.transform("max")]
        c = c[~c.duplicated(["competitor", "quote_date"], keep=False)]
        c = c.sort_values("quote_date").groupby("competitor").tail(1)
        median = float(c.price.median()) if len(c) else np.nan
        floor = r.actual_unit_cost / (1 - r.target_margin)
        suggested = max(r.actual_net_price, floor)
        increase = suggested / r.actual_net_price - 1
        # A held price can already be above market even when the target floor is
        # covered. Do not mislabel that as a target/market conflict.
        conflict = bool(pd.notna(median) and floor > median * 1.05)
        current_above_market = bool(pd.notna(median) and r.actual_net_price > median * 1.05)
        review = conflict or increase > max_increase
        out.append(dict(
            item_id=r.item_id, item=r.item, customer=r.customer,
            current_net_price=r.actual_net_price, target_net_price=floor,
            suggested_net_price=suggested, increase_pct=increase,
            competitor_median=median, comparable_quotes=len(c),
            market_guardrail_conflict=conflict,
            current_above_market=current_above_market,
            approval="Finance + Sales review" if review else "Sales review",
            reason="Target exceeds market review threshold" if conflict else
                   "Increase exceeds approval threshold" if increase > max_increase else
                   "Recover target margin" if increase > 0 else
                   "Hold; review existing above-market position" if current_above_market else "Hold; target covered",
            indicative_contribution_change=(suggested - r.actual_net_price) * r.actual_cases,
        ))
    return pd.DataFrame(out)


def procurement_alerts(panel, week):
    """Quote breadth/origin/cost alerts are proxies; no inventory or availability feed."""
    p = panel[panel.date <= pd.Timestamp(week)].sort_values("date")
    cur = p[p.date == pd.Timestamp(week)].copy()
    hist = p[(p.date < pd.Timestamp(week)) & (p.date >= pd.Timestamp(week) - pd.Timedelta(days=42))]
    baseline = hist.groupby("item_id").n_quotes.median()
    prev = hist.groupby("item_id").tail(1).set_index("item_id")
    cur["quote_breadth_ratio"] = cur.n_quotes / cur.item_id.map(baseline)
    cur["origin_changed"] = cur.item_id.map(prev.lead_origin).notna() & (
        cur.lead_origin != cur.item_id.map(prev.lead_origin))
    cur["cost_jump"] = cur.rel_cad - 1
    cur["review"] = (cur.quote_breadth_ratio < 0.6) | cur.origin_changed | (cur.cost_jump > 0.15)
    cur["owner"] = "Procurement"
    cur["next_step"] = "Confirm supplier availability and pack comparability before quoting"
    return cur[["item_id", "display_name", "lead_origin", "quote_breadth_ratio", "origin_changed",
                "cost_jump", "review", "owner", "next_step"]]


def executive_brief(sales, recs, alerts):
    d = profitability(sales)
    rev, contribution = d.revenue.sum(), d.contribution.sum()
    bridge = variance_bridge(sales)
    margin = f"{contribution / rev:.1%}" if rev else "n/a; no actual sales"
    return (
        f"# Commercial decision brief — {pd.Timestamp(d.date.max()).date()}\n\n"
        "**Historical portfolio simulation. All customers, competitor prices, discounts, volumes, "
        "delivery and spoilage costs are synthetic assumptions. No Bondi company data.**\n\n"
        f"- Net revenue: CAD {rev:,.0f}; contribution after variable service costs: CAD {contribution:,.0f} "
        f"({margin}). Fixed overhead excluded.\n"
        f"- Contribution variance vs illustrative budget: CAD {bridge.cad.iloc[-1] - bridge.cad.iloc[0]:+,.0f}.\n"
        f"- Finance: reconcile the price/volume/cost bridge; review {int(recs.market_guardrail_conflict.sum())} "
        "quotes where the margin floor exceeds the illustrative market threshold.\n"
        f"- Sales: review {int((recs.increase_pct > 0).sum())} margin recovery candidates; validate contracts "
        "and customer response before quoting.\n"
        f"- Procurement: investigate {int(alerts.review.sum())} quote-breadth/origin/cost alerts. "
        "Quote breadth is a proxy, not confirmed supply availability.\n\n"
        "Suggested-price uplift assumes unchanged volume and cost; it is not a forecast or realised benefit. "
        "Review actions at the next pricing meeting. Historical source ends January 2024; this is not today's market.\n"
    )

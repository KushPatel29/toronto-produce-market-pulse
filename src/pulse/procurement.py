"""Supplier bid comparison for a historical, explicitly synthetic procurement case.

All suppliers, bids, capacities, lead times, freight, spoilage and reliability scores
are fictional. Public terminal quotes provide a historical cost anchor only.
Recommendations cover one supplier per item and always require Procurement review.
"""

from hashlib import sha256
from math import ceil

import numpy as np
import pandas as pd

STATUS = "SYNTHETIC supplier bid; public historical cost proxy"
BID_COLUMNS = [
    "item_id", "item", "supplier", "unit", "currency", "quote_date", "valid_until",
    "quoted_price", "freight_per_case", "spoilage_rate", "moq_cases", "capacity_cases",
    "lead_days", "reliability", "data_status",
]


def demo_supplier_bids(panel, basket, as_of=None):
    """Three deterministic fictional bids per item with a quote in the last 14 days.

    The cheapest nominal bid deliberately has tighter capacity/lead-time constraints,
    illustrating why purchasing cannot rank supplier unit price alone.
    """
    as_of = pd.Timestamp(as_of if as_of is not None else panel.date.max()).normalize()
    hist = panel[(panel.date <= as_of) & (panel.date >= as_of - pd.Timedelta(days=14))]
    latest = hist.sort_values("date").groupby("item_id").tail(1).set_index("item_id")
    rows = []
    for _, item in basket.sort_values("item_id").iterrows():
        if item.item_id not in latest.index:
            continue
        anchor = latest.loc[item.item_id]
        seed = int.from_bytes(sha256(str(item.item_id).encode()).digest()[:4], "big")
        rng = np.random.default_rng(seed)
        for i, (factor, capacity, lead, reliability) in enumerate([
            (0.94, 0.75, 3, 0.92), (1.00, 1.20, 1, 0.98), (1.04, 1.65, 2, 0.97),
        ], 1):
            rows.append(dict(
                item_id=item.item_id, item=item.display_name,
                supplier=f"Demo supplier {i}", unit=item.unit_note, currency="CAD",
                quote_date=as_of, valid_until=as_of + pd.Timedelta(days=7),
                quoted_price=round(float(anchor.price_cad * factor * rng.uniform(0.99, 1.01)), 2),
                freight_per_case=round(float(anchor.price_cad * (0.03 + i * 0.008)), 2),
                spoilage_rate=[0.04, 0.02, 0.01][i - 1],
                moq_cases=max(1, ceil(float(item.weekly_cases) * [0.50, 0.25, 0.75][i - 1])),
                capacity_cases=max(1, int(float(item.weekly_cases) * capacity)),
                lead_days=lead, reliability=reliability, data_status=STATUS,
            ))
    return pd.DataFrame(rows, columns=BID_COLUMNS)


def compare_supplier_bids(bids, basket, as_of, max_lead_days=2, min_reliability=0.95):
    """Return (evaluated bids, one review recommendation per basket item).

    Demand means usable cases. Order = max(MOQ, ceil(demand / (1 - spoilage))).
    Total order cost includes freight on every ordered case. The comparison charges
    the complete order to this week's demand, with no resale value assigned to surplus.
    Capacity is ordered cases, not usable cases. No multi-supplier optimisation is claimed.
    """
    required = set(BID_COLUMNS) - {"item", "data_status"}
    missing = required - set(bids.columns)
    if missing:
        raise ValueError(f"Missing supplier fields: {', '.join(sorted(missing))}")
    if bids.duplicated(["item_id", "supplier"]).any():
        raise ValueError("Use one bid per supplier and item")
    if basket.item_id.duplicated().any():
        raise ValueError("Basket item identifiers must be unique")
    demand = pd.to_numeric(basket.weekly_cases, errors="coerce")
    if not np.isfinite(demand).all() or (demand <= 0).any():
        raise ValueError("Weekly demand must be finite and positive")
    if not np.isfinite(max_lead_days) or max_lead_days < 0 or not 0 <= min_reliability <= 1:
        raise ValueError("Invalid lead-time or reliability threshold")
    as_of = pd.Timestamp(as_of).normalize()
    if pd.isna(as_of):
        raise ValueError("A valid as-of date is required")
    b = basket.set_index("item_id")
    evaluated = []
    numeric = ["quoted_price", "freight_per_case", "spoilage_rate", "moq_cases",
               "capacity_cases", "lead_days", "reliability"]
    for _, bid in bids.iterrows():
        r = bid.to_dict()
        reasons = []
        values = pd.to_numeric(bid[numeric], errors="coerce")
        numeric_ok = bool(np.isfinite(values).all() and (values >= 0).all())
        numeric_ok = numeric_ok and values.quoted_price > 0 and values.spoilage_rate < 1 and values.reliability <= 1
        numeric_ok = numeric_ok and all(values[c] == int(values[c]) for c in ["moq_cases", "capacity_cases", "lead_days"])
        if not numeric_ok:
            reasons.append("Invalid numeric bid fields")
        known = bid.item_id in b.index
        need = float(b.loc[bid.item_id, "weekly_cases"]) if known else np.nan
        if not known:
            reasons.append("Unknown item")
        elif bid.unit != b.loc[bid.item_id, "unit_note"]:
            reasons.append("Case unit mismatch")
        if bid.currency != "CAD":
            reasons.append("Currency mismatch")
        quoted = pd.to_datetime(bid.quote_date, errors="coerce")
        until = pd.to_datetime(bid.valid_until, errors="coerce")
        if pd.isna(quoted) or pd.isna(until) or quoted > as_of or until < as_of or (as_of - quoted).days > 14:
            reasons.append("Future, expired or stale quote")
        if numeric_ok and values.lead_days > max_lead_days:
            reasons.append("Lead time exceeds requirement")
        if numeric_ok and values.reliability < min_reliability:
            reasons.append("Reliability below threshold")
        eligible = not reasons
        order = max(int(values.moq_cases), ceil(need / (1 - values.spoilage_rate))) if numeric_ok and known else np.nan
        cost = order * (values.quoted_price + values.freight_per_case) if pd.notna(order) else np.nan
        usable_capacity = values.capacity_cases * (1 - values.spoilage_rate) if numeric_ok else 0.0
        # Capacity below MOQ cannot be purchased on the stated terms.
        if numeric_ok and values.capacity_cases < values.moq_cases:
            usable_capacity = 0.0
        if eligible and values.capacity_cases < order:
            reasons.append("Insufficient capacity for demand and MOQ")
        r.update(dict(
            demand_usable_cases=need, required_order_cases=order,
            delivered_cost_per_usable_case=(values.quoted_price + values.freight_per_case) / (1 - values.spoilage_rate)
            if numeric_ok else np.nan,
            total_order_cost=cost, cost_per_demand_case=cost / need if known and pd.notna(cost) else np.nan,
            expected_usable_cases=order * (1 - values.spoilage_rate) if pd.notna(order) else np.nan,
            usable_capacity_cases=usable_capacity, eligible_before_capacity=eligible,
            feasible=not reasons, exclusion_reason="; ".join(reasons),
        ))
        evaluated.append(r)
    d = pd.DataFrame(evaluated)
    recommendations = []
    for _, item in basket.iterrows():
        s = d[d.item_id == item.item_id] if not d.empty else d
        ok = s[s.feasible].sort_values(["total_order_cost", "supplier"]) if not s.empty else s
        capable = s[s.eligible_before_capacity] if not s.empty else s
        available = float(capable.usable_capacity_cases.max()) if not capable.empty else 0.0
        pick = ok.iloc[0] if not ok.empty else None
        recommendations.append(dict(
            item_id=item.item_id, item=item.display_name, unit=item.unit_note,
            demand_usable_cases=float(item.weekly_cases),
            supplier=pick.supplier if pick is not None else "No feasible single supplier",
            order_cases=float(pick.required_order_cases) if pick is not None else 0.0,
            total_order_cost=float(pick.total_order_cost) if pick is not None else np.nan,
            cost_per_demand_case=float(pick.cost_per_demand_case) if pick is not None else np.nan,
            single_supplier_shortfall_cases=0.0 if pick is not None else max(0.0, float(item.weekly_cases) - available),
            status="Procurement review required" if pick is not None else "Escalate: split sourcing or alternate pack required",
        ))
    return d, pd.DataFrame(recommendations)

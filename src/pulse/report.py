"""Weekly Market Update: what moved, what to reprice, what is coming, built from the panel for any
report week. Mirrors the structure of a distributor's customer market report, but written for the
internal Sales / Procurement / Finance audience."""

from __future__ import annotations
import numpy as np
import pandas as pd
from .market import seasonal_index
from .pricing import HANDLING, BAND

SHRINK = 0.5


def market_update(panel: pd.DataFrame, basket: pd.DataFrame, week: str, list_prices: dict | None = None) -> dict:
    wk = pd.Timestamp(week)
    p = panel[panel.date <= wk].sort_values("date")
    cur = p[p.date == wk].set_index("item_id")
    if cur.empty:
        raise ValueError(f"no report for {week}")
    # A four-week reference must not borrow quotes from before a source gap.
    hist = p[(p.date < wk) & (p.date >= wk - pd.Timedelta(days=35))]
    prev4 = hist.groupby("item_id").tail(4).groupby("item_id").price_cad.mean()
    prev1 = hist[hist.date >= wk - pd.Timedelta(days=14)].groupby("item_id").tail(1).set_index("item_id")
    si = 1 + SHRINK * (seasonal_index(panel[panel.date < wk], (2017, 2018, 2019, 2020)) - 1)
    b = basket.set_index("item_id")
    rows = []
    for item, r in cur.iterrows():
        tm = b.loc[item, "target_margin"]
        cost = r.price_cad * (1 + HANDLING)
        ref_cost = prev4.get(item, np.nan) * (1 + HANDLING)  # what the current list was built on
        list_price = (list_prices or {}).get(item, ref_cost / (1 - tm))
        margin_now = 1 - cost / list_price
        m_now, m_next = wk.month, (wk + pd.DateOffset(weeks=4)).month
        outlook = (
            si.loc[item, m_next] / si.loc[item, m_now] - 1
            if item in si.index and m_now in si.columns and m_next in si.columns
            else np.nan
        )
        rows.append(
            {
                "item_id": item,
                "item": b.loc[item, "display_name"],
                "category": b.loc[item, "category"],
                "price_cad": r.price_cad,
                "wow": (r.rel_cad - 1)
                if pd.notna(r.rel_cad)
                else (
                    r.price_cad / prev1.price_cad.get(item) - 1
                    if item in prev1.index and (wk - prev1.date.get(item)).days <= 14
                    else np.nan
                ),
                "wow_like_for_like": pd.notna(r.rel_cad),
                "vs_4wk_avg": r.price_cad / prev4.get(item, np.nan) - 1,
                "lead_origin": r.lead_origin,
                "prev_origin": prev1.lead_origin.get(item, None),
                "list_price": list_price,
                "margin_at_list": margin_now,
                "target_margin": tm,
                "suggested_price": cost / (1 - tm),
                "action": (
                    "Raise price"
                    if margin_now < tm - BAND
                    else "Lower price / promote"
                    if margin_now > tm + BAND
                    else "Insufficient recent history"
                    if pd.isna(margin_now)
                    else "Hold"
                ),
                "seasonal_outlook_4wk": outlook,
            }
        )
    t = pd.DataFrame(rows)
    t["origin_switch"] = t.prev_origin.notna() & (t.lead_origin != t.prev_origin)
    return {
        "week": wk,
        "table": t,
        "n_items": len(t),
        "basket_wow": float(np.exp(np.log(1 + t[t.wow_like_for_like].wow).mean()) - 1),
    }


def _pct(x, d=0):
    if pd.isna(x):
        return "n/a"
    if abs(x) < 0.5 * 10 ** (-2 - d):
        return "0%"
    return f"{x:+.{d}%}"


def to_markdown(u: dict) -> str:
    t = u["table"]
    wk = u["week"].strftime("%B %d, %Y")
    up = t[t.wow > 0.005].sort_values("wow", ascending=False).head(5)
    dn = t[t.wow < -0.005].sort_values("wow").head(5)
    act = t[t.action.isin(["Raise price", "Lower price / promote"])].sort_values("margin_at_list")
    nxt = t.dropna(subset=["seasonal_outlook_4wk"]).sort_values("seasonal_outlook_4wk")
    L = [
        f"# Toronto Produce Market Update - week of {wk}",
        "",
        f"Source: USDA AMS Market News, Toronto terminal market (data from Infohort, Agriculture and Agri-Food Canada), "
        f"converted to CAD at the Bank of Canada rate. {u['n_items']} items quoted this week. Prices are wholesale per case.",
        "",
        "## Headline",
        "",
        f"- Basket moved **{_pct(u['basket_wow'], 1)}** week over week (like-for-like quotes).",
        f"- **{(t.action == 'Raise price').sum()} items need a price increase** to hold target margin; "
        f"{(t.action == 'Lower price / promote').sum()} have room to sharpen price or promote.",
        f"- Supply switches this week: {', '.join(t[t.origin_switch].apply(lambda r: f'{r['item']} ({r.prev_origin} -> {r.lead_origin})', axis=1)) or 'none'}.",
        "",
        "## Biggest moves (week over week)",
        "",
        "| Rising | Change | Falling | Change |",
        "|---|---|---|---|",
    ]
    for i in range(max(len(up), len(dn), 1)):
        a = up.iloc[i] if i < len(up) else None
        z = dn.iloc[i] if i < len(dn) else None
        L.append(
            f"| {a['item'] if a is not None else ''} | {_pct(a.wow) if a is not None else ''} | "
            f"{z['item'] if z is not None else ''} | {_pct(z.wow) if z is not None else ''} |"
        )
    L += [
        "",
        "## Pricing actions (list price built on the average cost of up to 4 prior weeks)",
        "",
        "| Item | Terminal quote (CAD/case) | Margin at current list | Target | Action | Suggested price |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in act.iterrows():
        L.append(
            f"| {r['item']} | ${r.price_cad:,.2f} | {r.margin_at_list:.0%} | {r.target_margin:.0%} | {r.action} | ${r.suggested_price:,.2f} |"
        )
    if act.empty:
        L.append("| No actionable prices (check recent-history coverage) | | | | | |")
    L += [
        "",
        "## Next 4 weeks: seasonal outlook (half-strength seasonal index, 2017-2020)",
        "",
        f"- Typically **easing**: {', '.join(f'{r['item']} ({_pct(r.seasonal_outlook_4wk)})' for _, r in nxt.head(4).iterrows())}.",
        f"- Typically **firming**: {', '.join(f'{r['item']} ({_pct(r.seasonal_outlook_4wk)})' for _, r in nxt.tail(4).iloc[::-1].iterrows())}.",
        "- Seasonal outlook is a planning signal, not a weekly forecast: week to week, the latest price is the best predictor (see backtest).",
        "",
        "## Full item table",
        "",
        "| Item | CAD/case | WoW | vs 4-wk avg | Lead origin | Action |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in t.sort_values(["category", "item"]).iterrows():
        mark = "" if r.wow_like_for_like or pd.isna(r.wow) else "*"
        L.append(
            f"| {r['item']} | ${r.price_cad:,.2f} | {_pct(r.wow)}{mark} | {_pct(r.vs_4wk_avg)} | {r.lead_origin} | {r.action} |"
        )
    L += [
        "",
        "\\* No identical quote last week (different origin or size), so the change compares this week's and last week's typical price.",
        "",
        "_Margins assume a 6% freight and handling allowance and illustrative target margins by category (config/basket.csv)._",
    ]
    return "\n".join(L)

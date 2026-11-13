"""Toronto Produce Market Pulse - interactive app.  Run: streamlit run app.py"""

import json
import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
from pulse import budget as bg  # noqa: E402
from pulse import market as mk  # noqa: E402
from pulse import pricing as pr  # noqa: E402
from pulse import report as rp  # noqa: E402
from pulse import commercial as cm  # noqa: E402
from pulse import procurement as pc  # noqa: E402
from pulse import datamodel as dm  # noqa: E402
from pulse import terms as ct  # noqa: E402

st.set_page_config(page_title="Toronto Produce Market Pulse", page_icon="🥬", layout="wide")

BLUE, ORANGE, AQUA, RED, MID, INK2 = "#16324f", "#9c6500", "#26734d", "#b32632", "#eef2f4", "#5a6b75"
OUT = ROOT / "outputs"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]



def money(v: float) -> str:
    """Whole-dollar CAD with the sign in front: -$9,937, not $-9,937."""
    return f"-${abs(v):,.0f}" if v < 0 else f"${v:,.0f}"


def break_gaps(df: pd.DataFrame, days: int = 14) -> pd.DataFrame:
    """Number each run of weekly observations so charts never draw a line across a gap in the source."""
    df = df.sort_values("date").copy()
    df["run"] = (df.date.diff().dt.days > days).cumsum()
    return df


@st.cache_data
def load():
    basket = pd.read_csv(ROOT / "config/basket.csv")
    panel = pd.read_csv(ROOT / "data/processed/weekly_item_panel.csv", parse_dates=["date"])
    rows = pd.read_csv(ROOT / "data/processed/basket_quotes.csv", parse_dates=["date"], low_memory=False)
    facts = json.loads((OUT / "headline_facts.json").read_text(encoding="utf-8"))
    dq = pd.read_csv(ROOT / "data/processed/dq_excluded_weeks.csv", parse_dates=["date"])
    return basket, panel, rows, facts, dq


@st.cache_data
def derived(panel, basket):
    idx = mk.basket_index(panel)
    chg = mk.annual_change(panel)
    si = mk.seasonal_index(panel)
    vol = mk.volatility(panel)
    detail, summ = pr.backtest(panel, basket)
    rec = pr.recommend_cadence(summ)
    return idx, chg, si, vol, detail, summ, rec


@st.cache_data
def budget_base(panel, rows, basket, shrink):
    return bg.build_budget(panel, rows, basket, shrink=shrink)


@st.cache_data
def terms_replay(_panel, _basket):
    segs = pd.read_csv(ROOT / "config/customer_terms.csv")
    return segs, ct.replay(_panel, _basket, segs)


@st.cache_resource
def star_db(_panel, _basket):
    import tempfile

    segs, d = terms_replay(_panel, _basket)
    path = Path(tempfile.gettempdir()) / "market_pulse_app.sqlite"
    dm.build(dm.tables(_panel, _basket, segs, d), path)
    return path


basket, panel, rows, facts, dq = load()
tfacts = json.loads((OUT / "terms_facts.json").read_text(encoding="utf-8"))
idx, chg, si, vol, detail, summ, rec = derived(panel, basket)
names = dict(zip(basket.item_id, basket.display_name, strict=True))
ids = {v: k for k, v in names.items()}

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### Toronto Produce Market Pulse")
    st.caption(
        "Pricing, margin and market intelligence for a foodservice produce distributor, on real Toronto "
        "terminal-market prices (USDA AMS / Infohort, Agriculture and Agri-Food Canada), converted to CAD."
    )
    st.markdown(
        f"- **{facts['quotes_raw']:,}** wholesale quotes\n- **{facts['report_weeks']}** weekly reports, "
        f"{facts['date_min']} to {facts['date_max']}\n- **30** items, chef basket"
    )
    st.markdown("[Code on GitHub](https://github.com/KushPatel29/toronto-produce-market-pulse) · built by Kush Patel")
    st.caption(
        "Target margins, case volumes and the 6% freight & handling allowance are illustrative assumptions. "
        "No source reports exist between April 2021 and November 2022."
    )
    st.markdown("### Project downloads")
    for label, filename, mime in [
        ("Excel decision model", "Pricing_Decision_Workbook.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("Stakeholder presentation", "Produce_Pricing_Decision_Brief.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    ]:
        if (OUT / filename).exists():
            st.download_button(label, (OUT / filename).read_bytes(), filename, mime=mime)
    st.caption("Built for a produce-distributor pricing workflow. Independent portfolio project; no employer affiliation.")

st.title("Toronto Produce Market Pulse")
st.caption("Historical case study through January 2024. Customer, competitor and supplier examples are synthetic. No Bondi company data.")
tabs = st.tabs(
    [
        "Market overview",
        "Weekly market update",
        "Item explorer",
        "Price calculator",
        "Pricing policies",
        "Budget & scenarios",
        "Method & data quality",
        "Customer & pricing desk",
        "Supplier comparison",
        "Customer terms & margin variance",
    ]
)

# ---------------------------------------------------------------- 1. overview
with tabs[0]:
    pol = facts["policy"]
    c = st.columns(4)
    c[0].metric(
        "Matched-month price change, 2019 to 2023",
        f"+{facts['basket_change_2019_2023_geo']:.0%}",
        help=f"Geometric mean across {facts['items_compared']} items; same calendar months compared within each item; {facts['items_up_2019_2023']} rose.",
    )
    c[1].metric(
        "Weeks >10 pts under target margin",
        f"{pol['band']['breach_rate']:.0%}",
        delta=f"{pol['band']['breach_rate'] - pol['monthly']['breach_rate']:+.0%} vs monthly price list",
        delta_color="inverse",
    )
    c[2].metric(
        "Price changes / 52 observations (band)",
        f"{pol['band']['changes_per_year']:.0f}",
        delta=f"{pol['band']['changes_per_year'] - pol['weekly']['changes_per_year']:+.0f} vs weekly repricing",
        delta_color="inverse",
    )
    w6 = facts["budget_wape_6m"]
    c[3].metric(
        "6-month budget forecast error",
        f"{w6['seasonal']:.1%}",
        delta=f"{w6['seasonal'] - w6['flat']:+.1%} vs flat forecast",
        delta_color="inverse",
        help="Unseen 2023 test; seasonal strength chosen on 2019-2020 only.",
    )

    st.subheader("Basket price index (monthly, 2019 = 100)")
    full = pd.DataFrame({"month_start": pd.date_range(idx.month_start.min(), idx.month_start.max(), freq="MS")}).merge(
        idx, how="left"
    )
    line = (
        alt.Chart(full)
        .mark_line(color=BLUE, strokeWidth=2)
        .encode(
            x=alt.X("month_start:T", title=None),
            y=alt.Y("index:Q", title="Index", scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("month_start:T", title="Month", format="%b %Y"),
                alt.Tooltip("index:Q", format=".1f"),
                "n_items",
            ],
        )
    )
    gap = (
        alt.Chart(pd.DataFrame({"a": [pd.Timestamp("2021-05-01")], "b": [pd.Timestamp("2022-10-31")]}))
        .mark_rect(color=MID)
        .encode(x="a:T", x2="b:T")
    )
    rule = alt.Chart(pd.DataFrame({"y": [100]})).mark_rule(color=INK2, strokeDash=[4, 4]).encode(y="y:Q")
    st.altair_chart((gap + rule + line).properties(height=300), width="stretch")
    st.caption(
        "Grey band: no Toronto reports from USDA, April 2021 to November 2022. The late-2022 peak is the Salinas Valley lettuce crisis (INSV crop loss)."
    )

    st.subheader("Matched-month CAD price per case, 2023 vs 2019")
    st.caption("At least 10 calendar months observed in both years per item, with equal month weights. This selected-basket case-price comparison is not a full-year produce inflation estimate.")
    ch = chg.assign(direction=np.where(chg.pct_chg > 0, "Up", "Down"))
    bars = (
        alt.Chart(ch)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            y=alt.Y("display_name:N", sort="-x", title=None),
            x=alt.X("pct_chg:Q", title="% change", axis=alt.Axis(format="%")),
            color=alt.Color("direction:N", scale=alt.Scale(domain=["Up", "Down"], range=[RED, BLUE]), legend=None),
            tooltip=[
                "display_name",
                alt.Tooltip("avg_2019:Q", format="$.2f"),
                alt.Tooltip("avg_2023:Q", format="$.2f"),
                alt.Tooltip("pct_chg:Q", format="+.0%"),
            ],
        )
    )
    labels = bars.mark_text(align="left", dx=4, fontSize=11).encode(
        text=alt.Text("pct_chg:Q", format="+.0%"), color=alt.value("#0b0b0b")
    )
    st.altair_chart((bars + labels).properties(height=620), width="stretch")

# ---------------------------------------------------------------- 2. market update
with tabs[1]:
    weeks = sorted(panel.date.unique(), reverse=True)
    pick = st.selectbox(
        "Report week",
        weeks,
        format_func=lambda d: pd.Timestamp(d).strftime("%B %d, %Y"),
        help="Any of the 265 clean report weeks. Try December 13, 2022 (lettuce crisis) or March 23, 2020 (COVID).",
    )
    try:
        u = rp.market_update(panel, basket, str(pd.Timestamp(pick).date()))
        md = rp.to_markdown(u)
        t = u["table"]
        m = st.columns(3)
        m[0].metric("Basket, week over week", f"{u['basket_wow']:+.1%}")
        m[1].metric("Items to raise price", int((t.action == "Raise price").sum()))
        m[2].metric("Items with room to sharpen price", int((t.action == "Lower price / promote").sum()))
        st.download_button(
            "Download this update (Markdown)", md, file_name=f"market_update_{pd.Timestamp(pick).date()}.md"
        )
        st.markdown(md)
    except ValueError as e:
        st.warning(str(e))

# ---------------------------------------------------------------- 3. item explorer
with tabs[2]:
    nm = st.selectbox("Item", basket.display_name, index=list(basket.display_name).index("Romaine lettuce"))
    item = ids[nm]
    s = break_gaps(panel[panel.item_id == item])
    v = vol.set_index("item_id").loc[item]
    r = rec.set_index("item_id").loc[item]
    k = st.columns(4)
    k[0].metric("Latest price (CAD/case)", f"${s.price_cad.iloc[-1]:,.2f}", help=str(s.date.iloc[-1].date()))
    k[1].metric("Weekly volatility", f"{v.weekly_vol:.1%}", help=f"Tier: {v.volatility_tier}")
    k[2].metric("4-week moves over 15%", f"{v.share_4wk_move_gt_15pct:.0%} of weeks")
    k[3].metric(
        "Recommended repricing",
        {"weekly": "Weekly", "band": "Band rule", "monthly": "Monthly list"}[r.recommended_policy],
    )
    band = (
        alt.Chart(s)
        .mark_area(color=BLUE, opacity=0.15)
        .encode(x=alt.X("date:T", title=None), y=alt.Y("low_cad:Q", title="CAD per case"), y2="high_cad:Q", detail="run:N")
    )
    ln = (
        alt.Chart(s)
        .mark_line(color=BLUE, strokeWidth=2)
        .encode(
            x="date:T",
            y="price_cad:Q",
            detail="run:N",
            tooltip=[
                alt.Tooltip("date:T", format="%Y-%m-%d"),
                alt.Tooltip("price_cad:Q", format="$.2f", title="Typical price"),
                alt.Tooltip("low_cad:Q", format="$.2f"),
                alt.Tooltip("high_cad:Q", format="$.2f"),
                "lead_origin",
            ],
        )
    )
    st.altair_chart((band + ln).properties(height=300, title=f"{nm}: weekly price and low-high range"), width="stretch")
    st.caption("Breaks in the line are weeks with no Toronto quote for this item, including the April 2021 - November 2022 source gap.")
    a, b = st.columns(2)
    if item in si.index:
        sd = pd.DataFrame({"month": MONTHS, "index": si.loc[item].values})
        sd["dir"] = np.where(sd["index"] >= 1, "Above average", "Below average")
        a.altair_chart(
            alt.Chart(sd)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                x=alt.X("month:N", sort=MONTHS, title=None),
                y=alt.Y("index:Q", title="Seasonal index", scale=alt.Scale(zero=False)),
                color=alt.Color(
                    "dir:N",
                    scale=alt.Scale(domain=["Above average", "Below average"], range=[RED, BLUE]),
                    legend=alt.Legend(orient="bottom", title=None),
                ),
                tooltip=["month", alt.Tooltip("index:Q", format=".2f")],
            )
            .properties(height=260, title="When it is cheap or dear (2017-2020)"),
            width="stretch",
        )
    om = mk.origin_mix(rows, item)
    top = om.sum().sort_values(ascending=False).index[:3]
    om = (
        om[top].assign(Other=1 - om[top].sum(axis=1)).reset_index().melt("month", var_name="origin", value_name="share")
    )
    om["month_name"] = om.month.map(lambda m: MONTHS[m - 1])
    b.altair_chart(
        alt.Chart(om)
        .mark_bar()
        .encode(
            x=alt.X("month_name:N", sort=MONTHS, title=None),
            y=alt.Y("share:Q", stack="normalize", axis=alt.Axis(format="%"), title="Share of quotes"),
            color=alt.Color(
                "origin:N",
                scale=alt.Scale(range=[BLUE, ORANGE, AQUA, "#b9b8b2"]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=["month_name", "origin", alt.Tooltip("share:Q", format=".0%")],
        )
        .properties(height=260, title="Where supply comes from, by month"),
        width="stretch",
    )

# ---------------------------------------------------------------- 4. price calculator
with tabs[3]:
    c1, c2 = st.columns([1, 1])
    with c1:
        nm = st.selectbox("Item ", basket.display_name, key="calc_item")
        item = ids[nm]
        s = panel[panel.item_id == item].sort_values("date")
        latest = float(s.price_cad.iloc[-1])
        cost = st.number_input("This week's terminal cost (CAD/case)", min_value=0.0, value=round(latest, 2), step=0.5)
        tm = st.slider(
            "Target margin", 0.10, 0.45, float(basket.set_index("item_id").target_margin[item]), 0.01, format="%.2f"
        )
        handling = st.slider("Freight & handling allowance", 0.0, 0.15, pr.HANDLING, 0.01, format="%.2f")
        ref = float(s.price_cad.tail(4).mean()) * (1 + handling) / (1 - tm)
        current = st.number_input(
            "Current list price (CAD/case)",
            min_value=0.0,
            value=round(ref, 2),
            step=0.5,
            help="Default: list built on the last 4 weeks' average cost at target margin.",
        )
    landed = cost * (1 + handling)
    suggested = landed / (1 - tm)
    margin_now = 1 - landed / current if current else float("nan")
    gap = margin_now - tm
    action = "Enter a positive current list price" if not current else "Raise price" if gap < -pr.BAND else "Lower price / promote" if gap > pr.BAND else "Hold"
    pctile = float((s.tail(52).price_cad < cost).mean())
    with c2:
        st.metric("Suggested price at target margin", f"${suggested:,.2f}")
        st.metric("Margin at current list", f"{margin_now:.1%}", delta=f"{gap:+.1%} vs target")
        (st.error if action == "Raise price" else st.success if action == "Hold" else st.info)(
            f"**Action: {action}**  (band ±{pr.BAND:.0%} pts)"
        )
        st.caption(
            f"This cost is higher than {pctile:.0%} of the last 52 weekly prices for {nm}. Landed cost ${landed:,.2f}; "
            f"gross margin at current list ${current - landed:,.2f} per case."
        )

# ---------------------------------------------------------------- 5. pricing policies
with tabs[4]:
    st.markdown(
        "Three policies replayed against every real weekly cost. Prices are set from **last week's** cost (quotes go out before "
        "the market week); margin is measured against **this week's** cost. Item-specific gaps over 14 days restart the replay. "
        "Volumes and demand response are not estimated. Cadence choices are retrospective and have not been validated on future data."
    )
    agg = (
        summ.groupby("policy")[["breach_rate", "margin_sd", "changes_per_year", "avg_margin"]]
        .mean()
        .loc[["monthly", "band", "weekly"]]
    )
    agg.index = ["Monthly price list", "Band rule (±5 pts)", "Weekly repricing"]
    st.dataframe(
        agg.rename(
            columns={
                "breach_rate": "Weeks >10 pts under target",
                "margin_sd": "Margin volatility (sd)",
                "changes_per_year": "Changes / 52 scored observations",
                "avg_margin": "Average realised margin",
            }
        ).style.format(
            {
                "Weeks >10 pts under target": "{:.0%}",
                "Margin volatility (sd)": "{:.1%}",
                "Changes / 52 scored observations": "{:.0f}",
                "Average realised margin": "{:.1%}",
            }
        ),
        width="stretch",
    )
    c1, c2 = st.columns([1, 2])
    nm = c1.selectbox(
        "Replay an item", basket.display_name, index=list(basket.display_name).index("Roma tomatoes"), key="pol_item"
    )
    polname = c1.radio(
        "Policy",
        ["monthly", "band", "weekly"],
        format_func={"monthly": "Monthly list", "band": "Band rule", "weekly": "Weekly"}.get,
    )
    period = c1.radio(
        "Period",
        ["B_2022_2024", "A_2017_2021"],
        format_func={"A_2017_2021": "2017-2021", "B_2022_2024": "2022-2024"}.get,
    )
    d = break_gaps(detail[(detail.item_id == ids[nm]) & (detail.policy == polname) & (detail.period == period)])
    long = d.melt(["date", "run"], ["cost", "price"], var_name="series", value_name="cad")
    long["series"] = long.series.map({"cost": "Landed cost", "price": "Sell price"})
    c2.altair_chart(
        alt.Chart(long)
        .mark_line(strokeWidth=2, interpolate="step-after")
        .encode(
            x=alt.X("date:T", title=None),
            y=alt.Y("cad:Q", title="CAD per case"),
            color=alt.Color(
                "series:N", scale=alt.Scale(range=[ORANGE, BLUE]), legend=alt.Legend(orient="bottom", title=None)
            ),
            detail="run:N",
            tooltip=[alt.Tooltip("date:T", format="%Y-%m-%d"), "series", alt.Tooltip("cad:Q", format="$.2f")],
        )
        .properties(height=280),
        width="stretch",
    )
    rr = summ[(summ.item_id == ids[nm]) & (summ.policy == polname)].iloc[0]
    c1.caption(
        f"Breach weeks {rr.breach_rate:.0%} · average margin {rr.avg_margin:.1%} · {rr.changes_per_year:.0f} price changes per 52 scored observations"
    )
    st.subheader("Retrospective repricing cadence by item")
    show = rec.assign(Item=rec.item_id.map(names)).set_index("Item")[
        ["recommended_policy", "breach_rate_monthly_list", "breach_rate_recommended", "changes_per_year_recommended"]
    ]
    st.dataframe(
        show.rename(
            columns={
                "recommended_policy": "Recommended",
                "breach_rate_monthly_list": "Breach weeks, monthly list",
                "breach_rate_recommended": "Breach weeks, recommended",
                "changes_per_year_recommended": "Changes / 52 scored observations",
            }
        ).style.format(
            {
                "Breach weeks, monthly list": "{:.0%}",
                "Breach weeks, recommended": "{:.0%}",
                "Changes / 52 scored observations": "{:.0f}",
            }
        ),
        width="stretch",
        height=420,
    )

# ---------------------------------------------------------------- 6. budget
with tabs[5]:
    st.markdown(
        "FY budget, Feb 2024 to Jan 2025. Cost path = recent deseasonalised level × seasonal index. Move the levers; everything recalculates."
    )
    st.caption("Price delay applies to the scenario cost multiplier at both onset and reversal. A March–April shock with one-month lag affects customer prices in April–May. Demand is fixed apart from the volume control.")
    l1, l2, l3 = st.columns(3)
    shrink = l1.slider("Seasonal strength", 0.0, 1.0, 0.5, 0.25, help="0.5 was chosen on 2019-2020 and tested on 2023.")
    fx = l1.slider("CAD weaker vs USD (on imported share)", -0.10, 0.15, 0.0, 0.01, format="%.2f")
    shock = l2.slider(
        "Leafy & tomato cost shock, Mar-Apr",
        0.0,
        1.0,
        0.0,
        0.05,
        format="%.2f",
        help=f"A 1-in-10 month historically runs ~{facts['spike_p90']['Leafy & lettuce'] - 1:.0%} above its trailing 12-calendar-month reference (at least 8 observed months).",
    )
    lag = l2.select_slider("Months before prices catch up", [0, 1, 2], value=1)
    handling_up = l3.slider("Freight & handling cost increase (absorbed)", 0.0, 0.5, 0.0, 0.05, format="%.2f")
    volume = l3.slider("Volume change", -0.20, 0.20, 0.0, 0.01, format="%.2f")
    base = budget_base(panel, rows, basket, shrink)
    scen = bg.custom_scenario(
        base, fx_shock=fx, supply_shock=shock, handling_up=handling_up, volume_change=volume, price_lag_months=lag
    )
    m = st.columns(4)
    m[0].metric(
        "Revenue", f"${scen.revenue.sum() / 1e6:,.2f}M", delta=f"{scen.revenue.sum() - base.revenue.sum():+,.0f}"
    )
    m[1].metric(
        "Gross margin",
        f"${scen.gross_margin.sum() / 1e3:,.0f}K",
        delta=f"{scen.gross_margin.sum() - base.gross_margin.sum():+,.0f}",
    )
    m[2].metric("Gross margin %", f"{scen.gross_margin.sum() / scen.revenue.sum():.1%}")
    m[3].metric("Items budgeted", scen.item_id.nunique(), help="Only items with recent cost quotes and complete-year seasonal support are budgeted.")
    mon = pd.concat(
        [
            base.groupby("month").gross_margin.sum().rename("Base"),
            scen.groupby("month").gross_margin.sum().rename("Scenario"),
        ],
        axis=1,
    )
    mon = mon.reset_index().melt("month", var_name="case", value_name="gm")
    st.altair_chart(
        alt.Chart(mon)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X("month:N", title=None),
            xOffset="case:N",
            y=alt.Y("gm:Q", title="Gross margin (CAD)", axis=alt.Axis(format="$,.0f")),
            color=alt.Color(
                "case:N", scale=alt.Scale(range=[BLUE, ORANGE]), legend=alt.Legend(orient="bottom", title=None)
            ),
            tooltip=["month", "case", alt.Tooltip("gm:Q", format="$,.0f")],
        )
        .properties(height=300),
        width="stretch",
    )
    cat = (
        scen.groupby("category")[["revenue", "gross_margin"]]
        .sum()
        .assign(gm_pct=lambda x: x.gross_margin / x.revenue)
        .sort_values("revenue", ascending=False)
    )
    st.dataframe(
        cat.style.format({"revenue": "${:,.0f}", "gross_margin": "${:,.0f}", "gm_pct": "{:.1%}"}),
        width="stretch",
    )
    st.download_button("Download scenario budget (CSV)", scen.to_csv(index=False), file_name="budget_scenario.csv")

# ---------------------------------------------------------------- 7. method
with tabs[6]:
    st.markdown(
        """
**Source.** USDA AMS Market News, *Toronto, Canada Terminal Market* fruit, vegetable and onion/potato reports (TO_FV010/020/030);
USDA credits Infohort, Agriculture and Agri-Food Canada as the source. Prices are republished in USD; this project converts them
back to CAD with the Bank of Canada rate for each report date. The series ended on 2024-01-30.

**Cleaning.** Conventional (non-organic) quotes only; mid price = (low + high) / 2; item price = median across origins and sizes that week.
Week-over-week changes compare identical quotes only (same origin, size, package), so a switch from Mexico to Canada is not read as a price change.
"""
    )
    st.subheader("Weeks excluded: suspected currency-conversion anomalies")
    st.caption("Diagnoses are inferred from the cross-item pattern, not confirmed by USDA. Exclusion uses a centred window with future observations: backtests use retrospectively cleaned data and are not live as-of pricing simulations.")
    st.dataframe(
        dq.assign(date=dq.date.dt.date)[["date", "basket_ratio", "usd_cad", "diagnosis"]].rename(
            columns={"basket_ratio": "Basket vs neighbouring weeks", "usd_cad": "USD/CAD that week"}
        ),
        width="stretch",
    )
    st.markdown(
        """
**Conversion noise.** About 45% of quotes each week are unchanged in CAD but still move in USD because USDA's own weekly FX rate moves.
The most common week-over-week USD ratio across all quotes reveals that conversion factor; dividing it out makes an unchanged price read exactly 0.0%.

**Forecasting.** One to four weeks ahead, the latest price beat a moving average, exponential smoothing and seasonal models.
Seasonal indices use complete item-years with equal month weights. Weekly horizons use 7 × h calendar days with a two-day reporting tolerance; training years must precede the forecast origin.
Budget-horizon results and seasonal-strength validation are downloadable from the repository. The default 0.5 strength is a configurable assumption; compare it with the recomputed validation grid rather than treating it as guaranteed best.
"""
    )
    w = pd.read_csv(OUT / "budget_horizon_forecast_test_2023.csv").pivot(
        index="h_months", columns="model", values="wape"
    )
    w.index = [f"{h} month(s) ahead" for h in w.index]
    st.dataframe(
        w.rename(columns={"flat": "Flat (WAPE)", "seasonal": "Half-strength seasonal (WAPE)"}).style.format("{:.1%}"),
        width="stretch",
    )
    st.subheader("Data model and SQL")
    st.markdown(
        "The real-cost pricing replay is also built as a star schema (`sql/star_schema/schema.sql`): `dim_item`, "
        "`dim_segment`, `dim_date`, `fact_market_price` and `fact_sales_price`. The pipeline writes it to SQLite and to "
        "CSVs for Power BI (`outputs/star_schema/`, measures in `powerbi/measures.dax`). The queries below run live on it."
    )
    qname = st.selectbox(
        "Star-schema query",
        ["01_terms_profitability.sql", "02_margin_variance_by_month.sql", "03_reprice_list.sql"],
        key="sqlq",
    )
    st.code((ROOT / "sql" / "star_schema" / qname).read_text(encoding="utf-8"), language="sql")
    st.dataframe(dm.run_query(star_db(panel, basket), qname), width="stretch", height=280, hide_index=True)
    st.caption("Reproduce everything: `python run_pipeline.py && python build_commercial_demo.py && pytest -q`")

# ---------------------------------------------------------------- 8. commercial decision workflow
with tabs[7]:
    st.subheader("Customer profitability & pricing decisions")
    st.warning("SYNTHETIC COMMERCIAL DEMO: customer segments, five competitor comparators, discounts, rebates, volumes, delivery and spoilage are simulated. Public terminal quotes are cost proxies. This is not actual company performance.")
    commercial_week = st.selectbox("Commercial scenario week", sorted(panel.date.unique(), reverse=True),
                                   format_func=lambda d: str(pd.Timestamp(d).date()))
    sales = cm.demo_sales(panel, basket, commercial_week)
    if sales.empty:
        st.info("No comparable recent prior quotes. Select another report week.")
    else:
        competitors = cm.demo_competitors(sales)
        threshold = st.slider("Price increase requiring Finance review", 0.0, 0.30, 0.10, 0.01)
        profits = cm.profitability(sales)
        recommendations = cm.recommendations(sales, competitors, threshold)
        alerts = cm.procurement_alerts(panel, commercial_week)
        k = st.columns(3)
        k[0].metric("Demo net revenue", f"CAD {profits.revenue.sum():,.0f}")
        k[1].metric("Contribution after variable service", f"CAD {profits.contribution.sum():,.0f}")
        k[2].metric("Revenue-weighted contribution margin", f"{profits.contribution.sum() / profits.revenue.sum():.1%}")
        st.caption("Contribution includes 6% handling, 2% spoilage and per-case delivery assumptions; fixed overhead excluded. All prices are CAD per comparable case. Gross margin in the historical backtest excludes these extra service costs.")
        group = st.radio("Profitability breakdown", ["customer", "category", "item"], horizontal=True)
        summary = profits.groupby(group)[["revenue", "variable_cost", "contribution", "target_gap_dollars"]].sum()
        summary["margin_pct"] = summary.contribution / summary.revenue
        st.dataframe(summary.style.format({"revenue": "{:,.0f}", "variable_cost": "{:,.0f}",
                      "contribution": "{:,.0f}", "target_gap_dollars": "{:,.0f}", "margin_pct": "{:.1%}"}))
        st.subheader("Finance: reconciled contribution variance")
        bridge = cm.variance_bridge(sales)
        waterfall = bridge.copy()
        waterfall["end"] = waterfall.cad.cumsum()
        waterfall["start"] = waterfall.end - waterfall.cad
        waterfall.loc[waterfall.index[-1], ["start", "end"]] = [0, waterfall.cad.iloc[-1]]
        waterfall["kind"] = np.where(waterfall.cad >= 0, "Favourable", "Unfavourable")
        waterfall.loc[[0, len(waterfall) - 1], "kind"] = "Total"
        st.altair_chart(alt.Chart(waterfall).mark_bar().encode(
            x=alt.X("driver:N", sort=bridge.driver.tolist(), title=None),
            y=alt.Y("start:Q", title="Contribution (CAD)"), y2="end:Q",
            color=alt.Color("kind:N", scale=alt.Scale(domain=["Total", "Favourable", "Unfavourable"],
                                                      range=[BLUE, AQUA, RED]), title=None),
            tooltip=["driver", alt.Tooltip("cad:Q", format=",.2f", title="CAD")],
        ).properties(height=300), width="stretch")
        st.dataframe(bridge, hide_index=True)
        st.caption("Exact bridge: budget contribution + volume/mix + net price/discount + variable cost = actual contribution. Each effect is calculated by item and customer; aggregation preserves mix.")
        st.subheader("Sales: quote recommendations & approvals")
        st.caption("Suggested net price preserves the target margin. Competitor quotes are segment-specific and net of discounts/rebates; median +5% and the increase threshold trigger review. Uplift assumes unchanged demand. Contract terms require review.")
        st.dataframe(recommendations, hide_index=True)
        st.subheader("Procurement: supply-risk review queue")
        st.caption("Alerts: quote breadth below 60% of its recent median, lead-origin change or cost jump above 15%. These signals do not confirm a shortage or actual stock availability.")
        st.dataframe(alerts[alerts.review], hide_index=True)
        brief = cm.executive_brief(sales, recommendations, alerts)
        with st.expander("Stakeholder decision brief", expanded=True):
            st.markdown(brief)
        st.download_button("Download stakeholder brief", brief, "commercial_decision_brief.md")
        st.download_button("Download synthetic ERP-style sales", sales.to_csv(index=False), "SYNTHETIC_sales.csv")
        st.download_button("Download reviewed price candidates", recommendations.to_csv(index=False), "SYNTHETIC_price_candidates.csv")
        with st.expander("Competitor evidence & comparability"):
            st.dataframe(competitors, hide_index=True)
            st.caption("Five fictional comparators; only nonfuture CAD quotes with matching case units and age at most 14 days qualify. Replace with lawfully sourced, timestamped observations for a real implementation.")

# ---------------------------------------------------------------- 9. procurement decisions
with tabs[8]:
    st.subheader("Supplier bids: cost, yield & availability")
    st.info("Synthetic procurement case. Three fictional suppliers quote each supported item. Capacities, freight, spoilage, lead times and reliability are assumptions; terminal quotes provide the historical cost anchor.")
    constraints, context = st.columns([1, 2])
    with constraints:
        supplier_week = st.selectbox("Supplier quote date", sorted(panel.date.unique(), reverse=True),
                                     format_func=lambda d: str(pd.Timestamp(d).date()))
        lead_limit = st.slider("Maximum supplier lead time (days)", 0, 7, 2)
        reliability_floor = st.slider("Minimum assumed delivery reliability", 0.80, 1.0, 0.95, 0.01)
    bids = pc.demo_supplier_bids(panel, basket, supplier_week)
    evaluated, supplier_queue = pc.compare_supplier_bids(bids, basket, supplier_week, lead_limit, reliability_floor)
    supported = supplier_queue.supplier.ne("No feasible single supplier")
    with context:
        a, b = st.columns(2)
        a.metric("Items with a feasible single supplier", int(supported.sum()))
        b.metric("Items requiring sourcing review", int((~supported).sum()))
        st.caption("Weekly demand is usable cases. Orders include expected spoilage and must meet MOQ and capacity constraints. Quotes must match CAD and the case unit and be valid on the selected date.")
    st.dataframe(supplier_queue.rename(columns={
        "item": "Item", "supplier": "Supplier for review", "unit": "Case unit",
        "demand_usable_cases": "Usable cases needed", "order_cases": "Cases to order",
        "total_order_cost": "Order cost (CAD)", "cost_per_demand_case": "CAD per needed case",
        "single_supplier_shortfall_cases": "Single-supplier shortfall", "status": "Next action",
    }), hide_index=True)
    st.caption("The review choice has the lowest full-order cost among feasible single-supplier bids. MOQ surplus is charged to this week's demand. Split sourcing, shelf-life timing, inventory and customer demand response are outside this model.")
    with st.expander("Compare bids and exclusion reasons"):
        st.dataframe(evaluated, hide_index=True)
    st.download_button("Download supplier review queue", supplier_queue.to_csv(index=False), "SYNTHETIC_supplier_review.csv")
    st.download_button("Download evaluated supplier bids", evaluated.to_csv(index=False), "SYNTHETIC_supplier_evaluation.csv")

# ---------------------------------------------------------------- 10. customer terms & margin variance
with tabs[9]:
    segs, sd = terms_replay(panel, basket)
    st.markdown(
        "Four customer types buy the basket on different pricing terms. Prices are replayed on the real weekly cost path, "
        "so the difference between segments comes from how each set of terms copes with real market moves. "
        "Segment terms and volume shares are assumptions (`config/customer_terms.csv`). These are not the synthetic customers on the pricing desk."
    )
    spnl = segs[["segment_id", "segment", "pricing_policy", "terms"]].merge(ct.segment_pnl(sd), on="segment_id")
    spnl = spnl.merge(ct.monthly_gap_spread(sd), on="segment_id")
    k = st.columns(4)
    con = spnl.set_index("segment_id").loc["contract"]
    others = spnl[spnl.segment_id != "contract"]
    k[0].metric(
        "Gross margin, all segments",
        f"{spnl.gm.sum() / spnl.revenue.sum():.1%}",
        help="Seven years of replayed weekly pricing, 2017-2024.",
    )
    k[1].metric(
        "Contract weeks >10 pts under target",
        f"{con.breach_rate:.0%}",
        delta=f"{con.breach_rate - others.breach_rate.mean():+.0%} vs other segments",
        delta_color="inverse",
    )
    k[2].metric(
        "Contract monthly margin swing",
        f"{con.sd:.1f} pts",
        help="Standard deviation of monthly gross margin % around target.",
    )
    k[3].metric("Worst contract month", f"{con.worst:.0f} pts vs target")
    st.dataframe(
        spnl.set_index("segment")[["terms", "revenue", "gm_pct", "target_pct", "breach_rate", "sd", "worst"]]
        .rename(
            columns={
                "terms": "Pricing terms",
                "revenue": "Revenue",
                "gm_pct": "GM %",
                "target_pct": "Target GM %",
                "breach_rate": "Weeks >10 pts under",
                "sd": "Monthly swing (pts)",
                "worst": "Worst month (pts)",
            }
        )
        .style.format(
            {
                "Revenue": "${:,.0f}",
                "GM %": "{:.1%}",
                "Target GM %": "{:.1%}",
                "Weeks >10 pts under": "{:.0%}",
                "Monthly swing (pts)": "{:.1f}",
                "Worst month (pts)": "{:.1f}",
            }
        ),
        width="stretch",
    )
    st.info(
        "Every segment lands on target over seven years; the difference is risk. A fixed monthly contract list "
        f"spends {con.breach_rate:.0%} of item-weeks more than 10 points under target. Replayed with a band-rule escalator clause, "
        f"that falls to {tfacts['contract_band_breach_rate']:.0%}."
    )

    st.subheader("Gross margin against target, by month and cause")
    seg_pick = st.multiselect("Segments", list(segs.segment), default=list(segs.segment), key="var_segs")
    cat_pick = st.multiselect(
        "Categories", sorted(basket.category.unique()), default=[], key="var_cats", placeholder="All categories"
    )
    f = sd[sd.segment_id.isin(segs[segs.segment.isin(seg_pick)].segment_id)]
    if cat_pick:
        f = f[f.category.isin(cat_pick)]
    if f.empty:
        st.warning("Pick at least one segment.")
    else:
        mv = ct.monthly_variance(f)
        long = mv.melt("month", ["var_cost_timing", "var_price_hold"], var_name="cause", value_name="cad")
        long["cause"] = long.cause.map(
            {"var_cost_timing": "Cost timing (one-week quote lag)", "var_price_hold": "Price hold (list or band terms)"}
        )
        long["month"] = pd.to_datetime(long.month)
        st.altair_chart(
            alt.Chart(long)
            .mark_bar(width=6)
            .encode(
                x=alt.X("month:T", title=None),
                y=alt.Y("sum(cad):Q", title="GM vs target (CAD)", stack="zero"),
                color=alt.Color(
                    "cause:N",
                    scale=alt.Scale(range=[BLUE, ORANGE]),
                    legend=alt.Legend(orient="bottom", title=None, labelLimit=400),
                ),
                tooltip=[alt.Tooltip("month:T", format="%b %Y"), "cause", alt.Tooltip("cad:Q", format="$,.0f")],
            )
            .properties(height=300),
            width="stretch",
        )
        w = mv.sort_values("gap_pts").head(5)[
            ["month", "revenue", "gm_pct", "target_pct", "gap_pts", "var_cost_timing", "var_price_hold"]
        ]
        st.caption("Five worst months for this selection")
        st.dataframe(
            w.rename(
                columns={
                    "month": "Month",
                    "revenue": "Revenue",
                    "gm_pct": "GM %",
                    "target_pct": "Target %",
                    "gap_pts": "Gap (pts)",
                    "var_cost_timing": "Cost timing",
                    "var_price_hold": "Price hold",
                }
            )
            .set_index("Month")
            .style.format(
                {
                    "Revenue": "${:,.0f}",
                    "GM %": "{:.1%}",
                    "Target %": "{:.1%}",
                    "Gap (pts)": "{:.1f}",
                    "Cost timing": money,
                    "Price hold": money,
                }
            ),
            width="stretch",
        )
        st.caption(
            "Cost timing: quotes go out on last week's cost, so a week where cost jumps costs margin under any terms. "
            "Price hold: the extra cost of keeping a list or band price instead of resetting to last week's cost. "
            "The two add up exactly to gross margin minus gross margin at target."
        )

    st.subheader("Contract escalator clause: what it would change")
    wi = ct.contract_whatif(panel, basket, segs, sd)
    st.dataframe(
        wi.set_index("category")
        .rename(
            columns={
                "gm_pct_monthly": "GM %, monthly list",
                "gm_pct_band": "GM %, band clause",
                "breach_monthly": "Breach weeks, monthly",
                "breach_band": "Breach weeks, band",
                "gm_gain": "GM change ($)",
            }
        )
        .style.format(
            {
                "GM %, monthly list": "{:.1%}",
                "GM %, band clause": "{:.1%}",
                "Breach weeks, monthly": "{:.0%}",
                "Breach weeks, band": "{:.0%}",
                "GM change ($)": money,
            }
        ),
        width="stretch",
    )

    st.subheader("ERP price-list upload")
    weeks_b = sorted(sd.date.dt.date.unique(), reverse=True)
    wk = st.selectbox("Effective week", weeks_b[:-1], key="pl_week")
    plist = ct.price_list(sd, basket, segs, str(wk))
    c1, c2, c3 = st.columns(3)
    c1.metric("Price lines", len(plist))
    c2.metric("Increases", int((plist.reason == "COST_UP").sum()))
    c3.metric("Decreases", int((plist.reason == "COST_DOWN").sum()))
    st.dataframe(plist, width="stretch", height=300, hide_index=True)
    st.download_button(
        "Download price-list CSV", plist.to_csv(index=False), file_name=f"price_list_{wk}.csv", mime="text/csv"
    )

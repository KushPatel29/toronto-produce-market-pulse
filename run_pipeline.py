"""Run the whole analysis end to end: python run_pipeline.py
Writes processed data to data/processed/ and every deliverable to outputs/."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))
from pulse import budget as bg, forecast as fc, market as mk, pricing as pr, report as rp  # noqa: E402
from pulse.panel import build  # noqa: E402

OUT = Path("outputs")
OUT.mkdir(exist_ok=True)
REPORT_WEEKS = ["2024-01-30", "2022-12-13", "2020-03-23"]


def main():
    basket = pd.read_csv("config/basket.csv")
    raw, rows, panel, anomalies = build(save=True)

    # 1. Market intelligence
    idx = mk.basket_index(panel)
    chg = mk.annual_change(panel)
    si = mk.seasonal_index(panel)
    vol = mk.volatility(panel)
    prem = mk.origin_premium(rows)
    idx.to_csv(OUT / "basket_index_monthly.csv", index=False)
    chg.to_csv(OUT / "price_change_2019_vs_2023.csv", index=False)
    si.round(4).to_csv(OUT / "seasonal_index_by_month.csv")
    vol.to_csv(OUT / "volatility_by_item.csv", index=False)
    prem.to_csv(OUT / "origin_price_premium.csv", index=False)
    for item in ["tom_roma", "let_rom", "strawberries", "peppers"]:
        mk.origin_mix(rows, item).round(3).to_csv(OUT / f"origin_mix_{item}.csv")

    # 2. Pricing policy backtest
    detail, summ = pr.backtest(panel, basket)
    rec = pr.recommend_cadence(summ)
    summ.to_csv(OUT / "pricing_policy_backtest.csv", index=False)
    rec.to_csv(OUT / "pricing_cadence_recommendation.csv", index=False)

    # 3. Forecasting
    bt = fc.backtest(panel)
    sc = fc.score(bt)
    sc.to_csv(OUT / "forecast_backtest_weekly.csv", index=False)
    wk_tot = (
        bt.assign(ae=(bt.fcst - bt.actual).abs())
        .groupby(["window", "h", "model"])
        .apply(lambda g: g.ae.sum() / g.actual.sum(), include_groups=False)
        .rename("wape")
        .reset_index()
    )
    wk_tot.to_csv(OUT / "forecast_wape_weekly_summary.csv", index=False)
    test = fc.monthly_backtest(
        panel, (1, 3, 6), si_years=(2017, 2018, 2019, 2020), origin_range=("2022-11", "2023-12"), shrink=0.5
    )
    # Score the declared holdout calendar year only; origins may precede it.
    test = test[test.target_month.str.startswith("2023-")]

    def wape(t):
        return (
            t.assign(ae=(t.fcst - t.actual).abs())
            .groupby(["h_months", "model"])
            .apply(lambda g: g.ae.sum() / g.actual.sum(), include_groups=False)
            .rename("wape")
            .reset_index()
        )

    shrink_grid = []
    for sh in [0, 0.25, 0.5, 0.75, 1.0]:
        w = wape(fc.monthly_backtest(panel, (3, 6), shrink=sh))
        w["shrink"] = sh
        shrink_grid.append(w)
    pd.concat(shrink_grid).to_csv(OUT / "seasonal_strength_validation_2019_2020.csv", index=False)
    mt = wape(test)
    mt.to_csv(OUT / "budget_horizon_forecast_test_2023.csv", index=False)

    # 4. Budget and scenarios
    bud = bg.build_budget(panel, rows, basket)
    scen = bg.scenario_table(bud)
    sens = bg.sensitivity(bud)
    spikes = bg.historical_spike_quantiles(panel)
    bud.to_csv(OUT / "budget_fy2024_by_item_month.csv", index=False)
    scen.to_csv(OUT / "budget_scenarios.csv", index=False)
    sens.to_csv(OUT / "budget_sensitivity.csv", index=False)
    spikes.to_csv(OUT / "historical_spike_quantiles.csv", index=False)

    # 5. Weekly market updates
    for wk in REPORT_WEEKS:
        u = rp.market_update(panel, basket, wk)
        (OUT / f"market_update_{wk}.md").write_text(rp.to_markdown(u), encoding="utf-8")
        u["table"].to_csv(OUT / f"market_update_{wk}.csv", index=False)

    # 6. Headline facts for README / dashboard
    geo = float(np.exp(np.log(chg.avg_2023 / chg.avg_2019).mean()) - 1)
    pol = summ.groupby("policy")[["avg_margin", "margin_sd", "breach_rate", "changes_per_year"]].mean()
    t3 = mt[mt.h_months == 3].set_index("model").wape
    t6 = mt[mt.h_months == 6].set_index("model").wape
    w1 = wk_tot[(wk_tot.h == 1)].groupby("model").wape.mean()
    facts = {
        "quotes_raw": int(len(raw)),
        "report_weeks": int(raw.date.nunique()),
        "date_min": str(raw.date.min().date()),
        "date_max": str(raw.date.max().date()),
        "basket_items": int(basket.shape[0]),
        "basket_quotes": int(len(rows)),
        "item_weeks": int(len(panel)),
        "excluded_weeks": anomalies.assign(date=anomalies.date.dt.strftime("%Y-%m-%d"))[
            ["date", "basket_ratio", "diagnosis"]
        ].to_dict("records"),
        "basket_change_2019_2023_geo": geo,
        "items_up_2019_2023": int((chg.pct_chg > 0).sum()),
        "items_compared": int(len(chg)),
        "comparison_min_shared_months": int(chg.n_months.min()),
        "comparison_max_shared_months": int(chg.n_months.max()),
        "index_2023_avg": float(idx[idx.month_start.dt.year == 2023]["index"].mean()),
        "index_2019_avg": float(idx[idx.month_start.dt.year == 2019]["index"].mean()),
        "policy": pol.round(4).to_dict("index"),
        "cadence_counts": rec.recommended_policy.value_counts().to_dict(),
        "wape_1wk": w1.round(4).to_dict(),
        "budget_wape_3m": t3.round(4).to_dict(),
        "budget_wape_6m": t6.round(4).to_dict(),
        "budget": scen.round(2).to_dict("records"),
        "spike_p90": spikes.set_index("category").p90.round(3).to_dict(),
    }
    (OUT / "headline_facts.json").write_text(json.dumps(facts, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                k: facts[k]
                for k in [
                    "quotes_raw",
                    "report_weeks",
                    "basket_change_2019_2023_geo",
                    "cadence_counts",
                    "budget_wape_3m",
                    "budget_wape_6m",
                ]
            },
            indent=1,
            default=str,
        )
    )
    return facts


def charts():
    import pandas as pd
    from pulse import charts as ch
    from pulse.panel import build

    _, _, panel, _ = build(save=False)
    basket = pd.read_csv("config/basket.csv")
    names = dict(zip(basket.item_id, basket.display_name, strict=True))
    img = OUT / "img"
    img.mkdir(exist_ok=True)
    idx = pd.read_csv(OUT / "basket_index_monthly.csv", parse_dates=["month_start"])
    ch.basket_index(idx, img / "basket_index.png")
    ch.price_change(pd.read_csv(OUT / "price_change_2019_vs_2023.csv"), img / "price_change_2019_2023.png")
    ch.seasonality(
        pd.read_csv(OUT / "seasonal_index_by_month.csv", index_col=0).rename(columns=int),
        names,
        img / "seasonality.png",
    )
    ch.policies(pd.read_csv(OUT / "pricing_policy_backtest.csv"), img / "pricing_policies.png")
    ch.forecast_test(pd.read_csv(OUT / "budget_horizon_forecast_test_2023.csv"), img / "forecast_test_2023.png")
    ch.lettuce_crisis(panel, img / "lettuce_crisis_2022.png")
    ch.tornado(pd.read_csv(OUT / "budget_sensitivity.csv"), img / "budget_tornado.png")


def terms():
    """Customer pricing terms on real costs, margin-variance bridge, ERP price list and the star schema."""
    from pulse import charts as ch
    from pulse import datamodel as dm
    from pulse import terms as tm
    from pulse.panel import build

    _, _, panel, _ = build(save=False)
    basket = pd.read_csv("config/basket.csv")
    segs = pd.read_csv("config/customer_terms.csv")
    sd = tm.replay(panel, basket, segs)
    pnl = segs[["segment_id", "segment", "pricing_policy"]].merge(
        tm.segment_pnl(sd).merge(tm.monthly_gap_spread(sd), on="segment_id"), on="segment_id"
    )
    mvar = tm.monthly_variance(sd)
    yvar = tm.variance_by(sd.assign(year=sd.date.dt.year), ["year"])
    whatif = tm.contract_whatif(panel, basket, segs, sd)
    pnl.to_csv(OUT / "terms_profitability.csv", index=False)
    tm.segment_category(sd).to_csv(OUT / "terms_category_profitability.csv", index=False)
    mvar.to_csv(OUT / "margin_variance_by_month.csv", index=False)
    yvar.to_csv(OUT / "margin_variance_by_year.csv", index=False)
    tm.variance_by(sd, ["category"]).to_csv(OUT / "margin_variance_by_category.csv", index=False)
    whatif.to_csv(OUT / "contract_escalator_whatif.csv", index=False)
    plist = tm.price_list(sd, basket, segs, REPORT_WEEKS[0])
    plist.to_csv(OUT / f"erp_price_list_upload_{REPORT_WEEKS[0]}.csv", index=False)
    star = OUT / "star_schema"
    db = star / "market_pulse.sqlite"
    star.mkdir(exist_ok=True)
    dm.build(dm.tables(panel, basket, segs, sd), db, star)
    for q in ["01_terms_profitability", "02_margin_variance_by_month", "03_reprice_list"]:
        dm.run_query(db, f"{q}.sql").to_csv(star / f"query_{q}.csv", index=False)
    alt = tm.replay(panel, basket, segs[segs.segment_id == "contract"], {"contract": "band"})
    worst = mvar.sort_values("gap_pts").iloc[0]
    facts = {
        "terms": pnl.set_index("segment_id")[["gm_pct", "target_pct", "gap_pts", "breach_rate", "sd", "worst", "best"]]
        .round(4)
        .to_dict("index"),
        "contract_band_breach_rate": round(float(alt.breach.mean()), 4),
        "worst_month": {
            k: (v if isinstance(v, str) else round(float(v), 2))
            for k, v in worst[["month", "gap_pts", "var_total", "var_cost_timing", "var_price_hold"]].items()
        },
        "variance_total": round(float(sd.var_total.sum()), 2),
        "variance_cost_timing": round(float(sd.var_cost_timing.sum()), 2),
        "variance_price_hold": round(float(sd.var_price_hold.sum()), 2),
        "timing_share_of_abs_monthly_variance": round(
            float(mvar.var_cost_timing.abs().sum() / (mvar.var_cost_timing.abs() + mvar.var_price_hold.abs()).sum()), 4
        ),
        "months_timing_larger": round(float((mvar.var_cost_timing.abs() > mvar.var_price_hold.abs()).mean()), 4),
        "revenue_replayed": round(float(sd.revenue.sum()), 2),
        "item_weeks_scored": int(len(sd)),
        "price_list_rows": int(len(plist)),
        "price_list_week": REPORT_WEEKS[0],
    }
    (OUT / "terms_facts.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")
    img = OUT / "img"
    ch.terms_risk(pnl, img / "terms_risk.png")
    ch.margin_variance(mvar, img / "margin_variance.png")
    print(json.dumps({k: facts[k] for k in ["terms", "contract_band_breach_rate", "worst_month"]}, indent=1))
    return facts


if __name__ == "__main__":
    main()
    charts()
    terms()

"""Synchronize the portfolio README's quantitative claims with pipeline outputs."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"


def main():
    f = json.loads((OUT / "headline_facts.json").read_text(encoding="utf-8"))
    c = json.loads((OUT / "commercial_demo/validation_summary.json").read_text(encoding="utf-8"))
    t = json.loads((OUT / "terms_facts.json").read_text(encoding="utf-8"))
    rg = json.loads((OUT / "rgm/rgm_facts.json").read_text(encoding="utf-8"))
    br = rg["bridge"]
    bd = rg["breakeven_by_depth"]
    tc = t["terms"]["contract"]
    others = [t["terms"][k]["breach_rate"] for k in ("fine_dining", "casual", "hotels")]
    wm = t["worst_month"]
    policy_rows = "\n".join(
        f"| {label} | {f['policy'][key]['breach_rate']:.1%} | {f['policy'][key]['changes_per_year']:.1f} |"
        for key, label in [("monthly", "Monthly list"), ("band", "Margin band"), ("weekly", "Weekly repricing")]
    )
    import pandas as pd

    panel = pd.read_csv(ROOT / "data/processed/weekly_item_panel.csv", parse_dates=["date"])
    rom = panel[panel.item_id == "let_rom"]
    rom_2019 = rom[rom.date.dt.year == 2019].price_cad.mean()
    rom_peak = rom[rom.date.between("2022-11-01", "2023-03-31")].price_cad.max()
    pol = f["policy"]
    cad = f["cadence_counts"]
    text = f"""# Toronto Produce Market Pulse

**Pricing, margin and market intelligence for a foodservice produce distributor, built on {f['quotes_raw']:,} real Toronto wholesale prices.**

[![quality](https://github.com/KushPatel29/toronto-produce-market-pulse/actions/workflows/quality.yml/badge.svg)](https://github.com/KushPatel29/toronto-produce-market-pulse/actions/workflows/quality.yml)
[![Live app](https://img.shields.io/badge/live%20app-Streamlit-ff4b4b)](https://toronto-fresh-market-pulse.streamlit.app)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776ab)
![SQL](https://img.shields.io/badge/SQL-SQLite%20star%20schema-003b57)
![Excel](https://img.shields.io/badge/Excel-scenario%20model%20%2B%20PivotTable-217346)

[![The live app: market overview](docs/img/app_overview.jpg)](https://toronto-fresh-market-pulse.streamlit.app)

A distributor's pricing analyst has to answer the same questions every week: *what is the market doing, which prices need to move, where is margin leaking, and what does it mean for the budget?* This project answers them end to end on public Toronto terminal-market data (USDA AMS, credited to Infohort / Agriculture and Agri-Food Canada), {f['date_min'][:4]}–{f['date_max'][:4]}, converted to CAD.

> **Historical portfolio case study.** Public quotes run from {f['date_min']} to {f['date_max']}. Customers, competitors, suppliers, demand, freight and spoilage are synthetic or illustrative assumptions and are labelled as such. No Bondi company data, live ERP integration or realised savings are claimed.

## Start here

| If you have | Open | You will see |
|---|---|---|
| 2 minutes | [Live app](https://toronto-fresh-market-pulse.streamlit.app) | Eleven tabs: market overview, weekly update for any of {f['report_weeks'] - len(f['excluded_weeks'])} weeks, item explorer, price calculator, pricing policies, budget levers, customer pricing desk, supplier comparison, customer terms and margin variance, price-volume-mix and promotions |
| 5 minutes | [Stakeholder briefing (7 slides)](outputs/Produce_Pricing_Decision_Brief.pptx) | Pricing cadence, supply-shock lag, customer terms, margin variance, Finance bridge, supplier decisions |
| 10 minutes | [Excel decision model](outputs/Pricing_Decision_Workbook.xlsx) · [Margin variance workbook](outputs/Margin_Variance_and_Terms.xlsx) · [VBA pack](excel_vba/) | Live scenario formulas, native PivotTable, monthly variance bridge with zero-check columns, price-volume-mix waterfall, promotion break-even calculator, ERP price-list upload, VBA macros that validate and export the monthly pack |
| 15 minutes | [Power BI model as code](powerbi/) | TMDL semantic model: 8 tables, 38 DAX measures, row-level security, French translations |
| An interview | [Job-description map and walkthrough](docs/ROLE_COVERAGE.md) | Every responsibility mapped to evidence, with its limits |

## Results at a glance

| Question | Answer | Evidence |
|---|---|---|
| How much has the basket moved? | **{f['basket_change_2019_2023_geo']:+.1%}** from 2019 to 2023 on matched months; {f['items_up_2019_2023']} of {f['items_compared']} items rose | `outputs/price_change_2019_vs_2023.csv` |
| How fast can supply break? | Romaine reached **{rom_peak / rom_2019:.1f}x** its 2019 average (CAD {rom_peak:,.0f} vs {rom_2019:,.0f} a case) in the late-2022 lettuce crisis | Weekly update for 2022-12-13 |
| How often should prices change? | A 5-point margin band cuts weeks >10 points under target from **{pol['monthly']['breach_rate']:.1%} to {pol['band']['breach_rate']:.1%}** with {pol['band']['changes_per_year']:.0f} price changes a year, vs {pol['weekly']['changes_per_year']:.0f} for weekly repricing | `outputs/pricing_policy_backtest.csv` |
| Which customers carry the risk? | Fixed monthly contract prices: **{tc['breach_rate']:.0%}** of weeks >10 points under target vs about {sum(others) / len(others):.0%} for other terms; an escalator clause cuts it to **{t['contract_band_breach_rate']:.0%}** | `outputs/terms_profitability.csv` |
| Why did margin miss target? | Mostly timing: quoting on last week's cost is **{t['timing_share_of_abs_monthly_variance']:.0%}** of the monthly swing; price holds are the rest | `outputs/margin_variance_by_month.csv` |
| Can the budget forecast beat flat? | 6-month error **{f['budget_wape_6m']['seasonal']:.1%} vs {f['budget_wape_6m']['flat']:.1%}** on unseen 2023, with seasonal strength chosen on 2019–2020 only | `outputs/budget_horizon_forecast_test_2023.csv` |
| What drove gross margin, 2019 to 2023? | List price **+${br['List price']:,.0f}** and cost **−${-br['Cost']:,.0f}**; volume −${-br['Volume']:,.0f}, mix +${br['Mix']:,.0f}, discounts −${-br['Discounts & promotions']:,.0f} on synthetic volumes | `outputs/rgm/pvm_bridge_2019_2023.csv` |
| Do promotions pay back? | Only **{rg['paid_back']} of {rg['events']}**: a 10% cut needs **{bd['0.10']:.2f}x** baseline volume to break even once the fee and post-promotion dip count; lift estimates land within {rg['uplift_mae_pts']:.1f} points of the planted truth | `outputs/rgm/promotion_events.csv` |
| Do the numbers tie out? | Contribution bridge agrees between SQL and Python within CAD 0.001; the margin-variance bridge ties to the dollar in Python, SQL and Excel | `validate_release.py`, `tests/` |

## How it works

```mermaid
flowchart LR
    A[USDA AMS Toronto terminal reports<br/>{f['quotes_raw']:,} quotes, 2017-2024] --> C[Clean and validate<br/>CAD conversion, FX-noise removal,<br/>anomaly and gap detection]
    B[Bank of Canada USD/CAD] --> C
    C --> D[Weekly item panel<br/>{f['item_weeks']:,} item-weeks, 30 items]
    D --> E[Market intelligence<br/>index, seasonality, volatility, origins]
    D --> F[Pricing<br/>policy replay, cadence, customer terms]
    D --> G[Forecast and budget<br/>backtests, FY scenarios, sensitivity]
    D --> H[Margin variance<br/>cost timing vs price hold]
    D --> R[Revenue growth<br/>price-volume-mix, promotion ROI]
    S[Synthetic sales, competitor<br/>and supplier data] --> I[Pricing desk and procurement<br/>net price, contribution, supplier feasibility]
    E & F & G & H & I & R --> O[(Validated outputs<br/>CSV, SQLite, JSON<br/>tested and reconciled)]
    O --> J[Streamlit app]
    O --> K[Excel models +<br/>VBA monthly pack]
    O --> L[SQL star schema +<br/>Power BI TMDL model]
    O --> M[Weekly market update +<br/>briefing deck]
```

## What the evidence supports

### Market: the basket moved, unevenly

Across {f['items_compared']} items with at least 10 calendar months observed in both 2019 and 2023, case prices changed {f['basket_change_2019_2023_geo']:+.1%} on a geometric-mean basis; {f['items_up_2019_2023']} items rose. Months have equal weight. This selected-basket case-price comparison is not a full-year produce inflation estimate; origin and size mix may differ.

![Matched-month case prices](outputs/img/price_change_2019_2023.png)

### Supply shocks: the late-2022 lettuce crisis

Crop losses in California's Salinas Valley pushed romaine to CAD {rom_peak:,.0f} a case against a 2019 average of {rom_2019:,.0f}. The weekly Market Update for 2022-12-13 flags it with top movers, supply shifts and a reprice list ([report](outputs/market_update_2022-12-13.md)).

![Lettuce crisis](outputs/img/lettuce_crisis_2022.png)

### Pricing: a risk and friction trade-off

Each policy prices from the most recent prior cost and restarts after item-specific gaps over 14 days. Results are equal-item means on retrospectively cleaned costs and fixed illustrative demand.

| Policy | Scored observations >10 margin points below target | Price changes per 52 scored observations |
|---|---:|---:|
{policy_rows}

The calmest policy that keeps breaches under 10% of weeks is: monthly list for {cad.get('monthly', 0)} items, band rule for {cad.get('band', 0)}, weekly repricing for {cad.get('weekly', 0)}. Cadence choices are retrospective selections on the same history, not validated future recommendations.

![Pricing policies](outputs/img/pricing_policies.png)

### Customer terms change risk, not margin

Four customer types buy the basket on different terms, replayed on real weekly costs with the same gap rules. Each lands within 0.2 points of its target margin over the cycle, but a fixed monthly contract list spends {tc['breach_rate']:.1%} of scored weeks more than 10 points under target, against {min(others):.1%}–{max(others):.1%} for the others, and its monthly margin swings {tc['sd']:.1f} points against about 2. A band-rule escalator clause cuts contract breach weeks to {t['contract_band_breach_rate']:.1%}. Customer shares and terms are assumptions in `config/customer_terms.csv`, separate from the synthetic pricing-desk customers.

![Breach weeks and margin swing by customer terms](outputs/img/terms_risk.png)

### Margin variance by cause

Gross margin minus margin at target splits exactly into *cost timing* (quotes go out on last week's cost) and *price hold* (the extra cost of keeping a list or band price). Month by month, cost timing is {t['timing_share_of_abs_monthly_variance']:.0%} of the absolute swing and the larger cause in {t['months_timing_larger']:.0%} of months. The worst month, {wm['month']}, was {abs(wm['gap_pts']):.1f} points under target when lettuce costs tripled in one week; CAD {-wm['var_cost_timing']:,.0f} of the CAD {-wm['var_total']:,.0f} shortfall was cost timing.

![Monthly margin variance by cause](outputs/img/margin_variance.png)

### Price, volume, mix and promotions

Gross margin is bridged from 2019 to 2023 item by item: volume (total cases at the old mix and margin), mix (shifts between items), list price, discounts and promotions, and cost. On real terminal costs and synthetic shipments, list price added ${br['List price']:,.0f} and cost took ${-br['Cost']:,.0f}; volume took ${-br['Volume']:,.0f}, mix added ${br['Mix']:,.0f} and deeper discounts took ${-br['Discounts & promotions']:,.0f}. The bridge closes to the cent in Python and in Excel (a native waterfall chart with a zero check), and the Power BI measures return the same numbers in Power BI Desktop.

![Gross margin bridge](outputs/img/pvm_bridge.png)

Each of {rg['events']} synthetic promotions is scored against a baseline of clean weeks either side, net of the post-promotion dip and a fixed event fee. Break-even lift rises steeply with depth: {bd['0.10']:.2f}x baseline volume at 10% off, {bd['0.12']:.2f}x at 12%, {bd['0.15']:.2f}x at 15%. {rg['paid_back']} events paid back; the verdicts are {rg['verdicts']['Repeat']} repeat, {rg['verdicts']['Redesign']} redesign, {rg['verdicts']['Stop']} stop. Because the lift is planted in the simulation, the method can be checked: estimates land within {rg['uplift_mae_pts']:.1f} points of the truth on average. That validates the method, not any real promotion.

![Promotion lift vs break-even](outputs/img/promo_breakeven.png)

### Forecasts and the FY budget

In the calendar-2023 budget holdout, half-strength seasonality has 3-month WAPE {f['budget_wape_3m']['seasonal']:.1%} versus flat {f['budget_wape_3m']['flat']:.1%}; 6-month WAPE is {f['budget_wape_6m']['seasonal']:.1%} versus flat {f['budget_wape_6m']['flat']:.1%}. Strength 0.5 is the narrow joint minimum over 3- and 6-month validation horizons with origins in 2019–2020. Seasonal estimates use complete 12-month item-years with equal month weights. One to four weeks ahead, the latest price is the best forecast ({f['wape_1wk']['naive']:.1%} WAPE one week out), so the operational answer is to react fast. The FY budget runs on the seasonal path with FX, supply-shock, freight and volume scenarios; shock onset and reversal are both lagged.

![Budget sensitivity](outputs/img/budget_tornado.png)

### Commercial reconciliation

The latest synthetic week has CAD {c['revenue']:,.0f} revenue and CAD {c['contribution']:,.0f} contribution. Independent SQL and Python contribution totals agree within CAD 0.001. Contribution includes variable delivery and spoilage and excludes fixed overhead; the historical policy gross margin uses a different cost basis.

## Skills for the role

| Skill | Reviewable evidence |
|---|---|
| Pricing models | Prior-cost policy replay, cadence by item, price calculator, customer-terms replay, ERP-style price-list upload |
| Market analysis and updates | Public quotes in CAD, matched-month comparison, seasonality, origin shifts, weekly Market Update for any report week |
| Margin and profitability | Policy and customer-terms margins; revenue-weighted customer and product contribution; monthly margin-variance bridge |
| Revenue growth management | Price-volume-mix bridge, discount rate, promotion baseline and lift, break-even lift, trade-spend ROI with repeat/redesign/stop verdicts |
| Forecasting and budgeting | Calendar-origin backtests; FY budget with scenarios and one-at-a-time sensitivity |
| Scenario planning | Live FX, supply-shock, freight, volume and price-lag levers in the app and the Excel model |
| Advanced Excel and VBA | Decision model with live scenario formulas and a native PivotTable ([verification](docs/EXCEL_MODEL.md)); margin-variance workbook with zero-check columns, PVM waterfall and break-even grid; [VBA macros](excel_vba/) that validate, summarise, export to PDF and log the monthly pack |
| SQL and data management | SQLite financial views; star schema (`sql/star_schema/`) with three analysis queries; validated data contract |
| BI and dashboards | Eleven-tab Streamlit/Altair app; [Power BI semantic model as code](powerbi/) (TMDL/PBIP): star schema, 38 DAX measures, dynamic row-level security, fr-CA translations; the report page itself is left blank |
| Procurement | Yield- and freight-adjusted order costs with capacity, MOQ, lead-time and validity checks |
| Communication | Generated stakeholder brief and an editable seven-slide PowerPoint briefing |
| Process improvement | One-command rebuild, deterministic exports, source checksums, regression tests and CI on every push |

[Full job-description map and interview walkthrough](docs/ROLE_COVERAGE.md). Work samples cannot establish a degree, industry tenure or real employer collaboration.

## Why the numbers can be trusted

- **Source integrity:** SHA-256 checksums of the public snapshot are verified on every release (`config/source_manifest.json`).
- **Data-quality defects caught, not hidden:** four weeks where USDA's currency conversion failed (prices left in CAD or converted twice) are detected and excluded; exchange-rate noise is removed so an unchanged CAD price reads exactly 0.0%.
- **No bridged gaps:** the April 2021 – November 2022 source gap and item-specific gaps are never treated as one week, in models or charts.
- **Reconciliation:** financial identities are tested in Python and re-computed independently in SQL and Excel.
- **Automated checks:** `pytest` covers financial identities, hand-calculated lag paths, missing calendar periods, future-data invariance, invalid and duplicate records, and the real Streamlit controls; GitHub Actions runs lint, tests and release validation on every push.

## Reproduce it

```bash
python -m pip install -r requirements-lock.txt
python run_pipeline.py            # clean data, analyses, charts, customer terms, star schema, PVM and promotions
python build_commercial_demo.py   # synthetic pricing desk and supplier comparison
python build_terms_workbook.py    # margin-variance workbook (terms, variance, PVM, promotions)
python build_powerbi_model.py     # Power BI TMDL model
python add_terms_slides.py        # customer-terms slides in the briefing
python build_project_docs.py      # this README, numbers synced from outputs
python build_report_page.py
python validate_release.py
python -m pytest -q && ruff check .
streamlit run app.py
```

Tested on Python 3.12. CSV, Markdown, SQLite and HTML files regenerate from committed sources. The decision workbook and the five base briefing slides are editable delivery snapshots; the margin-variance workbook and the two customer-terms slides are rebuilt by script. The original 13-sheet workbook is kept as a historical artifact.

```
src/pulse/panel.py        cleaning, FX and retrospective anomaly detection
src/pulse/market.py       matched months, complete-year seasonality, calendar risk
src/pulse/pricing.py      prior-cost policy replay with item-gap resets
src/pulse/forecast.py     calendar origins and prior-year training
src/pulse/budget.py       scenarios and lagged shock reversal
src/pulse/report.py       weekly Market Update generator
src/pulse/commercial.py   net-price comparability and customer contribution
src/pulse/procurement.py  synthetic supplier feasibility and order cost
src/pulse/terms.py        customer pricing terms, margin-variance bridge, ERP price list
src/pulse/rgm.py          price-volume-mix bridge and promotion evaluation
src/pulse/datamodel.py    star schema -> SQLite and Power BI CSVs
sql/                      financial views and star-schema queries
powerbi/                  TMDL semantic model (PBIP), DAX measures
excel_vba/                VBA modules for the monthly pack and ERP export
app.py                    Streamlit app (11 tabs)
tests/                    pytest suite, run in CI
```

## Sources and limits

- Public snapshot: USDA AMS MyMarketNews Toronto reports TO_FV010/020/030, credited to Infohort/AAFC; Bank of Canada report-date USD/CAD. Raw snapshot has 69,104 rows; {f['quotes_raw']:,} valid unique quotes remain after cleaning. The 30-item basket is a subset. [USDA portal](https://mymarketnews.ams.usda.gov/) · [Bank of Canada Valet](https://www.bankofcanada.ca/valet/docs).
- Four anomaly exclusions use a centred window and inferred conversion diagnoses. Backtests are conditional on retrospective cleaning, not fully as-of live simulations.
- There is a major April 2021–November 2022 gap plus item-specific gaps. No live daily or current-news feed is claimed.
- Terminal quotes are cost proxies, not invoices or distributor selling prices. Quote counts are not volumes or confirmed availability.
- Shipment volumes and promotion events in the price-volume-mix and promotion analysis are synthetic, built on real costs, so the method can be checked against a planted truth; they are not a distributor's results.
- Commercial and supplier data are fictional. No causal elasticity, demand response, split-supplier optimisation or realised savings are inferred.
- Budget scenarios lag shock multipliers while retaining the baseline seasonal price path. Inventory financing, fixed overhead and customer contracts are excluded.

[Review and operation](docs/REVIEW_AND_OPERATIONS.md)

---

Built by **Kush Patel**, data analyst in the Greater Toronto Area · [LinkedIn](https://www.linkedin.com/in/kush-patel-48885719b) · [Portfolio](https://kushpatel29.github.io) · [GitHub](https://github.com/KushPatel29)
"""
    (ROOT / "README.md").write_text(text, encoding="utf-8")
    print("README synchronized with analysis outputs")


if __name__ == "__main__":
    main()

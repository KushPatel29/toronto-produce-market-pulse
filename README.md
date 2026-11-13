# Toronto Produce Market Pulse

Pricing, market intelligence and procurement decisions for a foodservice produce distributor.

[Open the live app](https://toronto-fresh-market-pulse.streamlit.app) · [Stakeholder briefing](outputs/Produce_Pricing_Decision_Brief.pptx) · [Excel decision model](outputs/Pricing_Decision_Workbook.xlsx) · [Margin variance workbook](outputs/Margin_Variance_and_Terms.xlsx) · [Power BI model](powerbi/README.md)

**Historical portfolio case study.** Public terminal quotes run from 2017-01-02 to 2024-01-30. Customers, competitors, suppliers, demand, freight and spoilage are synthetic assumptions. No Bondi company data, actual ERP integration or realised business savings are claimed.

## A pricing meeting, end to end

1. **Market overview and weekly update:** historical case prices, matched quote movements, origin changes and seasonality. Try the December 2022 lettuce disruption.
2. **Pricing policies:** compare margin risk with customer price-change frequency. Policies use recent prior cost and restart after item-specific gaps over 14 days.
3. **Budget & scenarios:** change FX, cost, handling, volume and price delay. Both onset and reversal are delayed: a March–April cost shock with one-month lag affects prices in April–May.
4. **Customer & pricing desk:** net prices after discounts/rebates, contribution after variable service costs, segment-specific competitor comparisons and explicit review thresholds.
5. **Supplier comparison:** three fictional suppliers compared on full order cost, usable yield, MOQ, capacity, lead time, reliability and quote validity. Escalate items with no feasible single supplier.
6. **Finance and stakeholder reporting:** reconciled contribution bridge, generated written brief, SQLite views and editable Excel/PowerPoint deliverables.
7. **Customer terms & margin variance:** four customer types on weekly, band or fixed monthly terms, replayed on real costs; monthly margin variance split into cost timing and price hold; contract escalator test; ERP-style price-list upload for any week.

## What the evidence supports

**Matched-month comparison.** Across 18 items with at least 10 calendar months observed in both 2019 and 2023, case prices changed +14.2% on a geometric-mean basis; 15 items rose. Months have equal weight. This selected-basket case-price comparison is not a full-year produce inflation estimate; origin/size mix may differ. Exact support is in `outputs/price_change_2019_vs_2023.csv`.

![Matched-month case prices](outputs/img/price_change_2019_2023.png)

**Pricing is a risk/friction tradeoff.** These are equal-item means on retrospectively cleaned costs and fixed illustrative demand.

| Policy | Scored observations >10 margin points below target | Price changes per 52 scored observations |
|---|---:|---:|
| Monthly list | 18.5% | 11.9 |
| Margin band | 11.2% | 21.9 |
| Weekly repricing | 11.1% | 50.5 |

Cadence choices are retrospective selections on the same history, not validated future recommendations.

**Forecasts versus a baseline.** In the calendar-2023 budget holdout, half-strength seasonality has 3-month WAPE 27.4% versus flat 29.1%; 6-month WAPE is 24.4% versus flat 27.0%. Strength 0.5 remains the narrow joint minimum over 3/6-month validation horizons with origins in 2019–2020. Seasonal estimates use complete 12-month item-years with equal month weights. Weekly horizons are calendar days with a two-day report tolerance; training years precede each origin.

**Customer terms change risk, not margin.** Four customer types buy the basket on different terms, replayed on real weekly costs with the same gap rules as the policy backtest. Each lands within 0.2 points of its target margin over the cycle, but a fixed monthly contract list spends 19.2% of scored weeks more than 10 points under target, against 10.8%–11.3% for the others, and its monthly margin swings 5.8 points against about 2. A band-rule escalator clause cuts contract breach weeks to 11.7%. Customer shares and terms are assumptions in `config/customer_terms.csv`, separate from the synthetic pricing-desk customers.

![Breach weeks and margin swing by customer terms](outputs/img/terms_risk.png)

**Margin variance by cause.** Gross margin minus margin at target splits exactly into *cost timing* (quotes go out on last week's cost) and *price hold* (the extra cost of keeping a list or band price). Month by month, cost timing is 72% of the absolute swing and the larger cause in 88% of months. The worst month, 2018-11, was 10.2 points under target when lettuce costs tripled in one week; CAD 9,937 of the CAD 11,967 shortfall was cost timing. The bridge reconciles in Python, SQL and Excel.

![Monthly margin variance by cause](outputs/img/margin_variance.png)

**Commercial reconciliation.** The latest synthetic week has CAD 31,947 revenue and CAD 8,076 contribution. Independent SQL/Python contribution totals agree within CAD 0.001. Contribution includes variable delivery/spoilage and excludes fixed overhead; historical policy gross margin uses a different cost basis.

## Evidence for the role

| Skill | Reviewable evidence |
|---|---|
| Python, analysis and BI | Ten-tab Streamlit/Altair app; calendar backtests; scenario modules |
| Power BI-ready model | Star schema (`sql/star_schema/`) exported to CSV with DAX measures and relationships in `powerbi/`; no .pbix file is claimed |
| Margin variance | Monthly bridge: cost timing + price hold = gross margin − margin at target, tested to reconcile in Python, SQL and Excel |
| Advanced Excel | New editable decision model, formulas and customer summary; [Excel verification](docs/EXCEL_MODEL.md) |
| Financial analysis | Reconciled contribution bridge; revenue-weighted customer and product margins |
| Market/competitor intelligence | Public historical quotes and segment-specific synthetic net-price comparisons |
| Procurement | Yield/freight-adjusted order costs with capacity and service constraints |
| ERP-style data / SQL | Validated synthetic sales schema, SQLite facts/dimension and financial views; star-schema queries; ERP-style price-list upload file |
| Communication | Generated stakeholder brief and editable seven-slide PowerPoint briefing |
| Automation / detail | Deterministic exports, source checksums, regression tests, app controls and CI |

[Full JD map and interview walkthrough](docs/ROLE_COVERAGE.md). Work samples cannot establish a degree, industry tenure or real employer collaboration.

## Reproduce the analysis

```bash
python -m pip install -r requirements-lock.txt
python run_pipeline.py
python build_commercial_demo.py
python build_terms_workbook.py
python add_terms_slides.py
python build_project_docs.py
python build_report_page.py
python validate_release.py
python -m pytest -q
ruff check .
streamlit run app.py
```

Tested on Python 3.12. CSV/Markdown/SQLite/HTML files regenerate from committed sources. The decision workbook and the five base briefing slides are editable delivery snapshots; the margin-variance workbook and the two customer-terms slides are rebuilt by script. The original 13-sheet workbook is retained separately as a historical artifact.

```
src/pulse/panel.py        cleaning, FX and retrospective anomaly detection
src/pulse/market.py       matched months, complete-year seasonality, calendar risk
src/pulse/pricing.py      prior-cost policy replay with item-gap resets
src/pulse/forecast.py     calendar origins and prior-year training
src/pulse/budget.py       scenarios and lagged shock reversal
src/pulse/commercial.py   net-price comparability and customer contribution
src/pulse/procurement.py  synthetic supplier feasibility and order cost
src/pulse/terms.py        customer pricing terms, margin-variance bridge, ERP price list
src/pulse/datamodel.py    star schema -> SQLite and Power BI CSVs
sql/commercial_views.sql financial and customer views
sql/star_schema/          star schema and three analysis queries
powerbi/                  DAX measures and model notes
outputs/commercial_demo/ exports and SQLite database
```

## Sources and limits

- Public snapshot: USDA AMS MyMarketNews Toronto reports TO_FV010/020/030, credited to Infohort/AAFC; Bank of Canada report-date USD/CAD. Raw snapshot has 69,104 rows; 68,593 valid unique quotes remain after cleaning. The 30-item basket is a subset. [USDA portal](https://mymarketnews.ams.usda.gov/) · [Bank of Canada Valet](https://www.bankofcanada.ca/valet/docs).
- Four anomaly exclusions use a centred window and inferred conversion diagnoses. Backtests are conditional on retrospective cleaning, not fully as-of live simulations.
- There is a major April 2021–November 2022 gap plus item-specific gaps. No live daily or current-news feed is claimed.
- Terminal quotes are cost proxies, not invoices or distributor selling prices. Quote counts are not volumes or confirmed availability.
- Commercial and supplier data are fictional. No causal elasticity, demand response, split-supplier optimisation or realised savings are inferred.
- Budget scenarios lag shock multipliers while retaining the baseline seasonal price path. Inventory financing, fixed overhead and customer contracts are excluded.

[Review and operation](docs/REVIEW_AND_OPERATIONS.md)

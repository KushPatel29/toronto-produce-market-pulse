# Bondi Data Analyst: evidence and boundaries

This is a portfolio case study aligned to the supplied job description, not work commissioned by Bondi. It cannot establish employment tenure, a degree, work authorization, or experience collaborating inside an employer.

| Job responsibility / skill | Reviewable project evidence | Boundary |
|---|---|---|
| Pricing model management | Lagged weekly/monthly/band policy replay; cost-plus calculator; customer quote recommendations | Target margins and volumes are assumptions; no causal demand model |
| Multiple product lines and customer segments | 30-item basket; three simulated customer segments with discount and rebate waterfalls | Customer records are synthetic |
| Commodity market analysis | Public terminal quotes, CAD conversion, item price history and seasonal calendar | Historical dataset ends January 2024; not a live commodity feed |
| Competitor pricing | Five fictional comparators; timestamp, currency and pack-size comparability checks | Demonstrates a workflow, not real competitor intelligence |
| Market updates | Historical weekly report generator and downloadable stakeholder brief | Daily reporting is unsupported by a weekly discontinued source |
| Product/customer profitability | Weighted contribution margin by item, category and customer; delivery/spoilage assumptions. Gross margin by customer pricing terms on real costs | Contribution is before fixed overhead; customer terms and shares are assumptions |
| Margin variance against target | Monthly bridge: cost timing + price hold = gross margin − margin at target; worst months and causes; reconciled in Python, SQL and Excel | Historical replay on fixed volumes; not actual invoices |
| Price adjustments / risk | Target margin floor, increase threshold, competitor review threshold and approval owner | Suggestions require human review; uplift assumes unchanged volume |
| Sales, Procurement, Operations, Finance | Sales quote queue, Procurement signal queue, service-cost assumptions, reconciled Finance bridge | Simulates stakeholder handoffs; does not prove real workplace collaboration |
| Forecasting | Rolling-origin naive, moving-average, exponential smoothing and seasonal comparisons | Short-horizon models use a retrospectively cleaned panel; anomaly exclusions are not an as-of live cleaning simulation |
| Budgeting and projections | Historical FY2024 revenue/cost/gross-margin budget, scenarios and sensitivity | No actual company budget or realised outcomes |
| Dashboards / BI | Ten-tab interactive Streamlit/Altair app; Power BI-ready star schema with DAX measures and relationships (`powerbi/`) | No .pbix or Tableau workbook is claimed; the measures reproduce the Python and SQL totals |
| Reporting / presentations | Markdown reports and an editable seven-slide PowerPoint decision briefing, including customer terms and margin variance | Slides rendered and inspected; no actual employer presentation is claimed |
| Advanced Excel / Office | New decision workbook with live scenario formulas and a real customer PivotTable; margin-variance workbook with reconciliation checks | Monthly and annual figures tie to Python; native Excel recalculation and PivotTable refresh checked; see EXCEL_MODEL.md |
| Ad-hoc procurement | Three synthetic supplier bids per supported item with freight, spoilage, MOQ, capacity, lead time, reliability and validity checks | Compares feasible single-supplier orders; inventory and split-sourcing optimisation are excluded |
| ERP / data management | Validated ERP-style sales schema; runnable SQLite facts, item dimension and financial views; star schema; ERP-style price-list upload (item × price group, effective dates, reason codes); SQL/Python total reconciliation | No SAP, NetSuite, Dynamics or other live ERP integration |
| Scenario / sensitivity / problem-solving | Combined FX, cost, volume and pricing-delay controls; pricing policy stress replay | Fixed demand and simplified pricing-delay assumptions; not an optimisation engine |
| Process improvement / automation | Reproducible exports, generated brief, tests and CI configuration | Refresh is a reproducible historical build, not an automatic live data feed |
| Detail / communication / urgency | Explicit units, stale quote checks, financial identities, labelled approvals | Soft skills and performance under pressure must be supported with real interview examples |

## Five-minute interview walkthrough

1. Explain the source, historical cutoff, missing period and separation between public quotes and synthetic transactions.
2. Show December 2022 in the weekly report. Explain why last-known cost causes margin risk when lettuce spikes.
3. Compare monthly, band and weekly policies. Describe risk and customer price-change frequency rather than claiming revenue uplift.
4. Open Customer & pricing desk. Explain net price after discounts/rebates, service costs, weighted contribution, and a market-threshold conflict requiring Finance review.
5. Reconcile the Finance bridge and show Procurement's proxy alerts and supplier comparisons. Explain why the cheapest nominal supplier may fail the capacity or lead-time constraint. Open the Excel scenario model and briefing. Close with what would be needed in production: actual invoices, inventory, supplier quotes, contract terms and approved competitor evidence.

## Resume wording supported by the upgraded project

“Built a Python/SQL/Streamlit produce pricing case study using public Toronto wholesale data, with calendar-aware policy backtests, seasonal budgeting, customer contribution analysis and synthetic supplier comparisons. Developed an Excel scenario model with a native PivotTable, reconciled financial outputs across Python/SQL/Excel, and produced a stakeholder decision briefing.”

Do not describe simulated recovery as achieved savings or say this project supplies years of food-manufacturing experience.

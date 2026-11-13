# Review and operation

This final upgrade was reviewed against the supplied Bondi Data Analyst job description. The app has ten analytical views plus a native Excel decision model, a margin-variance workbook and a seven-slide PowerPoint briefing (two slides on customer terms and margin variance were added after the five-slide snapshot). It uses public historical quotes and clearly labelled synthetic commercial examples.

## Corrections from the second review

- Pricing replay now restarts after item-specific gaps longer than 14 days, rather than only at the major source gap. First returning quotes are not scored against stale costs.
- Weekly forecasting uses calendar origins (7 × horizon days, with two-day reporting tolerance). Complete training years precede the forecast origin. Smoothing restarts after gaps.
- Seasonality uses complete 12-month item-years and equal monthly weights. Four-week volatility requires calendar support; unknown changes are excluded from its denominator.
- The 2019/2023 comparison now requires at least 10 shared calendar months and equal-month weighting. It supports 18 items and +14.25%, replacing the unsupported 28-full-year-items/+10% claim.
- The budget delays both the onset and reversal of cost shocks. Combined shocks use the prior month's exposure, not the current month's. Historical shock quantiles use calendar rolling windows.
- Competitor comparisons match customer segment, net price basis, CAD, case unit and quote age. Contradictory duplicates are excluded. A held above-market price is distinguished from a target-margin/market conflict.
- Supplier review compares full order cost after freight, expected spoilage and MOQ, with capacity, validity and service constraints.

## Validation

Run the commands in the README for the exact release checks. The final checks cover financial identities, hand-calculated lag paths, missing calendar periods, future-data invariance, invalid and duplicate records, competitor comparability, supplier feasibility, source checksums, all 265 historical report dates and actual Streamlit controls.

The new Excel workbook was recalculated with both Artifact Tool and Microsoft Excel. All monthly/annual totals reconciled to Python for Base, Supply shock and Custom. A real native customer PivotTable was edited/refreshed/tested and restored; final cached formula-error count was zero. See EXCEL_MODEL.md. All five presentation slides were rendered and visually inspected; chart/table geometry and financial bridge arithmetic were checked. Excel and PowerPoint are editable delivery snapshots, separate from the reproducible Python/SQL analysis outputs.

## Scope and limits

The conversion-anomaly detector uses a centred window with future observations. Diagnoses are inferred, not publisher-confirmed. Historical backtests are conditional on retrospective cleaning; they are not fully as-of live performance tests. Cadence selection is retrospective on the same history used for evaluation.

Terminal quotes are cost proxies, not invoices or selling prices. Quote counts do not establish sales volume or supplier availability. The snapshot ends January 2024. Customer/supplier/competitor names and commercial inputs are synthetic. Contribution includes variable service costs and excludes fixed overhead. Policy backtest gross margin uses a different basis. No causal elasticity, demand response, actual savings, live ERP access or split-supplier optimisation is claimed.

The original 13-sheet workbook and PDFs remain historical artifacts. Use the new Pricing_Decision_Workbook.xlsx, the current app and regenerated CSV/Markdown reports for this upgrade.

## Data contract and operation

Sales grain is date/item/customer. Keys must be populated and unique; dates valid; financial fields numeric, finite and nonnegative; prices positive; target margins below 95%. Competitor evidence must match segment, net price basis, CAD and case unit, with an as-of quote no more than 14 days old. Supplier bids additionally require quote validity, feasible order quantity and agreed service thresholds.

Public source text checksums (line endings normalized to LF) are in config/source_manifest.json. validate_release.py checks those hashes, panel keys, report coverage and the independent SQL bridge. Checksums prove snapshot integrity, not publisher verification. No personal records, production credentials or customer data are included.

A production rollout would require approved ERP/invoice/inventory data, supplier costs and pack conversions, GL controls, contracts, actual demand response and an audited as-of cleaning process.

## Publish and rollback

The existing Streamlit app is linked to the repository main branch. Verify the rebuilt app after pushing. GitHub CI runs code checks, tests, commercial export and source/report/SQL validation. Revert the release commit and push the revert if a regression is found.

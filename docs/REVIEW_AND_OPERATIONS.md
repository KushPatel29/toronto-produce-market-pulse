# Final review and operation

Validation completed on 2026-11-13 with Python 3.12, pandas 3.0.6 and Streamlit 1.64.0: **28 pytest cases passed**, Ruff passed, all **265** historical weekly reports rendered, and the commercial SQLite/Python totals agreed within CAD 0.001. AppTest exercised budget/approval controls, the first report week and a zero list price. The local app was also inspected in a browser.

## Changes

- Prevented the weekly report's prior-cost reference from borrowing pre-gap data. Missing recent reference prices now show “Insufficient recent history” instead of “Hold”.
- Restarted forecast smoothing state after a gap longer than 14 days.
- Fixed Streamlit cache keys: panel/basket inputs are now hashed rather than excluded through underscore-prefixed arguments.
- Added a customer contribution workflow, fictional competitor comparability checks, explicit pricing approvals, quote-based procurement alerts and a downloadable executive brief.
- Added executable SQL financial views and deterministic commercial exports.
- Added regression tests for financial identities, stale/future/wrong-unit competitor exclusion, invalid inputs, future-data invariance, source gaps and actual Streamlit controls.

## Deliberate limitations

The original conversion-anomaly detector uses a centred nine-observation window, so the four exclusions use future observations. Currency-conversion diagnoses are inferred from the pattern, not confirmed by the publisher. Historical model comparisons therefore operate on a retrospectively cleaned dataset; they do not prove live-trading or live-pricing performance. No causal demand response or elasticity has been estimated. Cost shocks and demand are not jointly modelled.

The pre-existing FY2024 budget uses a simplified price-catch-up scenario: prices recover during the shocked months; it does not model a contract price lingering after a temporary shock ends. Its annual sensitivity table uses one-at-a-time approximations. Treat both as illustrations, not production cash-flow forecasts. The existing Excel workbook and PDFs are retained historical artifacts; use the regenerated CSV/Markdown files and current app for this upgrade's outputs.

USDA terminal quotes are neither procurement invoices nor distributor selling prices. Report counts are not traded volumes; quote breadth does not establish availability. Customer contribution includes simulated delivery/spoilage costs, while the original gross-margin backtest includes only the 6% handling assumption. Compare each measure on its own basis.

## Run locally

```bash
python -m pip install -r requirements.txt
python run_pipeline.py
python build_commercial_demo.py
python -m pytest -q
ruff check .
streamlit run app.py
```

`ruff` is a developer dependency: install with `python -m pip install ruff`.
The app runs from committed processed files and requires no API key or personal information.
The commercial export is deterministic; `outputs/commercial_demo/demo_analytics.sqlite` can be queried with standard SQLite tools.

## Data contract and real deployment

Sales grain is one selected-week/item/customer record. Required fields: date, item_id, customer, target_margin, budget/actual cases, budget/actual net selling price, budget/actual variable unit cost. Keys must be unique; financial fields must be finite and nonnegative; prices must be positive; margins must be below 95%. Competitor evidence must match item, case unit and CAD currency, and be dated between the report date and 14 days earlier.

A production connector would need approved read access to ERP invoices, credits, customer contracts, supplier costs, inventory and case-unit conversions. Reconcile invoice totals to the GL, account for returns, missing FX, landed-cost allocations and customer-specific terms. No uploaded production records or credentials are included in this project.

## Publish and rollback

The existing Streamlit Community Cloud application is linked to this repository. A push to its configured branch normally triggers a rebuild. Verify the build and all eight tabs on the live app after publication. If needed, revert the upgrade commit and push the revert. Local tests establish local behavior only; do not claim a live rollout until the live application has been observed.

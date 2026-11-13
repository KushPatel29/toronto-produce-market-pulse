# Pricing decision workbook

`outputs/Pricing_Decision_Workbook.xlsx` is the current five-sheet Excel companion. The legacy workbook remains unchanged as an earlier historical artifact.

Use the numeric selector in **Scenario!C4**: 1 Base, 2 Supply shock, 3 Custom. Amber cells with blue text are editable case assumptions. The active driver rows select one set of assumptions for one monthly forecast build. Blank inputs in an unselected case do not block Base; selecting a blank required input exposes `#N/A`.

The forecast covers February 2024 through January 2025. Source costs and seasonal baseline prices are prepared by the project's Python budget model. Volumes, target margins, the 6% source handling basis and the commercial transactions are illustrative assumptions. Public wholesale quotes end January 2024; no Bondi company data is used.

The combined FX/supply cost multiplier is shifted by calendar month to determine the selling-price multiplier. Both shock onset and reversal are delayed. Handling increases are absorbed; volume changes affect cases. Changing one input updates the same forecast, summary and monthly chart. Monthly and annual gross margin equals revenue less COGS.

**Commercial** contains live transaction and customer contribution formulas, plus a native customer PivotTable. Refresh the PivotTable after editing its source inputs. The customer demo is separate from the FY budget and excludes fixed overhead.

## Validation performed

- Authored with the bundled Artifact Tool. Recalculated and scanned with no formula errors.
- All 12 monthly and annual Revenue/COGS/Gross-margin results matched Python to CAD 0.01 for Base, 40% supply shock and combined Custom scenarios.
- Independently recalculated all three cases in Microsoft Excel Desktop. Tested a volume input change and selected/unselected blank inputs, then restored all values to Base.
- Added the native PivotTable through Excel's object model because Artifact Tool does not expose reliable PivotTable export. Its contribution total reconciled to Python. Changed one source price, refreshed the PivotTable, verified the expected contribution change and restored the source.
- Rendered and inspected all five sheets. The workbook is saved on Summary with Base selected.

Base annual revenue is CAD 1,623,277.57, COGS CAD 1,188,115.15 and gross margin CAD 435,162.42. The supply-shock illustration produces gross margin CAD 443,672.64 under fixed-volume cost-plus assumptions. That model result is not a claim that a supply disruption improves actual business outcomes: demand response and customer contract constraints are not estimated.

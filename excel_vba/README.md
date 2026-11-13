# Excel VBA: monthly margin pack

Three VBA modules automate the monthly reporting run on `outputs/Margin_Variance_and_Terms.xlsx`.

| Module | Macro | What it does |
|---|---|---|
| `MonthlyPack.bas` | `RunMonthlyPack` | Refresh all > full recalculation > run every reconciliation check > rebuild `Pack_Summary` with live formulas > export a dated PDF of the summary, bridge, variance and terms sheets to `reports\` > append to `Run_Log`. If any check fails, nothing is exported and the failing cells are listed. |
| | `RunMonthlyPackAndDraftEmail` | Same, then opens an Outlook draft with the PDF attached. It never sends. Late-bound, so the workbook still opens without Outlook. |
| `PriceListExport.bas` | `ExportERPPriceList` | Validates `ERP_Price_List` (codes filled, CAD only, price above zero, dates in order, no duplicate item x price group), highlights bad rows in red and refuses to export; otherwise writes the ERP upload CSV and warns on price moves over 15%. |
| `PackSetup.bas` | `AddButtons` | Adds the three buttons to the README sheet. |

**The checks.** Every column headed `Check` (Terms_Profitability, Margin_Variance), every labelled check cell (`PVM_Bridge!B13`) must be 0 within half a dollar, and no formula anywhere may return an error.

## Install

1. Open `Margin_Variance_and_Terms.xlsx`, press Alt+F11, then File > Import File for each `.bas` file.
2. Close the editor, run `PackSetup.AddButtons` once (Alt+F8).
3. Save as **Excel Macro-Enabled Workbook (.xlsm)**.

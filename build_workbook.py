"""Build outputs/Toronto_Produce_Pricing_Model.xlsx from the pipeline outputs.
Formulas stay live: change an assumption (blue cells) and the price calculator, budget, scenarios and
sensitivity all recalculate in Excel."""

import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import ColorScaleRule, CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

sys.path.insert(0, "src")
from pulse import budget as bg, market as mk  # noqa: E402
from pulse.panel import build  # noqa: E402

F = "Arial"
BLUE, GREEN, BLACK = "0000FF", "008000", "000000"
YELLOW = PatternFill("solid", fgColor="FFFF00")
HEAD = PatternFill("solid", fgColor="1F3864")
SUB = PatternFill("solid", fgColor="D9E1F2")
thin = Side(style="thin", color="BFBFBF")
BOX = Border(top=thin, bottom=thin, left=thin, right=thin)
CUR = '$#,##0.00;($#,##0.00);"-"'
CUR0 = '$#,##0;($#,##0);"-"'
PCT = '0.0%;(0.0%);"-"'


def font(color=BLACK, bold=False, size=10, italic=False):
    return Font(name=F, color=color, bold=bold, size=size, italic=italic)


def header(ws, row, labels, col=1):
    for i, lab in enumerate(labels):
        c = ws.cell(row=row, column=col + i, value=lab)
        c.font = Font(name=F, bold=True, color="FFFFFF", size=10)
        c.fill = HEAD
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = BOX


def title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = Font(name=F, bold=True, size=14, color="1F3864")
    if sub:
        ws["A2"] = sub
        ws["A2"].font = font(italic=True, color="595959")


def widths(ws, w):
    for i, x in enumerate(w, 1):
        ws.column_dimensions[get_column_letter(i)].width = x


def main(out="outputs/Toronto_Produce_Pricing_Model.xlsx"):
    basket = pd.read_csv("config/basket.csv")
    raw, rows, panel, anomalies = build(save=False)
    si_raw = mk.seasonal_index(panel, bg.SI_YEARS)
    si_shr = 1 + bg.SHRINK * (si_raw - 1)
    lvl = bg.base_levels(panel, si_shr)
    imp = bg.import_share(rows)
    items = [i for i in basket.item_id if i in lvl.index]
    b = basket.set_index("item_id")

    wb = Workbook()
    # ---------------- README
    ws = wb.active
    ws.title = "README"
    title(
        ws,
        "Toronto Produce Market Pulse - Pricing & Budget Model",
        "Real Toronto terminal-market prices (USDA AMS / Infohort AAFC), 2017-2024, in CAD",
    )
    lines = [
        (
            "What this is",
            "A pricing and budgeting model for a foodservice produce distributor, built on 7,199 item-weeks of real Toronto wholesale prices for a 30-item chef basket.",
        ),
        (
            "Sources",
            "USDA AMS Market News, Toronto Canada Terminal Market reports TO_FV010/020/030 (source: Infohort, Agriculture and Agri-Food Canada); Bank of Canada FXUSDCAD. Pulled 2026-11-13.",
        ),
        (
            "Data gap",
            "The source has no Toronto reports between April 2021 and November 2022. Nothing in this model bridges that gap.",
        ),
        (
            "Excluded weeks",
            "4 weeks where USDA's currency conversion failed (prices left in CAD or converted twice) are excluded automatically; see Data_Quality.",
        ),
        (
            "Legend",
            "Blue text = input you can change. Yellow fill = key assumption. Black = formula. Green = pulled from another sheet.",
        ),
        (
            "Assumptions",
            "Target margins, weekly case volumes and the 6% freight/handling allowance are illustrative, not company data. Change them on Assumptions.",
        ),
        (
            "How to use",
            "1) Price_Calculator: pick an item, enter today's cost, read the suggested price and action.  2) Budget: pick a scenario in Assumptions!C14.  3) Pivot_Monthly_Price: monthly average CAD price by item and year (live AVERAGEIFS on Data_Weekly); PivotTable_Price is a native Excel PivotTable when present.",
        ),
        ("Code", "Every number is reproducible: python run_pipeline.py && python build_workbook.py"),
    ]
    for i, (k, v) in enumerate(lines, start=4):
        ws.cell(row=i, column=1, value=k).font = font(bold=True)
        c = ws.cell(row=i, column=2, value=v)
        c.font = font()
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = 42
    widths(ws, [18, 110])

    # ---------------- Assumptions
    wa = wb.create_sheet("Assumptions")
    title(wa, "Assumptions", "Blue cells are inputs. Every formula in the workbook points here.")
    params = [
        (
            "Freight & handling allowance (% of terminal price)",
            0.06,
            PCT,
            "Illustrative. Covers inbound freight, cooler handling and shrink.",
        ),
        (
            "Repricing band (margin points)",
            0.05,
            PCT,
            "Reprice when margin at the current list drifts more than this from target.",
        ),
        (
            "Margin breach threshold (points below target)",
            0.10,
            PCT,
            "A week counts as a breach when margin falls this far below target.",
        ),
        (
            "Seasonal strength (shrink)",
            0.5,
            "0.00",
            "Chosen on the 2019-2020 validation window; 0 = flat, 1 = full seasonal index.",
        ),
        ("Weeks per month", 52 / 12, "0.00", "52 weeks / 12 months."),
        ("FX shock: CAD weaker vs USD", 0.05, PCT, "Applied to each item's imported share of supply."),
        (
            "Supply shock: leafy & tomato cost increase",
            0.40,
            PCT,
            "Sized from data: a 1-in-10 month runs ~38-41% above the trailing 12-month average.",
        ),
        (
            "Handling cost increase",
            0.10,
            PCT,
            "Fuel/freight inflation on the handling allowance, not passed to customers.",
        ),
        ("Volume change", -0.05, PCT, "Demand scenario."),
    ]
    header(wa, 4, ["Parameter", "Value", "Note"])
    for i, (k, v, fmt, note) in enumerate(params, start=5):
        wa.cell(row=i, column=1, value=k).font = font()
        c = wa.cell(row=i, column=2, value=v)
        c.font = font(BLUE)
        c.number_format = fmt
        c.fill = YELLOW
        wa.cell(row=i, column=3, value=note).font = font(italic=True, color="595959")
    wa["A14"] = "Active budget scenario"
    wa["A14"].font = font(bold=True)
    wa["C14"] = "Base"
    wa["C14"].font = font(BLUE, bold=True)
    wa["C14"].fill = YELLOW
    dv = DataValidation(
        type="list", formula1='"Base,CAD weaker,Leafy & tomato shock,Handling up,Volume down"', allow_blank=False
    )
    wa.add_data_validation(dv)
    dv.add("C14")
    wa["D14"] = "<- pick a scenario"
    wa["D14"].font = font(italic=True, color="595959")
    # item table
    header(
        wa,
        16,
        [
            "Item ID",
            "Item",
            "Category",
            "Target margin",
            "Weekly cases",
            "Deseasonalised cost level (CAD/case)",
            "Pack",
        ],
    )
    for r, item in enumerate(basket.item_id, start=17):
        wa.cell(row=r, column=1, value=item).font = font()
        wa.cell(row=r, column=2, value=b.loc[item, "display_name"]).font = font()
        wa.cell(row=r, column=3, value=b.loc[item, "category"]).font = font()
        c = wa.cell(row=r, column=4, value=float(b.loc[item, "target_margin"]))
        c.font = font(BLUE)
        c.number_format = PCT
        c = wa.cell(row=r, column=5, value=int(b.loc[item, "weekly_cases"]))
        c.font = font(BLUE)
        c.number_format = "#,##0"
        c = wa.cell(row=r, column=6, value=round(float(lvl[item]), 4) if item in lvl.index else None)
        c.font = font(BLUE)
        c.number_format = CUR
        wa.cell(row=r, column=7, value=b.loc[item, "unit_note"]).font = font()
    wa["F16"].comment = Comment(
        "Average of the last 8 weekly quotes up to 2024-01-30, divided by that week's half-strength seasonal index (run_pipeline.py / budget.base_levels). Spinach has no 2022-2024 quotes, so it is left out of the budget.",
        "model",
    )
    last_item_row = 16 + len(basket)
    widths(wa, [46, 22, 18, 13, 12, 20, 16])

    # ---------------- Data_Weekly (pivot source)
    wd = wb.create_sheet("Data_Weekly")
    cols = [
        "Date",
        "Year",
        "Month",
        "Item",
        "Category",
        "Price CAD/case",
        "Low CAD",
        "High CAD",
        "Quotes",
        "Lead origin",
        "Week-over-week (like-for-like)",
    ]
    p = panel.sort_values(["date", "item_id"])
    wd.append(cols)
    for _, r in p.iterrows():
        wd.append(
            [
                r.date.to_pydatetime(),
                r.date.year,
                r.date.month,
                r.display_name,
                r.category,
                round(r.price_cad, 4),
                round(r.low_cad, 4),
                round(r.high_cad, 4),
                int(r.n_quotes),
                r.lead_origin,
                (round(r.rel_cad - 1, 5) if pd.notna(r.rel_cad) else None),
            ]
        )
    n = wd.max_row
    tab = Table(displayName="WeeklyPrices", ref=f"A1:K{n}")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    wd.add_table(tab)
    for row in wd.iter_rows(min_row=2, max_row=n):
        row[0].number_format = "yyyy-mm-dd"
        for c in row[5:8]:
            c.number_format = CUR
        row[10].number_format = PCT
        for c in row:
            c.font = font()
    for c in wd[1]:
        c.font = Font(name=F, bold=True, color="FFFFFF")
    widths(wd, [11, 7, 7, 20, 16, 13, 11, 11, 8, 16, 14])
    wd.freeze_panes = "A2"

    # ---------------- Pivot_Monthly_Price (formula pivot)
    wp = wb.create_sheet("Pivot_Monthly_Price")
    title(
        wp,
        "Average CAD price per case by item and year",
        "Live AVERAGEIFS over Data_Weekly. 2021 covers Jan-Apr only; 2022 covers Nov-Dec only (source gap).",
    )
    years = [2017, 2018, 2019, 2020, 2021, 2022, 2023]
    header(wp, 4, ["Item", "Category"] + [str(y) for y in years] + ["2023 vs 2019"])
    names = basket.display_name.tolist()
    for r, (nm, cat) in enumerate(zip(names, basket.category, strict=True), start=5):
        wp.cell(row=r, column=1, value=nm).font = font()
        wp.cell(row=r, column=2, value=cat).font = font()
        for j, y in enumerate(years, start=3):
            c = wp.cell(
                row=r,
                column=j,
                value=f'=IFERROR(AVERAGEIFS(Data_Weekly!$F:$F,Data_Weekly!$D:$D,$A{r},Data_Weekly!$B:$B,{y}),"")',
            )
            c.number_format = CUR
            c.font = font(GREEN)
        c = wp.cell(row=r, column=10, value=f'=IFERROR(I{r}/E{r}-1,"")')
        c.number_format = PCT
        c.font = font()
    last = 4 + len(names)
    wp.conditional_formatting.add(
        f"J5:J{last}",
        ColorScaleRule(
            start_type="num",
            start_value=-0.3,
            start_color="2A78D6",
            mid_type="num",
            mid_value=0,
            mid_color="F0EFEC",
            end_type="num",
            end_value=0.5,
            end_color="E34948",
        ),
    )
    widths(wp, [22, 16] + [10] * 7 + [12])

    # ---------------- Seasonality
    wsn = wb.create_sheet("Seasonality")
    title(
        wsn,
        "Monthly seasonal index (1.00 = item's annual average)",
        "Estimated from 2017-2020 and 2023 complete-year data. The budget uses a half-strength version (Assumptions!B8).",
    )
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    header(wsn, 4, ["Item ID", "Item"] + months)
    for r, item in enumerate(items, start=5):
        wsn.cell(row=r, column=1, value=item).font = font()
        wsn.cell(row=r, column=2, value=b.loc[item, "display_name"]).font = font()
        for m in range(1, 13):
            c = wsn.cell(row=r, column=2 + m, value=round(float(si_raw.loc[item, m]), 4))
            c.number_format = "0.00"
            c.font = font(BLUE)
    s_last = 4 + len(items)
    wsn.conditional_formatting.add(
        f"C5:N{s_last}",
        ColorScaleRule(
            start_type="num",
            start_value=0.7,
            start_color="2A78D6",
            mid_type="num",
            mid_value=1,
            mid_color="F0EFEC",
            end_type="num",
            end_value=1.3,
            end_color="E34948",
        ),
    )
    widths(wsn, [12, 22] + [7] * 12)

    # ---------------- Price_Calculator
    wc = wb.create_sheet("Price_Calculator")
    title(wc, "Price calculator", "Pick an item and enter this week's terminal cost. Everything else is calculated.")
    labels = [
        ("Item", None),
        ("This week's terminal cost (CAD/case)", None),
        ("Current list price (CAD/case)", None),
        ("Target margin", None),
        ("Freight & handling", None),
        ("Landed cost", None),
        ("Suggested price at target", None),
        ("Margin at current list", None),
        ("Gap to target (pts)", None),
        ("Action", None),
        ("Seasonal outlook, next month vs this month", None),
    ]
    for i, (k, _) in enumerate(labels, start=4):
        wc.cell(row=i, column=1, value=k).font = font(bold=True)
    wc["B4"] = "Roma tomatoes"
    wc["B4"].font = font(BLUE, True)
    wc["B4"].fill = YELLOW
    dv2 = DataValidation(type="list", formula1=f"=Assumptions!$B$17:$B${last_item_row}")
    wc.add_data_validation(dv2)
    dv2.add("B4")
    latest = panel[panel.date == panel.date.max()].set_index("display_name").price_cad
    wc["B5"] = round(float(latest.get("Roma tomatoes", 40)), 2)
    wc["B5"].font = font(BLUE)
    wc["B5"].number_format = CUR
    wc["B5"].fill = YELLOW
    wc["C5"] = "Toronto terminal, week of 2024-01-30 (example)"
    wc["C5"].font = font(italic=True, color="595959")
    wc["B6"] = 62.89
    wc["B6"].font = font(BLUE)
    wc["B6"].number_format = CUR
    wc["B6"].fill = YELLOW
    wc["C6"] = "Example: list built on the prior 4-week average cost"
    wc["C6"].font = font(italic=True, color="595959")
    rng = f"Assumptions!$B$17:$B${last_item_row}"
    wc["B7"] = f"=INDEX(Assumptions!$D$17:$D${last_item_row},MATCH(B4,{rng},0))"
    wc["B7"].number_format = PCT
    wc["B7"].font = font(GREEN)
    wc["B8"] = "=Assumptions!$B$5"
    wc["B8"].number_format = PCT
    wc["B8"].font = font(GREEN)
    wc["B9"] = "=B5*(1+B8)"
    wc["B9"].number_format = CUR
    wc["B10"] = "=B9/(1-B7)"
    wc["B10"].number_format = CUR
    wc["B10"].font = font(bold=True)
    wc["B11"] = "=IF(B6>0,1-B9/B6,0)"
    wc["B11"].number_format = PCT
    wc["B12"] = "=B11-B7"
    wc["B12"].number_format = "+0.0%;-0.0%;0.0%"
    wc["B13"] = '=IF(B12<-Assumptions!$B$6,"Raise price",IF(B12>Assumptions!$B$6,"Lower price / promote","Hold"))'
    wc["B13"].font = font(bold=True)
    wc["C11"] = "=B6-B9"
    wc["C11"].number_format = CUR
    wc["D11"] = "<- gross margin per case at current list"
    wc["D11"].font = font(italic=True, color="595959")
    wc["B14"] = (
        "=IFERROR(INDEX(Seasonality!$C$5:$N$"
        + str(s_last)
        + ",MATCH(B4,Seasonality!$B$5:$B$"
        + str(s_last)
        + ",0),MOD(MONTH(TODAY()),12)+1)/INDEX(Seasonality!$C$5:$N$"
        + str(s_last)
        + ",MATCH(B4,Seasonality!$B$5:$B$"
        + str(s_last)
        + ',0),MONTH(TODAY()))-1,"n/a")'
    )
    wc["B14"].number_format = "+0.0%;-0.0%;0.0%"
    wc.conditional_formatting.add(
        "B13", CellIsRule(operator="equal", formula=['"Raise price"'], font=Font(name=F, color="D03B3B", bold=True))
    )
    widths(wc, [42, 18, 46, 40])

    # ---------------- Budget
    wbud = wb.create_sheet("Budget")
    title(
        wbud,
        "FY budget Feb 2024 - Jan 2025 (CAD)",
        "Cost = deseasonalised level x half-strength seasonal index x (1 + handling). Each scenario has its own gross-margin column.",
    )
    bcols = [
        "Item",
        "Category",
        "Month",
        "Month #",
        "Seasonal index",
        "Import share",
        "Cases",
        "Landed cost / case",
        "Sell price / case",
        "Revenue",
        "COGS",
        "GM - Base",
        "GM - CAD weaker",
        "GM - Leafy & tomato shock",
        "GM - Handling up",
        "GM - Volume down",
        "GM - Active scenario",
    ]
    header(wbud, 4, bcols)
    months_p = pd.period_range("2024-02", "2025-01", freq="M")
    r = 5
    for item in items:
        arow = 17 + list(basket.item_id).index(item)
        for m in months_p:
            mi = m.month
            srow = 5 + items.index(item)
            wbud.cell(row=r, column=1, value=b.loc[item, "display_name"]).font = font()
            wbud.cell(row=r, column=2, value=b.loc[item, "category"]).font = font()
            wbud.cell(row=r, column=3, value=str(m)).font = font()
            wbud.cell(row=r, column=4, value=mi).font = font()
            sl = get_column_letter(2 + mi)
            c = wbud.cell(row=r, column=5, value=f"=1+Assumptions!$B$8*(Seasonality!{sl}{srow}-1)")
            c.number_format = "0.000"
            c.font = font(GREEN)
            c = wbud.cell(row=r, column=6, value=round(float(imp.loc[item, mi]), 4) if item in imp.index else 0)
            c.number_format = PCT
            c.font = font(BLUE)
            c = wbud.cell(row=r, column=7, value=f"=Assumptions!$E${arow}*Assumptions!$B$9")
            c.number_format = "#,##0.0"
            c.font = font(GREEN)
            c = wbud.cell(row=r, column=8, value=f"=Assumptions!$F${arow}*E{r}*(1+Assumptions!$B$5)")
            c.number_format = CUR
            c = wbud.cell(row=r, column=9, value=f"=H{r}/(1-Assumptions!$D${arow})")
            c.number_format = CUR
            c = wbud.cell(row=r, column=10, value=f"=I{r}*G{r}")
            c.number_format = CUR0
            c = wbud.cell(row=r, column=11, value=f"=H{r}*G{r}")
            c.number_format = CUR0
            c = wbud.cell(row=r, column=12, value=f"=J{r}-K{r}")
            c.number_format = CUR0
            # CAD weaker: cost up on imported share from Feb; price catches up from Mar
            c = wbud.cell(
                row=r,
                column=13,
                value=f'=(I{r}*IF(C{r}="2024-02",1,1+Assumptions!$B$10*F{r})-H{r}*(1+Assumptions!$B$10*F{r}))*G{r}',
            )
            c.number_format = CUR0
            # leafy/tomato shock Mar-Apr; March price lags
            c = wbud.cell(
                row=r,
                column=14,
                value=(
                    f'=IF(AND(OR(B{r}="Leafy & lettuce",B{r}="Tomatoes"),OR(C{r}="2024-03",C{r}="2024-04")),'
                    f'(I{r}*IF(C{r}="2024-03",1,1+Assumptions!$B$11)-H{r}*(1+Assumptions!$B$11))*G{r},L{r})'
                ),
            )
            c.number_format = CUR0
            c = wbud.cell(
                row=r, column=15, value=f"=L{r}-H{r}/(1+Assumptions!$B$5)*Assumptions!$B$5*Assumptions!$B$12*G{r}"
            )
            c.number_format = CUR0
            c = wbud.cell(row=r, column=16, value=f"=L{r}*(1+Assumptions!$B$13)")
            c.number_format = CUR0
            c = wbud.cell(
                row=r,
                column=17,
                value=(
                    f'=INDEX(L{r}:P{r},MATCH(Assumptions!$C$14,{{"Base","CAD weaker","Leafy & tomato shock","Handling up","Volume down"}},0))'
                ),
            )
            c.number_format = CUR0
            c.font = font(bold=True)
            for cc in range(1, 18):
                if wbud.cell(row=r, column=cc).font.name != F:
                    wbud.cell(row=r, column=cc).font = font()
            r += 1
    blast = r - 1
    wbud.cell(row=r, column=1, value="TOTAL").font = font(bold=True)
    for col in range(10, 18):
        L = get_column_letter(col)
        c = wbud.cell(row=r, column=col, value=f"=SUM({L}5:{L}{blast})")
        c.number_format = CUR0
        c.font = font(bold=True)
    tot_row = r
    wbud.freeze_panes = "D5"
    widths(wbud, [20, 15, 9, 8, 9, 9, 8, 11, 11, 12, 12, 12, 12, 14, 12, 12, 13])

    # ---------------- Scenarios & sensitivity
    wsc = wb.create_sheet("Scenarios")
    title(
        wsc,
        "Scenario summary and sensitivity (annual gross margin, CAD)",
        "All values are live formulas on the Budget sheet.",
    )
    header(wsc, 4, ["Scenario", "Gross margin", "vs Base", "vs Base %", "What it assumes"])
    sc = [
        ("Base", "L", "Seasonal cost path, target margins, assumed volumes."),
        ("CAD weaker", "M", "Imported share of each item costs more from Feb; prices catch up from Mar."),
        (
            "Leafy & tomato shock",
            "N",
            "1-in-10 cost spike on leafy and tomatoes in Mar-Apr; March priced off February cost.",
        ),
        ("Handling up", "O", "Freight/handling allowance up 10%, absorbed."),
        ("Volume down", "P", "Fewer cases at the same margin."),
    ]
    for i, (nm, col, note) in enumerate(sc, start=5):
        wsc.cell(row=i, column=1, value=nm).font = font()
        c = wsc.cell(row=i, column=2, value=f"=Budget!{col}{tot_row}")
        c.number_format = CUR0
        c.font = font(GREEN)
        c = wsc.cell(row=i, column=3, value=f"=B{i}-$B$5")
        c.number_format = CUR0
        c = wsc.cell(row=i, column=4, value=f"=IF($B$5=0,0,B{i}/$B$5-1)")
        c.number_format = PCT
        wsc.cell(row=i, column=5, value=note).font = font(italic=True, color="595959")
    wsc["A11"] = "Base revenue"
    wsc["B11"] = f"=Budget!J{tot_row}"
    wsc["B11"].number_format = CUR0
    wsc["B11"].font = font(GREEN)
    wsc["A12"] = "Base COGS"
    wsc["B12"] = f"=Budget!K{tot_row}"
    wsc["B12"].number_format = CUR0
    wsc["B12"].font = font(GREEN)
    wsc["A13"] = "Base gross margin %"
    wsc["B13"] = "=IF(B11=0,0,B5/B11)"
    wsc["B13"].number_format = PCT
    header(wsc, 15, ["Sensitivity driver (one at a time)", "Upside", "Downside", "Swing"])
    sens = [
        ("Volume +/-10%", "=B5*0.1"),
        ("Produce cost +/-10%, passed through at target margin", "=B5*0.1"),
        ("Achieved margin +/-2 pts", "=B11*0.02"),
        ("Handling allowance +/-1 pt, absorbed", "=B12/(1+Assumptions!B5)*0.01"),
        ("Produce cost +/-10%, held one month", "=B12*0.1/12"),
    ]
    for i, (nm, f) in enumerate(sens, start=16):
        wsc.cell(row=i, column=1, value=nm).font = font()
        c = wsc.cell(row=i, column=2, value=f)
        c.number_format = CUR0
        c = wsc.cell(row=i, column=3, value=f"=-B{i}")
        c.number_format = CUR0
        c = wsc.cell(row=i, column=4, value=f"=B{i}-C{i}")
        c.number_format = CUR0
    widths(wsc, [52, 15, 13, 11, 80])

    # ---------------- Policy backtest + market update + data quality (values from the pipeline)
    for name, path, note in [
        (
            "Policy_Backtest",
            "outputs/pricing_policy_backtest.csv",
            "Values from run_pipeline.py: three pricing policies replayed on real weekly costs, 2017-2021 and 2022-2024.",
        ),
        (
            "Cadence_Recommendation",
            "outputs/pricing_cadence_recommendation.csv",
            "Calmest policy that keeps margin breaches under 10% of weeks; otherwise weekly.",
        ),
        (
            "Market_Update_2024-01-30",
            "outputs/market_update_2024-01-30.csv",
            "Latest week in the source. List price assumed to be built on the prior 4-week average cost.",
        ),
        (
            "Data_Quality",
            "data/processed/dq_excluded_weeks.csv",
            "Weeks excluded because USDA's currency conversion failed. Ratio = basket price vs neighbouring weeks.",
        ),
    ]:
        w = wb.create_sheet(name)
        df = pd.read_csv(path)
        title(w, name.replace("_", " "), note)
        header(w, 4, list(df.columns))
        for i, rr in enumerate(df.itertuples(index=False), start=5):
            for j, v in enumerate(rr, start=1):
                c = w.cell(
                    row=i, column=j, value=(None if pd.isna(v) else (round(v, 4) if isinstance(v, float) else v))
                )
                c.font = font()
                col = df.columns[j - 1]
                if any(k in col for k in ["margin", "rate", "wow", "vs_4wk", "outlook", "share"]):
                    c.number_format = PCT
                elif any(k in col for k in ["price", "cost", "gm_"]):
                    c.number_format = CUR
        for j in range(1, len(df.columns) + 1):
            w.column_dimensions[get_column_letter(j)].width = 16

    for w in wb.worksheets:
        w.sheet_view.showGridLines = w.title in ("Data_Weekly",)
    Path(out).parent.mkdir(exist_ok=True)
    wb.save(out)
    print("saved", out, "budget rows", blast - 4, "total row", tot_row)


if __name__ == "__main__":
    main()

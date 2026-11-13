"""Build outputs/Margin_Variance_and_Terms.xlsx: customer pricing terms, margin-variance bridge, contract escalator
and ERP price-list upload. Values come from run_pipeline.py; ratios, variances and checks are live formulas."""

import json
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.legend import LegendEntry
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

from build_workbook import BLUE, CUR, CUR0, PCT, YELLOW, font, header, title, widths


def main(out="outputs/Margin_Variance_and_Terms.xlsx"):
    tf = json.loads(Path("outputs/terms_facts.json").read_text(encoding="utf-8"))
    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    title(
        ws,
        "Margin variance and customer pricing terms",
        "Real Toronto terminal costs 2017-2024 (USDA AMS / Infohort AAFC), CAD",
    )
    lines = [
        (
            "What this is",
            "Four customer types buy the 30-item basket on different pricing terms: weekly market sheet, band rule, or fixed monthly contract list. Prices are replayed on real weekly costs.",
        ),
        (
            "Variance bridge",
            "Gross margin minus margin at target = cost timing (quotes go out on last week's cost) + price hold (cost of keeping a list or band price). The Check columns must be 0.",
        ),
        (
            "Assumptions",
            "Customer volume shares, margin offsets and terms (config/customer_terms.csv), target margins and the 6% freight/handling allowance are illustrative, not company data.",
        ),
        (
            "Not the pricing desk",
            "These customer types are separate from the synthetic customers in Pricing_Decision_Workbook.xlsx and the app's Customer & pricing desk.",
        ),
        (
            "Price-volume-mix",
            "PVM_Inputs and PVM_Bridge split gross-margin change 2019 to 2023 into volume, mix, list price, discounts and promotions, and cost (live formulas). Promo_Breakeven is a calculator. Cases and promotions there are SYNTHETIC; costs are real.",
        ),
        (
            "Legend",
            "Black = formula. Values pasted from the pipeline are plain text. Rebuild: python run_pipeline.py && python build_terms_workbook.py",
        ),
    ]
    for i, (k, v) in enumerate(lines, start=4):
        ws.cell(row=i, column=1, value=k).font = font(bold=True)
        c = ws.cell(row=i, column=2, value=v)
        c.font = font()
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = 32
    widths(ws, [20, 110])

    # ---------------- Customer segments and margin variance (values from run_pipeline.py, math live)
    seg = pd.read_csv("outputs/terms_profitability.csv")
    ws2 = wb.create_sheet("Terms_Profitability")
    title(
        ws2,
        "Profitability by customer pricing terms, 2017-2024 (replayed on real weekly costs)",
        "Segment terms and volume shares are assumptions (config/customer_terms.csv). Variance = cost timing + price hold; Check must be 0.",
    )
    cols = [
        "Segment",
        "Pricing terms",
        "Revenue",
        "Gross margin",
        "GM at target",
        "GM %",
        "Target %",
        "Gap (pts)",
        "Variance $",
        "Cost timing $",
        "Price hold $",
        "Check",
        "Breach weeks",
        "Monthly swing (sd, pts)",
    ]
    header(ws2, 4, cols)
    r0 = 5
    for i, rr in enumerate(seg.itertuples(), start=r0):
        vals = [rr.segment, rr.pricing_policy, rr.revenue, rr.gm, rr.gm_target]
        for j, v in enumerate(vals, start=1):
            ws2.cell(row=i, column=j, value=round(v, 2) if isinstance(v, float) else v).font = font()
        ws2.cell(row=i, column=6, value=f"=D{i}/C{i}")
        ws2.cell(row=i, column=7, value=f"=E{i}/C{i}")
        ws2.cell(row=i, column=8, value=f"=(F{i}-G{i})*100")
        ws2.cell(row=i, column=9, value=f"=D{i}-E{i}")
        ws2.cell(row=i, column=10, value=round(rr.var_cost_timing, 2)).font = font()
        ws2.cell(row=i, column=11, value=round(rr.var_price_hold, 2)).font = font()
        ws2.cell(row=i, column=12, value=f"=ROUND(I{i}-J{i}-K{i},0)")
        ws2.cell(row=i, column=13, value=round(rr.breach_rate, 4)).font = font()
        ws2.cell(row=i, column=14, value=round(rr.sd, 2)).font = font()
    rl = r0 + len(seg) - 1
    tr = rl + 1
    ws2.cell(row=tr, column=1, value="Total").font = font(bold=True)
    for col in "CDEIJKL":
        ws2[f"{col}{tr}"] = f"=SUM({col}{r0}:{col}{rl})"
        ws2[f"{col}{tr}"].font = font(bold=True)
    ws2[f"F{tr}"] = f"=D{tr}/C{tr}"
    ws2[f"G{tr}"] = f"=E{tr}/C{tr}"
    ws2[f"H{tr}"] = f"=(F{tr}-G{tr})*100"
    for i in range(r0, tr + 1):
        for col, fmt in zip(
            "CDEFGHIJKLMN", [CUR0, CUR0, CUR0, PCT, PCT, "0.00", CUR0, CUR0, CUR0, "0", PCT, "0.0"], strict=True
        ):
            ws2[f"{col}{i}"].number_format = fmt
    ws2.conditional_formatting.add(
        f"M{r0}:M{rl}", ColorScaleRule(start_type="min", start_color="FFFFFF", end_type="max", end_color="F4B183")
    )
    n = tr + 2
    ws2.cell(row=n, column=1, value="Reading it").font = font(bold=True)
    ws2.cell(
        row=n + 1,
        column=1,
        value=f"All four customer types land on target over seven years; the difference is risk. The fixed monthly contract list "
        f"spends {seg.set_index('segment_id').loc['contract', 'breach_rate']:.0%} of item-weeks more than 10 points under target; "
        f"a band-rule escalator clause cuts that to {tf['contract_band_breach_rate']:.0%} (see Contract_Escalator).",
    ).font = font()
    widths(ws2, [28, 13, 13, 13, 13, 9, 9, 9, 12, 12, 12, 8, 11, 12])

    wv = wb.create_sheet("Margin_Variance")
    mv = pd.read_csv("outputs/margin_variance_by_month.csv")
    title(
        wv,
        "Gross margin against target by month - variance bridge",
        "Cost timing = quotes go out on last week's cost. Price hold = cost of holding a list or band price. Variance = GM - GM at target.",
    )
    header(
        wv,
        4,
        [
            "Month",
            "Revenue",
            "Gross margin",
            "GM at target",
            "Variance $",
            "Cost timing $",
            "Price hold $",
            "Check",
            "GM %",
            "Gap (pts)",
        ],
    )
    for i, rr in enumerate(mv.itertuples(), start=5):
        wv.cell(row=i, column=1, value=rr.month).font = font()
        for j, v in zip(
            [2, 3, 4, 6, 7], [rr.revenue, rr.gm, rr.gm_target, rr.var_cost_timing, rr.var_price_hold], strict=True
        ):
            wv.cell(row=i, column=j, value=round(v, 2)).font = font()
        wv.cell(row=i, column=5, value=f"=C{i}-D{i}")
        wv.cell(row=i, column=8, value=f"=ROUND(E{i}-F{i}-G{i},0)")
        wv.cell(row=i, column=9, value=f"=C{i}/B{i}")
        wv.cell(row=i, column=10, value=f"=(C{i}-D{i})/B{i}*100")
        for col, fmt in zip("BCDEFGHIJ", [CUR0] * 6 + ["0", PCT, "0.00"], strict=True):
            wv[f"{col}{i}"].number_format = fmt
    ml = 4 + len(mv)
    t = ml + 1
    wv.cell(row=t, column=1, value="Total").font = font(bold=True)
    for col in "BCDEFGH":
        wv[f"{col}{t}"] = f"=SUM({col}5:{col}{ml})"
        wv[f"{col}{t}"].font = font(bold=True)
        wv[f"{col}{t}"].number_format = CUR0 if col != "H" else "0"
    wv[f"J{t}"] = f"=(C{t}-D{t})/B{t}*100"
    wv[f"J{t}"].number_format = "0.00"
    wv.conditional_formatting.add(
        f"J5:J{ml}",
        ColorScaleRule(
            start_type="num",
            start_value=-10,
            start_color="E34948",
            mid_type="num",
            mid_value=0,
            mid_color="FFFFFF",
            end_type="num",
            end_value=10,
            end_color="2A78D6",
        ),
    )
    wv.freeze_panes = "B5"
    widths(wv, [10, 13, 13, 13, 12, 13, 13, 8, 9, 10])

    pl = pd.read_csv(f"outputs/erp_price_list_upload_{tf['price_list_week']}.csv")
    we = wb.create_sheet("ERP_Price_List")
    title(
        we,
        f"Price-list upload, week of {tf['price_list_week']} (one row per item x customer price group)",
        "Format for a bulk price import into an ERP. Change % and Margin at price are live formulas.",
    )
    pcols = list(pl.columns)
    header(we, 4, pcols + ["margin_at_price"])
    for i, rr in enumerate(pl.itertuples(index=False), start=5):
        for j, v in enumerate(rr, start=1):
            we.cell(row=i, column=j, value=v).font = font()
        ci = {c: get_column_letter(k + 1) for k, c in enumerate(pcols)}
        we[f"{ci['change_pct']}{i}"] = f"={ci['unit_price']}{i}/{ci['prior_price']}{i}-1"
        last = get_column_letter(len(pcols) + 1)
        we[f"{last}{i}"] = f"=1-{ci['landed_cost']}{i}/{ci['unit_price']}{i}"
        for c, fmt in [
            ("unit_price", CUR),
            ("prior_price", CUR),
            ("landed_cost", CUR),
            ("change_pct", PCT),
            ("target_margin", PCT),
        ]:
            we[f"{ci[c]}{i}"].number_format = fmt
        we[f"{last}{i}"].number_format = PCT
    we.freeze_panes = "C5"
    widths(we, [13, 22, 14, 13, 26, 8, 11, 11, 10, 12, 12, 10, 11, 11, 12])

    w = wb.create_sheet("Contract_Escalator")
    df = pd.read_csv("outputs/contract_escalator_whatif.csv")
    title(
        w,
        "Institutional contracts: fixed monthly list vs a band-rule escalator clause",
        "Clause reprices when margin drifts 5 points from target. GM change is over the full history.",
    )
    cols = [
        "Category",
        "GM %, monthly list",
        "GM %, band clause",
        "Breach weeks, monthly",
        "Breach weeks, band",
        "GM change $",
        "Breach change (pts)",
    ]
    header(w, 4, cols)
    for i, rr in enumerate(df.itertuples(index=False), start=5):
        for j, v in enumerate(rr, start=1):
            w.cell(row=i, column=j, value=round(v, 4) if isinstance(v, float) else v).font = font()
        w.cell(row=i, column=7, value=f"=(E{i}-D{i})*100")
        for col, fmt in zip("BCDEFG", [PCT, PCT, PCT, PCT, CUR0, "0.0"], strict=True):
            w[f"{col}{i}"].number_format = fmt
    widths(w, [18, 16, 16, 18, 16, 13, 16])

    rgm_sheets(wb)
    for sh in wb.worksheets:
        sh.sheet_view.showGridLines = False
    Path(out).parent.mkdir(exist_ok=True)
    wb.save(out)
    print("saved", out)


def rgm_sheets(wb):
    """Price-volume-mix bridge (item inputs, live effect formulas, waterfall) and a promotion break-even calculator."""
    d = pd.read_csv("outputs/rgm/pvm_by_item.csv")
    names = pd.read_csv("config/basket.csv").set_index("item_id").display_name
    wi = wb.create_sheet("PVM_Inputs")
    title(
        wi,
        "Price-volume-mix inputs by item, 2019 (A) vs 2023 (B)",
        "Blue = values from the pipeline (real terminal costs; SYNTHETIC cases and promotions). Black = formulas. Prices are per case.",
    )
    cols = [
        "Item",
        "Category",
        "Cases A",
        "Cases B",
        "List A",
        "List B",
        "Net A",
        "Net B",
        "Cost A",
        "Cost B",
        "Margin/case A",
        "Share A",
        "Share B",
        "GM A",
        "GM B",
        "Volume",
        "Mix",
        "List price",
        "Discounts & promos",
        "Cost",
    ]
    header(wi, 4, cols)
    r0 = 5
    r1 = r0 + len(d) - 1
    tot = r1 + 1
    for i, rr in enumerate(d.itertuples(index=False), start=r0):
        wi.cell(row=i, column=1, value=names.get(rr.item_id, rr.item_id)).font = font()
        wi.cell(row=i, column=2, value=rr.category).font = font()
        for j, v in enumerate(
            [rr.cases_a, rr.cases_b, rr.list_a, rr.list_b, rr.net_a, rr.net_b, rr.cost_a, rr.cost_b], start=3
        ):
            wi.cell(row=i, column=j, value=round(float(v), 4)).font = font(color=BLUE)
        f = {
            11: f"=G{i}-I{i}",
            12: f"=C{i}/$C${tot}",
            13: f"=D{i}/$D${tot}",
            14: f"=C{i}*K{i}",
            15: f"=D{i}*(H{i}-J{i})",
            16: f"=($D${tot}-$C${tot})*L{i}*$N${tot}/$C${tot}",
            17: f"=$D${tot}*(M{i}-L{i})*K{i}",
            18: f"=D{i}*(F{i}-E{i})",
            19: f"=D{i}*((H{i}-F{i})-(G{i}-E{i}))",
            20: f"=-D{i}*(J{i}-I{i})",
        }
        for c, v in f.items():
            wi.cell(row=i, column=c, value=v)
        for col, fmt in zip("CDEFGHIJKLMNOPQRST", ["#,##0"] * 2 + [CUR] * 7 + [PCT] * 2 + [CUR0] * 7, strict=True):
            wi[f"{col}{i}"].number_format = fmt
    wi.cell(row=tot, column=1, value="Total").font = font(bold=True)
    for col in "CDLMNOPQRST":
        wi[f"{col}{tot}"] = f"=SUM({col}{r0}:{col}{r1})"
        wi[f"{col}{tot}"].font = font(bold=True)
        wi[f"{col}{tot}"].number_format = "#,##0" if col in "CD" else PCT if col in "LM" else CUR0
    wi.freeze_panes = "C5"
    widths(wi, [24, 15] + [10] * 18)

    wbr = wb.create_sheet("PVM_Bridge")
    title(
        wbr,
        "Gross margin bridge, 2023 vs 2019",
        "Each effect sums its column on PVM_Inputs. Check must be 0. Volumes and promotions are synthetic; costs are real.",
    )
    header(wbr, 4, ["Driver", "CAD", "Chart base", "Increase", "Decrease", "Total"])
    rows = [
        ("Gross margin 2019", f"=PVM_Inputs!N{tot}"),
        ("Volume", f"=PVM_Inputs!P{tot}"),
        ("Mix", f"=PVM_Inputs!Q{tot}"),
        ("List price", f"=PVM_Inputs!R{tot}"),
        ("Discounts & promotions", f"=PVM_Inputs!S{tot}"),
        ("Cost", f"=PVM_Inputs!T{tot}"),
        ("Gross margin 2023", f"=PVM_Inputs!O{tot}"),
    ]
    for i, (k, v) in enumerate(rows, start=5):
        wbr.cell(row=i, column=1, value=k).font = font(bold=k.startswith("Gross"))
        wbr.cell(row=i, column=2, value=v)
        if k.startswith("Gross"):
            wbr.cell(row=i, column=3, value=0)
            wbr.cell(row=i, column=4, value=0)
            wbr.cell(row=i, column=5, value=0)
            wbr.cell(row=i, column=6, value=f"=B{i}")
        else:
            # running total before this effect = B5 + sum of earlier effects
            prior = f"SUM($B$5:B{i - 1})"
            wbr.cell(row=i, column=3, value=f"=IF(B{i}>=0,{prior},{prior}+B{i})")
            wbr.cell(row=i, column=4, value=f"=MAX(B{i},0)")
            wbr.cell(row=i, column=5, value=f"=MAX(-B{i},0)")
            wbr.cell(row=i, column=6, value=0)
        for col in "BCDEF":
            wbr[f"{col}{i}"].number_format = CUR0
    wbr["A13"] = "Check (GM 2023 - GM 2019 - effects)"
    wbr["A13"].font = font(bold=True)
    wbr["B13"] = "=ROUND(B11-B5-SUM(B6:B10),2)"
    wbr["B13"].number_format = "0.00"
    ch = BarChart()
    ch.type = "col"
    ch.grouping = "stacked"
    ch.overlap = 100
    ch.title = "Gross margin bridge, 2023 vs 2019 (CAD)"
    data = Reference(wbr, min_col=3, max_col=6, min_row=4, max_row=11)
    ch.add_data(data, titles_from_data=True)
    ch.set_categories(Reference(wbr, min_col=1, min_row=5, max_row=11))
    ch.series[0].graphicalProperties.noFill = True
    ch.series[0].graphicalProperties.line.noFill = True
    for srs, color in zip(ch.series[1:], ["1BAF7A", "E34948", "52514E"], strict=True):
        srs.graphicalProperties.solidFill = color
        srs.graphicalProperties.line.solidFill = color
    ch.legend.position = "b"
    ch.legend.overlay = False
    ch.legend.legendEntry = [LegendEntry(idx=0, delete=True)]
    ch.title.overlay = False
    ch.roundedCorners = False
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    ch.y_axis.numFmt = "$#,##0"
    ch.y_axis.majorGridlines = None
    ch.width, ch.height = 22, 9
    wbr.add_chart(ch, "H4")
    widths(wbr, [36, 14, 12, 12, 12, 12])

    wc = wb.create_sheet("Promo_Breakeven")
    title(
        wc,
        "Promotion break-even calculator",
        "Yellow cells are inputs. Lift = how many times baseline volume the promotion must sell to earn the same margin.",
    )
    inputs = [
        ("Regular gross margin (% of net price)", 0.25, PCT),
        ("Promotion price cut", 0.10, PCT),
        ("Fixed event cost (CAD)", 150, CUR0),
        ("Baseline revenue over the promotion weeks (CAD)", 4000, CUR0),
    ]
    for i, (k, v, fmt) in enumerate(inputs, start=4):
        wc.cell(row=i, column=1, value=k).font = font()
        c = wc.cell(row=i, column=2, value=v)
        c.font = font(color=BLUE)
        c.fill = YELLOW
        c.number_format = fmt
    wc["A9"] = "Margin per promoted case (% of regular price)"
    wc["B9"] = "=B4-B5"
    wc["B9"].number_format = PCT
    wc["A10"] = "Volume lift needed to break even (x baseline)"
    wc["A10"].font = font(bold=True)
    wc["B10"] = '=IF(B9<=0,"No lift breaks even",(B4*B7+B6)/(B9*B7))'
    wc["B10"].number_format = '0.00"x"'
    wc["B10"].font = font(bold=True)
    wc["A11"] = "Extra volume needed"
    wc["B11"] = '=IF(ISNUMBER(B10),B10-1,"-")'
    wc["B11"].number_format = PCT
    wc["A13"] = "Break-even lift by margin (rows) and price cut (columns), no fixed cost"
    wc["A13"].font = font(bold=True)
    cuts = [0.05, 0.10, 0.15, 0.20, 0.25]
    margins = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    wc.cell(row=14, column=1, value="Margin (rows) vs price cut").font = font(bold=True)
    for j, cpct in enumerate(cuts, start=2):
        c = wc.cell(row=14, column=j, value=cpct)
        c.number_format = "0%"
        c.font = font(color=BLUE, bold=True)
    for i, mpct in enumerate(margins, start=15):
        c = wc.cell(row=i, column=1, value=mpct)
        c.number_format = "0%"
        c.font = font(color=BLUE, bold=True)
        for j in range(2, 2 + len(cuts)):
            col = get_column_letter(j)
            wc.cell(
                row=i, column=j, value=f'=IF($A{i}<={col}$14,"n/a",$A{i}/($A{i}-{col}$14))'
            ).number_format = '0.00"x"'
    wc.conditional_formatting.add(
        f"B15:{get_column_letter(1 + len(cuts))}{14 + len(margins)}",
        ColorScaleRule(
            start_type="num", start_value=1, start_color="FFFFFF", end_type="num", end_value=4, end_color="F4B183"
        ),
    )
    wc["A22"] = (
        "Reading it: a 10% cut on a 25% margin needs 1.67x volume before any fixed cost. In the synthetic events, "
        "counting the fee and the post-promotion dip, the median promotion needed about 2.5x."
    )
    widths(wc, [48, 14, 12, 12, 12, 12])


if __name__ == "__main__":
    main()

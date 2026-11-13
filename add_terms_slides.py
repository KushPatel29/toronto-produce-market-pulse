"""Insert two slides (customer pricing terms, margin variance by cause) into the stakeholder briefing.

Starts from the five-slide editable snapshot in assets/ and writes the seven-slide deck to outputs/, reusing the
deck's own text boxes and table styling and renumbering the page labels. Safe to re-run.
"""

import copy
import json
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_TICK_LABEL_POSITION
from pptx.util import Emu, Pt

BASE = Path("assets/briefing_base_5_slides.pptx")
DECK = Path("outputs/Produce_Pricing_Decision_Brief.pptx")
NAVY, GREEN, GREY, INK = (
    RGBColor(0x14, 0x2D, 0x41),
    RGBColor(0x24, 0x7D, 0x5B),
    RGBColor(0x61, 0x71, 0x7B),
    RGBColor(0x23, 0x37, 0x44),
)
INSERT_AT = 3  # after "Temporary supply shocks and price lag"
ROW_H = 430000  # table row height (EMU) for the five-row terms table


def _shape(slide, name):
    return next(s for s in slide.shapes if s.name == name)


def _clone_text(src, dst_slide, new_name, text):
    el = copy.deepcopy(src._element)
    dst_slide.shapes._spTree.append(el)
    sh = dst_slide.shapes[-1]
    sh.name = new_name
    paras = sh.text_frame.paragraphs
    run = paras[0].runs[0]
    for p in paras[1:]:
        p._p.getparent().remove(p._p)
    for r in paras[0].runs[1:]:
        r._r.getparent().remove(r._r)
    run.text = text
    return sh


def _clone_table(src, dst_slide, rows, widths, top=None):
    el = copy.deepcopy(src._element)
    dst_slide.shapes._spTree.append(el)
    sh = dst_slide.shapes[-1]
    sh.name = "terms-table"
    tbl = sh._element.graphic.graphicData.tbl
    grid = tbl.tblGrid
    head_tr, body_tr = tbl.tr_lst[0], tbl.tr_lst[1]
    head_tc, body_tc = head_tr.tc_lst[1], body_tr.tc_lst[1]
    for gc in list(grid):
        grid.remove(gc)
    for tr in list(tbl.tr_lst):
        tbl.remove(tr)
    for w in widths:
        gc = copy.deepcopy(src._element.graphic.graphicData.tbl.tblGrid[0])
        gc.set("w", str(w))
        grid.append(gc)
    for i, row in enumerate(rows):
        tr = copy.deepcopy(head_tr if i == 0 else body_tr)
        for tc in list(tr.tc_lst):
            tr.remove(tc)
        for v in row:
            tc = copy.deepcopy(head_tc if i == 0 else body_tc)
            r = tc.txBody.p_lst[0].r_lst[0]
            for extra in tc.txBody.p_lst[0].r_lst[1:]:
                tc.txBody.p_lst[0].remove(extra)
            r.t.text = str(v)
            tr.append(tc)
        tbl.append(tr)
    for tr in tbl.tr_lst:
        tr.set("h", str(ROW_H))
        for rpr in tr.xpath(".//a:rPr"):
            rpr.set("sz", "1400")
    sh.width = Emu(sum(widths))
    sh.height = Emu(ROW_H * len(rows))
    if top is not None:
        sh.top = Emu(top)
    return sh


def main():
    f = json.loads(Path("outputs/terms_facts.json").read_text(encoding="utf-8"))
    pnl = pd.read_csv("outputs/terms_profitability.csv").set_index("segment_id")
    yv = pd.read_csv("outputs/margin_variance_by_year.csv")
    prs = Presentation(BASE)
    sld_ids = prs.slides._sldIdLst
    ref, ref_lag = prs.slides[1], prs.slides[2]
    layout = ref.slide_layout

    # ---- slide A: customer terms
    a = prs.slides.add_slide(layout)
    for ph in list(a.placeholders):
        ph._element.getparent().remove(ph._element)
    _clone_text(_shape(ref, "title"), a, "terms-title", "Fixed contract prices carry the margin risk")
    _clone_text(_shape(ref, "page"), a, "terms-page", "")
    _clone_text(
        _shape(ref, "context"),
        a,
        "terms-context",
        "Real Toronto costs 2017–2024 · four customer types, each on its own pricing terms · CAD per case",
    )
    names = {
        "fine_dining": "Independent & fine dining",
        "casual": "Casual & chain restaurants",
        "hotels": "Hotels & catering",
        "contract": "Institutional contracts",
    }
    terms = {"weekly": "Weekly sheet", "band": "Band rule", "monthly": "Fixed monthly list"}
    rows = [["Customer type", "Pricing terms", "GM vs target", "Breach weeks", "Monthly swing"]]
    for sid in ["fine_dining", "casual", "hotels", "contract"]:
        r = pnl.loc[sid]
        rows.append(
            [names[sid], terms[r.pricing_policy], f"{r.gap_pts:+.1f} pts", f"{r.breach_rate:.1%}", f"{r.sd:.1f} pts"]
        )
    table = _clone_table(ref.shapes[3], a, rows, [3352800, 2209800, 1752600, 1752600, 1752600])
    c = f["terms"]["contract"]
    interp = _clone_text(
        _shape(ref, "pricing-interpretation"),
        a,
        "terms-interpretation",
        f"Every customer type earns its target over the cycle. The contract list spends {c['breach_rate']:.0%} of weeks "
        f"more than 10 points under; a 5-point escalator clause cuts that to {f['contract_band_breach_rate']:.0%}.",
    )
    t = _clone_text(
        _shape(ref, "pricing-caveat"),
        a,
        "terms-caveat",
        "Customer shares and terms are assumptions (config/customer_terms.csv), separate from the synthetic pricing-desk "
        "customers. Breach: margin more than 10 points below target. Swing: standard deviation of monthly margin vs target.",
    )
    interp.top = Emu(table.top + table.height + 300000)
    t.top = Emu(interp.top + 1180000)

    # ---- slide B: margin variance by cause
    b = prs.slides.add_slide(layout)
    for ph in list(b.placeholders):
        ph._element.getparent().remove(ph._element)
    _clone_text(_shape(ref, "title"), b, "terms-title", "Most margin variance comes from timing, not terms")
    _clone_text(_shape(ref, "page"), b, "terms-page", "")
    _clone_text(
        _shape(ref_lag, "lag-subtitle"),
        b,
        "terms-subtitle",
        "Gross margin minus margin at target, all customer types, CAD thousands by year",
    )
    lag_chart = next(s for s in ref_lag.shapes if s.has_chart)
    cd = CategoryChartData()
    cd.categories = [str(y) + ("*" if y in (2021, 2022, 2024) else "") for y in yv.year]
    cd.add_series("Cost timing", [round(v / 1000, 1) for v in yv.var_cost_timing])
    cd.add_series("Price hold", [round(v / 1000, 1) for v in yv.var_price_hold])
    gf = b.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_STACKED, lag_chart.left, lag_chart.top, lag_chart.width, lag_chart.height, cd
    )
    gf.name = "terms-chart"
    ch = gf.chart
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(11)
    ch.plots[0].gap_width = 60
    ch.plots[0].overlap = 100
    for s, col in zip(ch.series, [NAVY, GREEN], strict=True):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = col
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = RGBColor(0xE1, 0xE8, 0xE5)
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(11)
    va.tick_labels.number_format = '0"K"'
    va.tick_labels.number_format_is_linked = False
    ch.category_axis.tick_labels.font.size = Pt(11)
    ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    ch.category_axis.format.line.color.rgb = RGBColor(0x9A, 0xA5, 0xAC)
    wm = f["worst_month"]
    month = pd.Timestamp(wm["month"]).strftime("%b %Y")
    concl = copy.deepcopy(_shape(ref_lag, "lag-conclusion")._element)
    b.shapes._spTree.append(concl)
    sh = b.shapes[-1]
    sh.name = "terms-conclusion"
    tf = sh.text_frame
    texts = [
        month,
        f"Lettuce cost tripled in one week: {abs(wm['gap_pts']):.0f} pts under target, ${-wm['var_cost_timing'] / 1000:.1f}K of "
        f"${-wm['var_total'] / 1000:.1f}K from cost timing",
        "",
        "Price hold",
        "The part contract terms can fix",
    ]
    proto = [p for p in tf.paragraphs if p.runs][:2]
    for p in list(tf.paragraphs):
        p._p.getparent().remove(p._p)
    for i, txt in enumerate(texts):
        src = proto[0] if i in (0, 3) else proto[1]
        p = copy.deepcopy(src._p)
        tf._txBody.append(p)
        para = tf.paragraphs[-1]
        for r in para.runs[1:]:
            r._r.getparent().remove(r._r)
        if para.runs:
            para.runs[0].text = txt
        else:
            para.add_run().text = txt
    _clone_text(
        _shape(ref_lag, "lag-caveat"),
        b,
        "terms-caveat",
        f"Month by month, cost timing (quoting on last week's cost) is {f['timing_share_of_abs_monthly_variance']:.0%} of the "
        f"absolute swing and the larger cause in {f['months_timing_larger']:.0%} of months; price hold is the cost of keeping a "
        "list or band price. Both reconcile to the dollar in Python, SQL and Excel. *Partial year (source gap or end of series).",
    )

    # ---- move the two new slides after the supply-shock slide, then renumber
    new = [sld_ids[-2], sld_ids[-1]]
    for el in new:
        sld_ids.remove(el)
    for k, el in enumerate(new):
        sld_ids.insert(INSERT_AT + k, el)
    n = len(prs.slides)
    for i, s in enumerate(prs.slides):
        for shp in s.shapes:
            if shp.name in ("page", "terms-page") and shp.has_text_frame:
                run = shp.text_frame.paragraphs[0].runs[0]
                run.text = f"{i + 1}  /  {n}"
    prs.save(DECK)
    print("saved", DECK, n, "slides")


if __name__ == "__main__":
    main()

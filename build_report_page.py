"""Build outputs/index.html: a one-page report (KPIs, charts, latest Market Update) for GitHub Pages."""

import base64
import json
from pathlib import Path

import markdown

OUT = Path("outputs")
f = json.loads((OUT / "headline_facts.json").read_text(encoding="utf-8"))
img = lambda n: "data:image/png;base64," + base64.b64encode((OUT / "img" / n).read_bytes()).decode()  # noqa: E731
upd = markdown.markdown((OUT / "market_update_2024-01-30.md").read_text(encoding="utf-8"), extensions=["tables"])
crisis = markdown.markdown((OUT / "market_update_2022-12-13.md").read_text(encoding="utf-8"), extensions=["tables"])
pol = f["policy"]
kpis = [
    (f"{f['quotes_raw']:,}", "real Toronto wholesale quotes, 2017-2024"),
    (
        f"+{f['basket_change_2019_2023_geo']:.0%}",
        f"basket price change 2019 to 2023 ({f['items_up_2019_2023']} of {f['items_compared']} items up)",
    ),
    (
        f"{pol['monthly']['breach_rate']:.0%} -> {pol['band']['breach_rate']:.0%}",
        "weeks >10 pts under target margin: monthly list vs band rule",
    ),
    (
        f"-{1 - f['budget_wape_6m']['seasonal'] / f['budget_wape_6m']['flat']:.0%}",
        "6-month budget forecast error vs flat, unseen 2023 test",
    ),
]
tiles = "".join(f'<div class="kpi"><div class="v">{v}</div><div class="l">{lab}</div></div>' for v, lab in kpis)
html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Toronto Produce Market Pulse</title><style>
:root{{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--rule:#e4e3df;--accent:#2a78d6}}
body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 -apple-system,Segoe UI,Roboto,Arial,sans-serif}}
main{{max-width:1040px;margin:0 auto;padding:32px 20px 64px}} h1{{font-size:28px;margin:0 0 4px}} h2{{font-size:20px;margin:40px 0 8px;border-top:1px solid var(--rule);padding-top:24px}}
.sub{{color:var(--ink2);margin:0 0 20px}} .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}
.kpi{{border:1px solid var(--rule);border-radius:8px;padding:14px 16px;background:#fff}} .kpi .v{{font-size:26px;font-weight:700}} .kpi .l{{color:var(--ink2);font-size:13px}}
img{{max-width:100%;border:1px solid var(--rule);border-radius:6px;margin:8px 0}} table{{border-collapse:collapse;font-size:13px;margin:8px 0;width:100%}}
th,td{{border-bottom:1px solid var(--rule);padding:5px 8px;text-align:left}} th{{background:#f0efec}} details{{margin:12px 0}} summary{{cursor:pointer;color:var(--accent);font-weight:600}}
.note{{color:var(--ink2);font-size:13px}} .report{{background:#fff;border:1px solid var(--rule);border-radius:8px;padding:4px 20px 12px}} .report h1{{font-size:20px}} .report h2{{font-size:16px;border:0;margin-top:20px;padding-top:0}}
</style></head><body><main>
<h1>Toronto Produce Market Pulse</h1>
<p class="sub">Pricing, margin and market intelligence for a foodservice produce distributor, on real Toronto terminal-market prices (USDA AMS / Infohort, Agriculture and Agri-Food Canada), in CAD. By Kush Patel.</p>
<div class="kpis">{tiles}</div>
<p class="note">Historical case study: source ends January 2024, not a live market feed. The Streamlit app adds a customer and pricing decision desk using clearly labelled synthetic customers and competitor comparators. Anomaly exclusions use a centred window; backtests are conditional on retrospective cleaning.</p>
<h2>Market: historical produce costs</h2><img src="{img("basket_index.png")}" alt="Monthly basket index 2017-2024, 2019 = 100">
<img src="{img("price_change_2019_2023.png")}" alt="Price change by item, 2023 vs 2019">
<h2>Supply shock: the late-2022 lettuce crisis</h2><img src="{img("lettuce_crisis_2022.png")}" alt="Romaine and iceberg weekly prices Nov 2022 - Jan 2024">
<details><summary>What the Market Update said the week of December 13, 2022</summary><div class="report">{crisis}</div></details>
<h2>Pricing: how often to reprice</h2><img src="{img("pricing_policies.png")}" alt="Pricing policy comparison">
<p class="note">Gross-margin dollars over a full cycle are within 1% across policies; the difference is risk. Recommended: monthly list for apples, bananas, mushrooms; band rule for avocados, carrots, garlic, kale, lemons, onions; weekly for the rest.</p>
<h2>Seasonal buying calendar</h2><img src="{img("seasonality.png")}" alt="Seasonal index heatmap by item and month">
<h2>Forecasting and budget</h2><img src="{img("forecast_test_2023.png")}" alt="Forecast error flat vs seasonal on 2023 test"><img src="{img("budget_tornado.png")}" alt="Budget sensitivity tornado">
<h2>Latest weekly Market Update</h2><div class="report">{upd}</div>
<p class="note">Margins use illustrative target margins and a 6% freight and handling allowance (config/basket.csv). Source gap: no Toronto reports April 2021 - November 2022. Four weeks with failed currency conversion are excluded. Code: python run_pipeline.py.</p>
</main></body></html>"""
(OUT / "index.html").write_text(html, encoding="utf-8")
print("wrote outputs/index.html", len(html) // 1024, "KB")

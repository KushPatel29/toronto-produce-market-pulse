"""Export the commercial case study and runnable SQLite analytics layer."""

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from pulse import commercial as cm  # noqa: E402
from pulse import procurement as pc  # noqa: E402


def main():
    out = ROOT / "outputs" / "commercial_demo"
    out.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(ROOT / "data/processed/weekly_item_panel.csv", parse_dates=["date"])
    basket = pd.read_csv(ROOT / "config/basket.csv")
    sales = cm.demo_sales(panel, basket)
    competitors = cm.demo_competitors(sales)
    recs = cm.recommendations(sales, competitors)
    alerts = cm.procurement_alerts(panel, sales.date.max())
    bids = pc.demo_supplier_bids(panel, basket, sales.date.max())
    evaluated_bids, supplier_recs = pc.compare_supplier_bids(bids, basket, sales.date.max())
    tables = {
        "SYNTHETIC_sales": sales,
        "SYNTHETIC_competitors": competitors,
        "price_candidates": recs,
        "procurement_alerts": alerts,
        "contribution_variance_bridge": cm.variance_bridge(sales),
        "customer_profitability": cm.profitability(sales),
        "SYNTHETIC_supplier_bids": bids,
        "supplier_bid_evaluation": evaluated_bids,
        "supplier_review_queue": supplier_recs,
    }
    for name, table in tables.items():
        table.to_csv(out / f"{name}.csv", index=False)
    (out / "decision_brief.md").write_text(cm.executive_brief(sales, recs, alerts), encoding="utf-8")
    with sqlite3.connect(out / "demo_analytics.sqlite") as conn:
        sales.to_sql("fact_sales", conn, if_exists="replace", index=False)
        basket.to_sql("dim_item", conn, if_exists="replace", index=False)
        panel.to_sql("fact_market_quotes", conn, if_exists="replace", index=False)
        competitors.to_sql("fact_competitor_quotes", conn, if_exists="replace", index=False)
        bids.to_sql("fact_supplier_bids", conn, if_exists="replace", index=False)
        conn.executescript((ROOT / "sql" / "commercial_views.sql").read_text(encoding="utf-8"))
        sql_total = conn.execute("SELECT SUM(contribution) FROM v_customer_margin").fetchone()[0]
        py_total = cm.profitability(sales).contribution.sum()
        if abs(sql_total - py_total) > 0.001:
            raise ValueError("SQL/Python contribution reconciliation failed")
    summary = dict(
        data_status="SYNTHETIC commercial demo; real historical cost proxies",
        week=str(sales.date.max().date()), rows=len(sales),
        revenue=float(cm.profitability(sales).revenue.sum()),
        contribution=float(py_total), sql_contribution=float(sql_total),
        finance_review_candidates=int((recs.approval == "Finance + Sales review").sum()),
        procurement_review_items=int(alerts.review.sum()),
        supplier_items_requiring_escalation=int(supplier_recs.supplier.eq("No feasible single supplier").sum()),
    )
    (out / "validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

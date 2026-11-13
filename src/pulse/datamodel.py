"""Star schema for the pricing model: SQLite database plus CSV exports for Power BI / Tableau."""

from __future__ import annotations
import sqlite3
from pathlib import Path

import pandas as pd
from .pricing import HANDLING

ROOT = Path(__file__).resolve().parents[2]


def tables(panel: pd.DataFrame, basket: pd.DataFrame, segments: pd.DataFrame, seg_detail: pd.DataFrame) -> dict:
    dates = panel[["date", "period"]].drop_duplicates().sort_values("date")
    dim_date = pd.DataFrame(
        {
            "date_key": dates.date.dt.strftime("%Y-%m-%d"),
            "year": dates.date.dt.year,
            "month": dates.date.dt.month,
            "year_month": dates.date.dt.strftime("%Y-%m"),
            "period": dates.period,
        }
    )
    dim_item = basket.rename(columns={"display_name": "item_name", "unit_note": "uom"})[
        ["item_id", "item_name", "category", "uom", "target_margin", "weekly_cases"]
    ]
    n = panel["n_quotes"] if "n_quotes" in panel else pd.Series(pd.NA, index=panel.index)
    fact_market = pd.DataFrame(
        {
            "item_id": panel.item_id,
            "date_key": panel.date.dt.strftime("%Y-%m-%d"),
            "terminal_cad": panel.price_cad.round(4),
            "landed_cost": (panel.price_cad * (1 + HANDLING)).round(4),
            "n_quotes": n,
        }
    )
    d = seg_detail
    fact_sales = pd.DataFrame(
        {
            "item_id": d.item_id,
            "segment_id": d.segment_id,
            "date_key": d.date.dt.strftime("%Y-%m-%d"),
            "cases": d.cases.round(3),
            "sell_price": d.price.round(4),
            "landed_cost": d.cost.round(4),
            "prior_cost": d.cost_prev.round(4),
            "target_margin": d.target.round(4),
            "price_changed": d.changed.astype(int),
        }
    )
    return {
        "dim_item": dim_item,
        "dim_segment": segments,
        "dim_date": dim_date,
        "fact_market_price": fact_market,
        "fact_sales_price": fact_sales,
    }


def build(tabs: dict, db_path: Path, csv_dir: Path | None = None) -> None:
    db_path.unlink(missing_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.executescript((ROOT / "sql" / "star_schema" / "schema.sql").read_text(encoding="utf-8"))
        for name, df in tabs.items():
            df.to_sql(name, con, if_exists="append", index=False)
        con.commit()
    finally:
        con.close()
    if csv_dir is not None:
        csv_dir.mkdir(parents=True, exist_ok=True)
        for name, df in tabs.items():
            df.to_csv(csv_dir / f"{name}.csv", index=False)


def run_query(db_path: Path, name: str) -> pd.DataFrame:
    con = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query((ROOT / "sql" / "star_schema" / name).read_text(encoding="utf-8"), con)
    finally:
        con.close()

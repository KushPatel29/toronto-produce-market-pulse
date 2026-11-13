"""Verify source snapshot integrity, report coverage and SQL financial identities."""

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from pulse import report as rp  # noqa: E402


def main():
    manifest = json.loads((ROOT / "config/source_manifest.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["sha256"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Source snapshot changed: {relative}")
    p = pd.read_csv(ROOT / "data/processed/weekly_item_panel.csv", parse_dates=["date"])
    b = pd.read_csv(ROOT / "config/basket.csv")
    if p.duplicated(["item_id", "date"]).any() or not (p.price_cad > 0).all():
        raise ValueError("Invalid processed panel keys or prices")
    for week in sorted(p.date.unique()):
        text = rp.to_markdown(rp.market_update(p, b, str(pd.Timestamp(week).date())))
        if "Full item table" not in text:
            raise ValueError("Incomplete weekly report")
    with sqlite3.connect(ROOT / "outputs/commercial_demo/demo_analytics.sqlite") as conn:
        residual = conn.execute("""SELECT SUM(budget_contribution + volume_mix_effect +
            net_price_effect + cost_effect - actual_contribution) FROM v_finance_bridge""").fetchone()[0]
        if not np.isfinite(residual) or abs(residual) > .001:
            raise ValueError("SQL contribution bridge does not reconcile")
    result = dict(source_checksums="passed", report_dates_rendered=int(p.date.nunique()),
                  sql_bridge_residual_cad=float(residual), panel_key_validation="passed")
    (ROOT / "outputs/release_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

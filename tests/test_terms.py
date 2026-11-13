"""Customer pricing terms, margin-variance bridge, star schema and ERP price list."""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
from pulse import datamodel as dm, terms as tm  # noqa: E402
from pulse.panel import build  # noqa: E402


@pytest.fixture(scope="module")
def seg():
    _, _, panel, _ = build(save=False)
    basket = pd.read_csv("config/basket.csv")
    segs = pd.read_csv("config/customer_terms.csv")
    return panel, basket, segs, tm.replay(panel, basket, segs)


def test_terms_config_is_complete(seg):
    segs = seg[2]
    assert np.isclose(segs.volume_share.sum(), 1.0)
    assert set(segs.pricing_policy) <= {"weekly", "band", "monthly"}


def test_variance_bridge_reconciles_exactly(seg):
    d = seg[3]
    assert np.allclose(d.var_total, d.var_cost_timing + d.var_price_hold)
    assert np.isclose(d.gm.sum() - d.gm_target.sum(), d.var_total.sum())
    weekly = d[d.policy == "weekly"]
    assert np.allclose(weekly.var_price_hold, 0, atol=1e-9)  # weekly pricing never holds a stale price


def test_no_price_bridges_an_item_gap(seg):
    panel, _, _, d = seg
    p = panel.sort_values("date")[["item_id", "date", "price_cad"]].copy()
    p["prev_date"] = p.groupby("item_id").date.shift()
    m = d.merge(p, on=["item_id", "date"], how="left")
    assert (panel.sort_values("date").groupby("item_id").date.diff().dt.days > 14).any()  # gaps exist
    # every scored week is priced on a cost observed at most 14 days earlier
    assert ((m.date - m.prev_date).dt.days <= 14).all()


def test_terms_split_item_volume(seg):
    _, basket, _, d = seg
    wk = d.groupby(["item_id", "date"]).cases.sum().reset_index()
    exp = wk.item_id.map(basket.set_index("item_id").weekly_cases)
    assert np.allclose(wk.cases, exp)


def test_sql_matches_pandas(seg, tmp_path):
    panel, basket, segs, d = seg
    db = tmp_path / "m.sqlite"
    dm.build(dm.tables(panel, basket, segs, d), db)
    q = dm.run_query(db, "01_terms_profitability.sql").set_index("segment")
    p = tm.segment_pnl(d).merge(segs[["segment_id", "segment"]]).set_index("segment")
    assert np.allclose(q.gm_pct, p.gm_pct.reindex(q.index), atol=1e-4)
    assert np.allclose(q.breach_rate, p.breach_rate.reindex(q.index), atol=2e-3)
    mv = dm.run_query(db, "02_margin_variance_by_month.sql")
    assert abs(mv.variance.sum() - d.var_total.sum()) < len(mv)  # whole-dollar rounding per month
    assert len(dm.run_query(db, "03_reprice_list.sql")) > 0


def test_price_list_is_valid_upload(seg):
    _, basket, segs, d = seg
    pl = tm.price_list(d, basket, segs, "2024-01-30")
    assert not pl.duplicated(["item_code", "price_group"]).any()
    assert (pl.unit_price > 0).all() and pl.notna().all().all()
    held = pl[pl.reason == "HELD"]
    assert np.allclose(held.unit_price, held.prior_price)

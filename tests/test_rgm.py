"""Price-volume-mix bridge and promotion evaluation (synthetic volumes on real costs)."""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
from pulse import rgm  # noqa: E402
from pulse.panel import build  # noqa: E402
from pulse.pricing import HANDLING  # noqa: E402


@pytest.fixture(scope="module")
def sim():
    _, _, panel, _ = build(save=False)
    basket = pd.read_csv("config/basket.csv")
    w, ev = rgm.simulate(panel, basket)
    return panel, w, ev


def test_bridge_reconciles_exactly(sim):
    _, w, _ = sim
    bridge, detail = rgm.pvm(w, 2019, 2023)
    effects = bridge.cad.iloc[1:-1].sum()
    assert np.isclose(effects, bridge.cad.iloc[-1] - bridge.cad.iloc[0])
    per_item = detail[["volume", "mix", "list_price", "trade", "cost"]].sum(axis=1)
    assert np.isclose(per_item.sum(), (detail.gm_b - detail.gm_a).sum())


def test_volume_and_mix_vanish_when_cases_are_unchanged(sim):
    _, w, _ = sim
    a = w[w.year == 2019]
    shares = a.groupby("item_id").cases.sum() / a.cases.sum()
    b = w[w.year == 2023].copy()
    totals = b.groupby("item_id").cases.transform("sum")
    target = b.item_id.map(shares) * a.cases.sum()
    b["cases"] = b.cases / totals * target
    for col in ["revenue", "list_revenue", "cogs"]:
        unit = {"revenue": "net_price", "list_revenue": "list_price", "cogs": "unit_cost"}[col]
        b[col] = b.cases * b[unit]
    b["gm"] = b.revenue - b.cogs
    bridge, _ = rgm.pvm(pd.concat([a, b]), 2019, 2023)
    eff = bridge.set_index("driver").cad
    assert abs(eff["Volume"]) < 1e-6 and abs(eff["Mix"]) < 1e-6


def test_costs_are_real_and_no_price_bridges_a_gap(sim):
    panel, w, _ = sim
    m = w.merge(panel[["item_id", "date", "price_cad"]], on=["item_id", "date"])
    assert np.allclose(m.unit_cost, m.price_cad * (1 + HANDLING))
    p = panel.sort_values("date")[["item_id", "date"]].copy()
    p["prev"] = p.groupby("item_id").date.shift()
    x = w.merge(p, on=["item_id", "date"])
    assert ((x.date - x.prev).dt.days <= 14).all()
    assert w.data_status.str.startswith("SYNTHETIC").all()


def test_promotion_lift_is_recovered(sim):
    _, w, ev = sim
    r = rgm.promo_eval(w, ev)
    assert len(r) >= 90
    assert r.uplift_error_pts.abs().mean() < 12  # measured vs planted lift
    agree = ((r.est_uplift > r.breakeven_uplift) == (r.roi > 0)).mean()
    assert agree > 0.9


def test_breakeven_formula_by_hand():
    # margin 25% of a $100 case, 10% cut, no fee, no dip: needs 25 / 15 = 1.667x
    m, d, price, base, n = 25.0, 0.10, 100.0, 10.0, 2
    bn = base * n
    be = (bn * m + rgm.PROMO_FEE * 0) / (bn * (m - d * price))
    assert np.isclose(be, 25 / 15)

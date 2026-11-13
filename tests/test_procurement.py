"""Supplier feasibility and usable-case procurement-cost arithmetic."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pulse import procurement as pc  # noqa: E402


@pytest.fixture
def data():
    basket = pd.DataFrame([dict(item_id="x", display_name="Romaine", unit_note="24 count", weekly_cases=90)])
    bid = dict(item_id="x", supplier="Demo A", unit="24 count", currency="CAD", quote_date="2024-01-30",
               valid_until="2024-02-05", quoted_price=40., freight_per_case=5., spoilage_rate=0.10,
               moq_cases=20, capacity_cases=110, lead_days=1, reliability=0.99)
    return pd.DataFrame([bid]), basket


def test_freight_and_spoilage_are_charged_to_usable_cases(data):
    d, r = pc.compare_supplier_bids(*data, as_of="2024-01-30")
    assert d.delivered_cost_per_usable_case.iloc[0] == pytest.approx(50.)
    assert d.required_order_cases.iloc[0] == 100
    assert r.total_order_cost.iloc[0] == pytest.approx(4500.)
    assert r.order_cases.iloc[0] * 0.9 >= 90


def test_moq_surplus_changes_lowest_total_cost_choice(data):
    bids, basket = data
    cheap = bids.iloc[0].to_dict() | {"supplier": "Cheap nominal", "quoted_price": 35., "moq_cases": 200, "capacity_cases": 200}
    bids = pd.concat([bids, pd.DataFrame([cheap])], ignore_index=True)
    d, r = pc.compare_supplier_bids(bids, basket, "2024-01-30")
    assert d.feasible.all()
    assert r.supplier.iloc[0] == "Demo A"


@pytest.mark.parametrize("field,value", [
    ("quote_date", "2024-02-01"), ("quote_date", "2023-12-01"), ("valid_until", "2024-01-29"),
    ("unit", "wrong pack"), ("currency", "USD"), ("lead_days", 3), ("reliability", 0.8),
    ("spoilage_rate", 1.0), ("quoted_price", -1), ("capacity_cases", 99),
])
def test_infeasible_quotes_are_not_recommended(data, field, value):
    bids, basket = data
    bids.loc[0, field] = value
    d, r = pc.compare_supplier_bids(bids, basket, "2024-01-30")
    assert not d.feasible.iloc[0]
    assert r.order_cases.iloc[0] == 0
    assert "No feasible" in r.supplier.iloc[0]


def test_capacity_shortfall_is_measured_in_usable_cases(data):
    bids, basket = data
    bids.loc[0, "capacity_cases"] = 80
    _, r = pc.compare_supplier_bids(bids, basket, "2024-01-30")
    assert r.single_supplier_shortfall_cases.iloc[0] == pytest.approx(18)


def test_capacity_below_moq_cannot_be_used(data):
    bids, basket = data
    bids.loc[0, ["capacity_cases", "moq_cases"]] = [80, 100]
    _, r = pc.compare_supplier_bids(bids, basket, "2024-01-30")
    assert r.single_supplier_shortfall_cases.iloc[0] == 90


def test_demo_bid_generation_is_deterministic_and_as_of():
    basket = pd.read_csv(ROOT / "config/basket.csv")
    panel = pd.read_csv(ROOT / "data/processed/weekly_item_panel.csv", parse_dates=["date"])
    week = pd.Timestamp("2022-12-13")
    a = pc.demo_supplier_bids(panel, basket, week)
    b = pc.demo_supplier_bids(panel[panel.date <= week], basket, week)
    pd.testing.assert_frame_equal(a, b)
    assert a.supplier.nunique() == 3
    assert a.data_status.str.startswith("SYNTHETIC").all()

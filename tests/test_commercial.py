"""Financial reconciliation, comparability and missing-history regression tests."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pulse import commercial as cm, report as rp, forecast as fc  # noqa: E402


@pytest.fixture
def demo():
    panel = pd.read_csv(ROOT / "data/processed/weekly_item_panel.csv", parse_dates=["date"])
    basket = pd.read_csv(ROOT / "config/basket.csv")
    return panel, basket, cm.demo_sales(panel, basket)


def test_bridge_reconciles_to_actual_with_price_cost_volume_changes(demo):
    sales = demo[2].copy()
    # Stress non-uniform changes so volume/mix and cross terms cannot cancel accidentally.
    sales.loc[sales.index[::3], "actual_cases"] *= 1.7
    sales.loc[sales.index[1::3], "actual_unit_cost"] *= 1.4
    sales.loc[sales.index[2::3], "actual_net_price"] *= 0.8
    b = cm.variance_bridge(sales)
    assert b.cad.iloc[:-1].sum() == pytest.approx(b.cad.iloc[-1])
    p = cm.profitability(sales)
    assert p.contribution.sum() == pytest.approx(p.revenue.sum() - p.variable_cost.sum())
    # Revenue weighting, not average of customer percentages.
    assert np.average(p.margin_pct, weights=p.revenue) == pytest.approx(p.contribution.sum() / p.revenue.sum())


@pytest.mark.parametrize("field,value", [("actual_net_price", 0), ("actual_cases", -1),
                                          ("actual_unit_cost", np.inf), ("target_margin", 1)])
def test_invalid_financial_inputs_rejected(demo, field, value):
    sales = demo[2].copy()
    sales.loc[0, field] = value
    with pytest.raises(ValueError):
        cm.profitability(sales)


def test_duplicate_customer_item_rejected(demo):
    with pytest.raises(ValueError, match="unique"):
        cm.profitability(pd.concat([demo[2], demo[2].iloc[:1]]))


@pytest.mark.parametrize("field,value", [("customer", "  "), ("item_id", None), ("date", "not-a-date"),
                                         ("rebate", 1.0), ("discount", -0.1), ("spoilage_rate", np.nan)])
def test_sales_contract_rejects_bad_keys_dates_and_rates(demo, field, value):
    sales = demo[2].copy()
    sales[field] = sales[field].astype(object)
    sales.loc[0, field] = value
    with pytest.raises(ValueError):
        cm.profitability(sales)


def test_numeric_csv_strings_are_normalised_before_arithmetic(demo):
    sales = demo[2].copy()
    expected = cm.profitability(sales).revenue.sum()
    for field in ["actual_cases", "actual_net_price", "target_margin"]:
        sales[field] = sales[field].astype(str)
    assert cm.profitability(sales).revenue.sum() == pytest.approx(expected)


def test_sales_duplicate_keys_detected_after_date_and_key_normalisation(demo):
    sales = demo[2].iloc[:1].copy()
    duplicate = sales.copy()
    duplicate["date"] = duplicate.date.dt.strftime("%Y-%m-%d")
    duplicate["customer"] = duplicate.customer + " "
    with pytest.raises(ValueError, match="unique"):
        cm.profitability(pd.concat([sales, duplicate]))


def test_recommendations_reach_margin_without_hiding_market_conflicts(demo):
    sales = demo[2]
    competitors = cm.demo_competitors(sales)
    competitors["price"] *= 0.2
    r = cm.recommendations(sales, competitors)
    assert r.market_guardrail_conflict.all()
    assert (r.approval == "Finance + Sales review").all()
    assert np.all(1 - sales.actual_unit_cost / r.suggested_net_price >= sales.target_margin - 1e-10)


@pytest.mark.parametrize("field,value", [("currency", "USD"), ("unit", "wrong pack"),
                                         ("quote_date", "2000-01-01"), ("quote_date", "2099-01-01")])
def test_noncomparable_competitors_excluded(demo, field, value):
    c = cm.demo_competitors(demo[2])
    c[field] = value
    r = cm.recommendations(demo[2], c)
    assert (r.comparable_quotes == 0).all()
    assert r.competitor_median.isna().all()
    assert r.suggested_net_price.notna().all()


def test_competitor_comparisons_are_customer_specific_net_prices(demo):
    sales = demo[2]
    c = cm.demo_competitors(sales)
    r = cm.recommendations(sales, c)
    assert (r.comparable_quotes == 5).all()
    assert np.allclose(r.competitor_median, sales.actual_net_price)
    assert c.price_basis.eq("net_after_discounts_rebates").all()


@pytest.mark.parametrize("field,value", [("customer", "unrelated customer"),
                                         ("price_basis", "gross_list"), ("quote_date", "invalid"),
                                         ("price", "not-a-price")])
def test_ambiguous_or_wrong_basis_comparators_are_not_used(demo, field, value):
    c = cm.demo_competitors(demo[2])
    c[field] = value
    r = cm.recommendations(demo[2], c)
    assert (r.comparable_quotes == 0).all()


def test_duplicate_comparators_do_not_change_market_median(demo):
    c = cm.demo_competitors(demo[2])
    expected = cm.recommendations(demo[2], c)
    duplicated = pd.concat([c, c[c.competitor == "Demo comparator 1"]] * 3)
    actual = cm.recommendations(demo[2], duplicated)
    assert np.allclose(actual.competitor_median, expected.competitor_median)
    assert (actual.comparable_quotes == 5).all()


def test_latest_per_competitor_and_conflicting_quote_exclusion(demo):
    sales = demo[2].iloc[:1]
    c = cm.demo_competitors(sales)
    older = c.copy()
    older["quote_date"] -= pd.Timedelta(days=7)
    older["price"] *= 0.1
    r = cm.recommendations(sales, pd.concat([c, older]))
    assert r.competitor_median.iloc[0] == pytest.approx(sales.actual_net_price.iloc[0])
    conflicting = c.iloc[:1].copy()
    conflicting["price"] *= 2
    r = cm.recommendations(sales, pd.concat([c, older, conflicting]))
    assert r.comparable_quotes.iloc[0] == 4


def test_held_above_market_price_is_not_reported_as_target_floor_conflict(demo):
    sales = demo[2].iloc[:1].copy()
    sales["actual_net_price"] = 120.0
    sales["actual_unit_cost"] = 70.0
    sales["target_margin"] = 0.25
    c = cm.demo_competitors(sales)
    c["price"] = 100.0
    r = cm.recommendations(sales, c).iloc[0]
    assert not r.market_guardrail_conflict
    assert r.current_above_market
    assert r.increase_pct == 0
    assert r.approval == "Sales review"
    assert "existing above-market" in r.reason


def test_demo_is_reproducible_and_does_not_use_future_prices(demo):
    panel, basket, sales = demo
    pd.testing.assert_frame_equal(sales, cm.demo_sales(panel, basket))
    week = pd.Timestamp("2022-12-13")
    a = cm.demo_sales(panel, basket, week)
    changed = panel.copy()
    changed.loc[changed.date > week, "price_cad"] *= 99
    pd.testing.assert_frame_equal(a, cm.demo_sales(changed, basket, week))


def test_gap_restart_has_no_stale_list_price_or_demo_sales(demo):
    panel, basket, _ = demo
    week = panel[panel.period == "B_2022_2024"].date.min()
    u = rp.market_update(panel, basket, str(week.date()))
    assert u["table"].list_price.isna().all()
    assert (u["table"].action == "Insufficient recent history").all()
    assert cm.demo_sales(panel, basket, week).empty


def test_forecast_state_restarts_after_gap():
    dates = list(pd.date_range("2020-01-01", periods=12, freq="7D")) + list(pd.date_range("2023-01-01", periods=3, freq="7D"))
    panel = pd.DataFrame({"item_id": "x", "date": dates, "price_cad": [100.] * 12 + [10.] * 3})
    # seasonal_index requires no display/category fields; empty training years give naive fallback.
    bt = fc.backtest(panel, windows=[("2023-01-01", "2023-02-01", (2017, 2018))], horizons=(1,))
    assert np.allclose(bt[bt.model == "ses"].fcst, 10.)


def test_procurement_alerts_do_not_use_future_quotes(demo):
    panel = demo[0]
    week = pd.Timestamp("2022-12-13")
    a = cm.procurement_alerts(panel, week)
    pd.testing.assert_frame_equal(a, cm.procurement_alerts(panel[panel.date <= week], week))

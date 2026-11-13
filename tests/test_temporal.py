"""Regression tests for item-specific gaps and calendar-aware risk measures."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pulse import market as mk, pricing as pr  # noqa: E402


@pytest.mark.parametrize("policy", ["weekly", "monthly", "band"])
def test_price_state_restarts_after_item_gap(policy):
    dates = pd.Series(list(pd.date_range("2020-01-06", periods=5, freq="7D"))
                      + list(pd.date_range("2020-04-06", periods=5, freq="7D")))
    cost = np.array([50.] * 5 + [100.] * 5)
    price, changed = pr._simulate(cost, dates, 0.25, policy)
    assert np.isnan(price[5])  # no quote against the stale January cost
    assert np.allclose(price[6:], 100 / 0.75)
    assert not changed[5] and not changed[6]  # reinitialisation is not a list-price change
    # Returning segment must not depend on historical costs before the gap.
    cost[:5] *= 8
    revised, _ = pr._simulate(cost, dates, 0.25, policy)
    np.testing.assert_allclose(revised[5:], price[5:], equal_nan=True)


def test_backtest_does_not_score_first_quote_after_internal_gap():
    dates = list(pd.date_range("2020-01-06", periods=5, freq="7D"))
    dates += list(pd.date_range("2020-04-06", periods=5, freq="7D"))
    panel = pd.DataFrame({"item_id": "x", "period": "A", "date": dates,
                          "price_cad": [50.] * 5 + [100.] * 5})
    basket = pd.DataFrame({"item_id": ["x"], "target_margin": [0.25]})
    detail, _ = pr.backtest(panel, basket)
    assert pd.Timestamp("2020-04-06") not in set(detail.date)
    assert np.allclose(detail.margin, 0.25)


def _risk_panel(dates):
    return pd.DataFrame({"item_id": "x", "period": "A", "date": pd.to_datetime(dates),
                         "display_name": "Example", "category": "Example",
                         "price_cad": [10., 10., 10., 10., 20.],
                         "rel_cad": [np.nan, 1., 1., 1., 2.]})


def test_four_week_risk_denominator_excludes_unobserved_changes():
    dates = pd.date_range("2020-01-06", periods=5, freq="7D")
    result = mk.volatility(_risk_panel(dates)).iloc[0]
    # There is one observable four-week comparison, and it exceeds 15%.
    assert result.share_4wk_move_gt_15pct == 1.0


def test_four_week_risk_rejects_observation_offset_across_long_gap():
    dates = ["2020-01-06", "2020-01-13", "2020-01-20", "2020-01-27", "2020-04-06"]
    result = mk.volatility(_risk_panel(dates)).iloc[0]
    assert np.isnan(result.share_4wk_move_gt_15pct)


def test_four_week_risk_allows_minor_reporting_day_shift():
    dates = ["2020-01-06", "2020-01-13", "2020-01-20", "2020-01-27", "2020-02-04"]
    result = mk.volatility(_risk_panel(dates)).iloc[0]
    assert result.share_4wk_move_gt_15pct == 1.0


def test_weekly_risk_uses_percentage_drop_not_symmetric_log_threshold():
    panel = _risk_panel(pd.date_range("2020-01-06", periods=5, freq="7D"))
    panel["rel_cad"] = [np.nan, 0.905, 0.89, 1.095, 1.11]
    result = mk.volatility(panel).iloc[0]
    assert result.share_weeks_move_gt_10pct == 0.5


def test_seasonal_index_omits_incomplete_item_years():
    rows = [("complete", pd.Timestamp(2020, m, 1), float(m)) for m in range(1, 13)]
    rows += [("complete", pd.Timestamp(2019, m, 1), 999.) for m in range(1, 12)]
    rows += [("partial", pd.Timestamp(2020, m, 1), 100.) for m in range(1, 12)]
    panel = pd.DataFrame(rows, columns=["item_id", "date", "price_cad"])
    result = mk.seasonal_index(panel, years=(2019, 2020))
    assert list(result.index) == ["complete"]
    np.testing.assert_allclose(result.loc["complete"].to_numpy(), np.arange(1, 13) / 6.5)


def test_seasonal_index_equal_month_weight_despite_quote_frequency():
    # January has five reports while every other month has one. It must not
    # receive five times the weight in the item's annual price denominator.
    rows = [("x", pd.Timestamp(2020, m, 1), 20. if m == 1 else 10.) for m in range(1, 13)]
    rows += [("x", pd.Timestamp(2020, 1, day), 20.) for day in [6, 13, 20, 27]]
    rows += [("x", pd.Timestamp(2019, m, 1), 10. if m == 1 else 20.) for m in range(1, 13)]
    panel = pd.DataFrame(rows, columns=["item_id", "date", "price_cad"])
    result = mk.seasonal_index(panel, years=(2019, 2020))
    expected = (np.array([20.] + [10.] * 11) / (130 / 12)
                + np.array([10.] + [20.] * 11) / (230 / 12)) / 2
    np.testing.assert_allclose(result.loc["x"].to_numpy(), expected)


def test_seasonal_index_without_complete_year_has_explicit_empty_support():
    panel = pd.DataFrame({"item_id": ["x"], "date": [pd.Timestamp("2020-01-01")], "price_cad": [10.]})
    result = mk.seasonal_index(panel, years=(2020,))
    assert result.empty
    assert list(result.columns) == list(range(1, 13))


def test_annual_change_matches_calendar_months_and_weights_them_equally():
    dates = ["2019-01-07", "2019-02-04", "2023-01-02", "2023-01-09", "2023-01-16",
             "2023-01-23", "2023-01-30", "2023-02-06", "2023-03-06"]
    panel = pd.DataFrame({"item_id": "x", "display_name": "Example", "category": "Example",
                          "date": pd.to_datetime(dates), "price_cad": [10., 20., 20., 20., 20., 20., 20., 40., 999.]})
    result = mk.annual_change(panel, min_months=2).iloc[0]
    assert result.avg_2019 == 15.
    assert result.avg_2023 == 30.
    assert result.pct_chg == 1.
    assert result.n_months == 2
    assert result.compared_months == "01,02"


def test_annual_change_excludes_items_without_ten_common_months():
    rows = []
    for item, months in [("supported", 10), ("sparse", 9)]:
        for year, price in [(2019, 10.), (2023, 20.)]:
            for month in range(1, months + 1):
                rows.append((item, item, "Example", pd.Timestamp(year, month, 1), price))
    panel = pd.DataFrame(rows, columns=["item_id", "display_name", "category", "date", "price_cad"])
    result = mk.annual_change(panel)
    assert result.item_id.tolist() == ["supported"]
    assert result.n_months.tolist() == [10]


def test_annual_change_missing_comparison_year_returns_explicit_empty_result():
    panel = pd.DataFrame({"item_id": ["x"], "display_name": ["Example"], "category": ["Example"],
                          "date": [pd.Timestamp("2019-01-01")], "price_cad": [10.]})
    result = mk.annual_change(panel)
    assert result.empty
    assert set(["avg_2019", "avg_2023", "pct_chg", "n_months", "compared_months"]) <= set(result.columns)

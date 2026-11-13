"""Scenario timing and calendar-window regressions with hand-calculated examples."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pulse import budget as bg  # noqa: E402


def budget():
    return pd.DataFrame(dict(item_id="x", category="Tomatoes", month=["2024-02", "2024-03", "2024-04", "2024-05", "2024-06"],
                             landed_cost=75., sell_price=100., cases=10., import_share=[.2, .4, .6, .8, .5],
                             revenue=1000., cogs=750., gross_margin=250.))


def test_temporary_shock_delays_both_price_increase_and_reversal():
    d = bg.custom_scenario(budget(), supply_shock=.4)
    assert d.landed_cost.tolist() == pytest.approx([75, 105, 105, 75, 75])
    assert d.sell_price.tolist() == pytest.approx([100, 100, 140, 140, 100])
    assert d.gross_margin.tolist() == pytest.approx([250, -50, 350, 650, 250])


def test_combined_shocks_use_prior_months_exposure_not_current_exposure():
    b = budget()
    d = bg.custom_scenario(b.sample(frac=1, random_state=1), supply_shock=.4, fx_shock=.1).sort_values("month")
    assert d.cost_multiplier.tolist() == pytest.approx([1.02, 1.456, 1.484, 1.08, 1.05])
    assert d.price_multiplier.tolist() == pytest.approx([1, 1.02, 1.456, 1.484, 1.08])
    immediate = bg.custom_scenario(b, supply_shock=.4, price_lag_months=0)
    assert np.allclose(immediate.cost_multiplier, immediate.price_multiplier)


def test_multi_month_lag_recovery_continues_after_cost_shock_ends():
    d = bg.custom_scenario(budget(), supply_shock=.4, price_lag_months=2)
    assert d.price_multiplier.tolist() == pytest.approx([1, 1, 1, 1.4, 1.4])


@pytest.mark.parametrize("lag", [-1, .5, 13])
def test_invalid_lag_rejected(lag):
    with pytest.raises(ValueError):
        bg.custom_scenario(budget(), price_lag_months=lag)


def test_missing_calendar_month_rejected_instead_of_compressing_time():
    with pytest.raises(ValueError, match="missing item/month"):
        bg.custom_scenario(budget().drop(index=1))


def test_spike_quantiles_do_not_borrow_across_year_long_gap():
    dates = list(pd.date_range("2020-01-01", periods=12, freq="MS")) + list(pd.date_range("2023-01-01", periods=5, freq="MS"))
    p = pd.DataFrame(dict(item_id="x", category="Tomatoes", date=dates, price_cad=[10.] * 12 + [1000.] * 5))
    q = bg.historical_spike_quantiles(p)
    assert q.p90.iloc[0] == pytest.approx(1.)

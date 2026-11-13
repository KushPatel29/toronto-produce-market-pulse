"""Horizon labels and training cutoffs must represent calendar time."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pulse import forecast as fc  # noqa: E402


def test_weekly_horizon_does_not_compress_missing_report_week():
    dates = pd.date_range("2020-01-01", periods=18, freq="7D").delete(14)
    p = pd.DataFrame(dict(item_id="x", date=dates, price_cad=10.))
    bt = fc.backtest(p, windows=[("2020-01-01", "2020-06-01", (2017, 2018))], horizons=(1, 2, 4))
    assert (bt.elapsed_days - 7 * bt.h).abs().le(2).all()
    target = pd.Timestamp("2020-04-15")  # first report after omitted April 8
    assert bt[(bt.date == target) & (bt.h == 1)].empty
    assert not bt[(bt.date == target) & (bt.h == 2)].empty


def test_seasonal_inputs_after_origin_cannot_change_forecast():
    dates = pd.date_range("2017-01-01", "2019-02-01", freq="7D")
    p = pd.DataFrame(dict(item_id="x", date=dates, price_cad=[10. + d.month for d in dates]))
    target = pd.Timestamp("2019-01-06")
    a = fc.backtest(p, windows=[(str(target.date()), str(target.date()), (2017, 2018))], horizons=(4,))
    origin = a.origin_date.iloc[0]
    changed = p.copy()
    changed.loc[changed.date > origin, "price_cad"] *= 5
    b = fc.backtest(changed, windows=[(str(target.date()), str(target.date()), (2017, 2018))], horizons=(4,))
    assert a.fcst.tolist() == b.fcst.tolist()

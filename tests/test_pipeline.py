"""Data-quality and logic tests. Run: pytest -q"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import os  # noqa: E402

os.chdir(ROOT)
from pulse import budget as bg, forecast as fc, market as mk, pricing as pr  # noqa: E402
from pulse.panel import build, detect_conversion_anomalies  # noqa: E402


@pytest.fixture(scope="module")
def data():
    raw, rows, panel, anomalies = build(save=False)
    basket = pd.read_csv("config/basket.csv")
    return raw, rows, panel, anomalies, basket


def test_raw_shape_and_dates(data):
    raw = data[0]
    assert len(raw) > 60000
    assert raw.date.min() == pd.Timestamp("2017-01-02") and raw.date.max() == pd.Timestamp("2024-01-30")
    assert (raw.high_price_usd >= raw.low_price_usd).all() and (raw.low_price_usd > 0).all()


def test_fx_covers_every_report_week():
    fx = pd.read_csv("data/raw/boc_usdcad_on_report_dates.csv")
    assert fx.usd_cad.between(1.15, 1.50).all() and len(fx) == 269
    assert abs(fx.usd_cad.sum() - (354.0612 + 1.3435)) < 1e-6  # browser checksum + 2017-01-02 fill


def test_panel_one_row_per_item_week(data):
    panel = data[2]
    assert not panel.duplicated(["item_id", "date"]).any()
    assert (panel.price_cad > 0).all()
    assert panel.item_id.nunique() == 30


def test_source_gap_is_never_bridged(data):
    panel = data[2]
    gap = panel[(panel.date > "2021-04-30") & (panel.date < "2022-11-01")]
    assert gap.empty
    first_b = panel[panel.period == "B_2022_2024"].date.min()
    assert panel[panel.date == first_b].rel_cad.isna().all()


def test_conversion_anomalies_detected(data):
    an = data[3]
    assert set(an.date.dt.strftime("%Y-%m-%d")) == {"2020-08-31", "2023-03-14", "2023-04-25", "2023-05-02"}
    assert not data[2].date.isin(an.date).any()


def test_anomaly_detector_flags_injected_error(data):
    panel = data[2].copy()
    fx = pd.read_csv("data/raw/boc_usdcad_on_report_dates.csv", parse_dates=["report_date"]).rename(
        columns={"report_date": "date"}
    )
    wk = pd.Timestamp("2019-06-03")
    rate = fx.set_index("date").usd_cad[wk]
    panel.loc[panel.date == wk, "price_cad"] *= rate  # simulate "published in CAD, labelled USD"
    flagged = detect_conversion_anomalies(panel.assign(period=np.where(panel.date < "2022-01-01", "A", "B")), fx)
    assert wk in set(flagged.date)
    assert "labelled USD" in flagged.set_index("date").diagnosis[wk]


def test_unchanged_quotes_show_zero_change(data):
    panel = data[2]
    # stable items: like-for-like change is exactly flat in a large share of weeks once conversion noise is removed
    m = panel[panel.item_id == "apples"].rel_cad.dropna()
    assert (m.sub(1).abs() < 1e-3).mean() > 0.5


def test_weekly_policy_hits_target_when_cost_is_flat():
    dates = pd.Series(pd.date_range("2020-01-06", periods=10, freq="7D"))
    price, changed = pr._simulate(np.full(10, 50.0), dates, 0.25, "weekly")
    margin = 1 - 50.0 / price[1:]
    assert np.allclose(margin, 0.25) and changed.sum() == 0


def test_seasonal_index_normalised(data):
    si = mk.seasonal_index(data[2])
    assert np.allclose(si.mean(axis=1), 1.0)


def test_budget_totals_add_up(data):
    raw, rows, panel, an, basket = data
    bud = bg.build_budget(panel, rows, basket)
    assert np.isclose(bud.gross_margin.sum(), bud.revenue.sum() - bud.cogs.sum())
    gm_pct = bud.gross_margin.sum() / bud.revenue.sum()
    assert basket.target_margin.min() <= gm_pct <= basket.target_margin.max()
    scen = bg.scenario_table(bud)
    assert scen.set_index("scenario").gross_margin["volume_down_5pct"] == pytest.approx(
        0.95 * scen.gross_margin.iloc[0]
    )


def test_forecast_backtest_has_no_lookahead(data):
    panel = data[2]
    bt = fc.monthly_backtest(panel, (3,), shrink=0.5)
    assert pd.PeriodIndex(bt.target_month, freq="M").min() > pd.Period("2018-12", "M")  # SI years are 2017-2018 only


def test_custom_scenario_matches_named_scenarios(data):
    raw, rows, panel, an, basket = data
    bud = bg.build_budget(panel, rows, basket)
    named = bg.scenario_table(bud).set_index("scenario").gross_margin
    assert bg.custom_scenario(bud).gross_margin.sum() == pytest.approx(named["base"])
    assert bg.custom_scenario(bud, fx_shock=0.05).gross_margin.sum() == pytest.approx(named["cad_weaker_5pct"])
    assert bg.custom_scenario(bud, supply_shock=0.40).gross_margin.sum() == pytest.approx(named["lettuce_tomato_shock"])
    assert bg.custom_scenario(bud, handling_up=0.10).gross_margin.sum() == pytest.approx(named["handling_up_10pct"])
    assert bg.custom_scenario(bud, volume_change=-0.05).gross_margin.sum() == pytest.approx(named["volume_down_5pct"])

"""Short-horizon cost forecasting (1-4 weeks ahead) with honest backtests.

Models are deliberately simple and explainable: naive, 4-week moving average, seasonal-adjusted naive
(last price x seasonal index ratio), and simple exponential smoothing on log prices. Seasonal indices
used in a backtest are always estimated from years BEFORE the test window (no look-ahead).
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from .market import seasonal_index

MODELS = ["naive", "ma4", "seasonal_naive", "ses", "blend"]


def _ses(y: np.ndarray, alpha: float = 0.5) -> float:
    lvl = np.log(y[0])
    for v in np.log(y[1:]):
        lvl = alpha * v + (1 - alpha) * lvl
    return float(np.exp(lvl))


def predict(hist: pd.DataFrame, target_date: pd.Timestamp, si: pd.Series | None) -> dict:
    """hist: one item's rows (date, price_cad) up to the forecast origin, sorted."""
    y = hist.price_cad.to_numpy()
    last, origin = y[-1], hist.date.iloc[-1]
    f = {"naive": last, "ma4": float(np.mean(y[-4:])), "ses": _ses(y[-12:])}
    if si is not None and not si.isna().any():
        f["seasonal_naive"] = last * si[target_date.month] / si[origin.month]
    else:
        f["seasonal_naive"] = last
    f["blend"] = float(np.exp(np.mean(np.log([f["seasonal_naive"], f["ses"]]))))
    return f


def backtest(panel: pd.DataFrame, windows=None, horizons=(1, 2, 4)) -> pd.DataFrame:
    """Rolling-origin backtest. windows: list of (test_start, test_end, si_years)."""
    if windows is None:
        windows = [("2019-01-01", "2021-04-30", (2017, 2018)), ("2023-01-01", "2024-01-31", (2017, 2018, 2019, 2020))]
    out = []
    for start, end, years in windows:
        si_all = seasonal_index(panel, years)
        for item, s in panel.sort_values("date").groupby("item_id"):
            s = s.reset_index(drop=True)
            si = si_all.loc[item] if item in si_all.index else None
            test_idx = s.index[(s.date >= start) & (s.date <= end)]
            for i in test_idx:
                for h in horizons:
                    o = i - h
                    if o < 8:
                        continue
                    # never forecast across a gap: origin and target must be <= 7*h+7 days apart
                    if (s.date[i] - s.date[o]).days > 7 * h + 7:
                        continue
                    hist = s.iloc[: o + 1]
                    # Restart model state after a missing-data period.
                    starts = hist.date.diff().dt.days.gt(14)
                    if starts.any():
                        hist = hist.loc[starts[starts].index[-1]:]
                    f = predict(hist, s.date[i], si)
                    for mname, val in f.items():
                        out.append((item, start[:4], h, s.date[i], mname, val, s.price_cad[i]))
    return pd.DataFrame(out, columns=["item_id", "window", "h", "date", "model", "fcst", "actual"])


def score(bt: pd.DataFrame) -> pd.DataFrame:
    g = bt.assign(ae=(bt.fcst - bt.actual).abs(), e=bt.fcst - bt.actual)
    s = (
        g.groupby(["item_id", "h", "model"])
        .agg(ae=("ae", "sum"), e=("e", "sum"), a=("actual", "sum"), n=("ae", "size"))
        .reset_index()
    )
    s["wape"] = s.ae / s.a
    s["bias"] = s.e / s.a
    return s


def best_models(sc: pd.DataFrame, h: int = 1) -> pd.DataFrame:
    s = sc[sc.h == h]
    naive = s[s.model == "naive"].set_index("item_id").wape.rename("naive_wape")
    best = s.sort_values("wape").groupby("item_id").head(1).set_index("item_id")[["model", "wape", "bias"]]
    best = best.join(naive)
    best["improvement_vs_naive"] = 1 - best.wape / best.naive_wape
    return best.reset_index()


def monthly_backtest(
    panel: pd.DataFrame,
    horizons=(1, 3, 6),
    si_years=(2017, 2018),
    origin_range=("2019-01", "2020-12"),
    shrink: float = 1.0,
) -> pd.DataFrame:
    """Budget-horizon test on monthly averages: forecast month t+h from month t.
    flat = carry month t forward; seasonal = month t x SI(t+h)/SI(t), SI estimated from 2017-2018 only,
    tested on origins in 2019-2020 (the longest continuous stretch after the SI years)."""
    si = 1 + shrink * (seasonal_index(panel, si_years) - 1)
    p = panel.assign(m=panel.date.dt.to_period("M")).groupby(["item_id", "m"]).price_cad.mean().reset_index()
    out = []
    for item, s in p.groupby("item_id"):
        if item not in si.index or si.loc[item].isna().any():
            continue
        s = s.set_index("m").price_cad
        for o in s.index:
            if not (origin_range[0] <= str(o) <= origin_range[1]):
                continue
            for h in horizons:
                t = o + h
                if t not in s.index:
                    continue
                flat = s[o]
                seas = s[o] * si.loc[item][t.month] / si.loc[item][o.month]
                out += [(item, h, str(t), "flat", flat, s[t]), (item, h, str(t), "seasonal", seas, s[t])]
    return pd.DataFrame(out, columns=["item_id", "h_months", "target_month", "model", "fcst", "actual"])


def select_seasonal_items(panel: pd.DataFrame, h: int = 3, shrink: float = 1.0) -> list[str]:
    """Items where the seasonal model beat the flat forecast in the 2019-2020 validation window."""
    mb = monthly_backtest(panel, horizons=(h,), shrink=shrink)
    w = (
        mb.assign(ae=(mb.fcst - mb.actual).abs())
        .groupby(["item_id", "model"])
        .apply(lambda g: g.ae.sum() / g.actual.sum())
        .unstack()
    )
    return sorted(w.index[w.seasonal < w.flat])

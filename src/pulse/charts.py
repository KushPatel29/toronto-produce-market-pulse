"""Static charts for the README and report page (matplotlib). Palette: validated reference
categorical slots (blue, orange, aqua) and a blue<->red diverging pair with a gray midpoint."""

from __future__ import annotations
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
import numpy as np
import pandas as pd

BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
INK, INK2, GRID, SURF, MID = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb", "#f0efec"
DIV = LinearSegmentedColormap.from_list("div", [BLUE, MID, RED])
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK2,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": SURF,
        "axes.facecolor": SURF,
        "savefig.facecolor": SURF,
        "axes.titleweight": "bold",
        "axes.titlesize": 12,
        "axes.titlecolor": INK,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
    }
)


def basket_index(idx: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(9, 3.6))
    s = idx.set_index("month_start")["index"]
    full = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="MS"))
    ax.plot(full.index, full.values, color=BLUE, lw=2)
    ax.axhline(100, color=INK2, lw=0.8, ls="--")
    ax.axvspan(pd.Timestamp("2021-05-01"), pd.Timestamp("2022-10-31"), color=MID, zorder=0)
    ax.text(
        pd.Timestamp("2021-12-15"),
        ax.get_ylim()[0] + 3,
        "No source reports\nApr 2021 - Nov 2022",
        ha="center",
        color=INK2,
        fontsize=8,
    )
    pk = s["2022-11-01":"2023-03-01"]
    ax.annotate(
        "Lettuce crisis\n(INSV, Salinas)",
        xy=(pk.idxmax(), pk.max()),
        xytext=(pd.Timestamp("2023-06-01"), pk.max() - 4),
        arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8),
        color=INK,
        fontsize=8,
    )
    ax.set_title("Toronto wholesale produce basket, monthly index (2019 = 100, 30 items, CAD)", loc="left")
    ax.set_ylabel("Index")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def price_change(chg: pd.DataFrame, path):
    d = chg.sort_values("pct_chg")
    fig, ax = plt.subplots(figsize=(7.5, 7))
    cols = [RED if v > 0 else BLUE for v in d.pct_chg]
    ax.barh(d.display_name, d.pct_chg * 100, color=cols, height=0.7)
    for y, v in enumerate(d.pct_chg * 100):
        ax.text(
            v + (1 if v >= 0 else -1),
            y,
            f"{v:+.0f}%",
            va="center",
            ha="left" if v >= 0 else "right",
            fontsize=8,
            color=INK,
        )
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_title("Average CAD price per case, 2023 vs 2019", loc="left")
    ax.set_xlabel("% change")
    ax.grid(axis="y", visible=False)
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo - 6, hi + 8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def seasonality(si: pd.DataFrame, names: dict, path):
    d = si.copy()
    d.index = [names.get(i, i) for i in d.index]
    d = d.loc[(d.max(axis=1) - d.min(axis=1)).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(8.5, 8))
    im = ax.imshow(d.values, cmap=DIV, norm=TwoSlopeNorm(vcenter=1, vmin=0.6, vmax=1.5), aspect="auto")
    ax.set_xticks(range(12), ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_yticks(range(len(d)), d.index)
    ax.grid(False)
    for (i, j), v in np.ndenumerate(d.values):
        if abs(v - 1) >= 0.2:
            ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=7, color=INK)
    cb = fig.colorbar(im, ax=ax, shrink=0.6)
    cb.set_label("Price vs item's annual average")
    ax.set_title("When produce is cheap or dear (seasonal index, 2017-2020)", loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def policies(summ: pd.DataFrame, path):
    p = (
        summ.groupby("policy")[["breach_rate", "changes_per_year", "avg_margin"]]
        .mean()
        .loc[["monthly", "band", "weekly"]]
    )
    labels = {"monthly": "Monthly price list", "band": "Band rule (+/-5 pts)", "weekly": "Weekly repricing"}
    cols = [BLUE, ORANGE, AQUA]
    fig, axs = plt.subplots(1, 3, figsize=(10, 3.4))
    for ax, (col, ttl, fmt) in zip(
        axs,
        [
            ("breach_rate", "Weeks >10 pts below target margin", "{:.0%}"),
            ("changes_per_year", "Customer price changes per year", "{:.0f}"),
            ("avg_margin", "Average realised margin", "{:.1%}"),
        ],
        strict=True,
    ):
        ax.bar([labels[i] for i in p.index], p[col], color=cols, width=0.6)
        for x, v in enumerate(p[col]):
            ax.text(x, v, fmt.format(v), ha="center", va="bottom", fontsize=9, color=INK)
        ax.set_title(ttl, loc="left", fontsize=10)
        ax.tick_params(axis="x", labelsize=8, rotation=12)
        ax.grid(axis="x", visible=False)
        ax.set_yticks([])
    fig.suptitle(
        "Pricing policies replayed on real weekly Toronto costs (30 items, 2017-2024)",
        x=0.01,
        ha="left",
        fontweight="bold",
        color=INK,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def forecast_test(mt: pd.DataFrame, path):
    d = mt.pivot(index="h_months", columns="model", values="wape")
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    x = np.arange(len(d))
    w = 0.36
    ax.bar(x - w / 2 - 0.01, d["flat"] * 100, w, color=BLUE, label="Flat (carry current price)")
    ax.bar(x + w / 2 + 0.01, d["seasonal"] * 100, w, color=ORANGE, label="Half-strength seasonal")
    for i, h in enumerate(d.index):
        ax.text(i - w / 2, d.loc[h, "flat"] * 100, f"{d.loc[h, 'flat']:.1%}", ha="center", va="bottom", fontsize=8)
        ax.text(
            i + w / 2, d.loc[h, "seasonal"] * 100, f"{d.loc[h, 'seasonal']:.1%}", ha="center", va="bottom", fontsize=8
        )
    ax.set_xticks(x, [f"{h} month{'s' if h > 1 else ''} ahead" for h in d.index])
    ax.set_ylabel("WAPE (%)")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.grid(axis="x", visible=False)
    ax.set_title("Budget-horizon forecast error, unseen 2023 test", loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def lettuce_crisis(panel: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(9, 3.4))
    for item, col, nm in [("let_rom", BLUE, "Romaine"), ("let_ice", ORANGE, "Iceberg")]:
        s = panel[(panel.item_id == item) & (panel.date >= "2022-11-01")].set_index("date").price_cad
        base = panel[(panel.item_id == item) & (panel.date.dt.year == 2019)].price_cad.mean()
        ax.plot(s.index, s.values, color=col, lw=2, marker="o", ms=3, label=nm)
        ax.axhline(base, color=col, lw=0.8, ls=":")
        ax.text(
            pd.Timestamp("2022-11-03"),
            base + (1 if nm == "Iceberg" else -1),
            f"{nm} 2019 average ${base:.0f}",
            va="bottom" if nm == "Iceberg" else "top",
            ha="left",
            fontsize=8,
            color=INK2,
        )
        ax.annotate(
            f"{nm} peak ${s.max():.0f}",
            xy=(s.idxmax(), s.max()),
            xytext=(10, 6 if nm == "Iceberg" else -14),
            textcoords="offset points",
            fontsize=8,
            color=INK,
        )
    ax.set_ylabel("CAD per case")
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("Late-2022 lettuce crisis in Toronto wholesale prices", loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def tornado(sens: pd.DataFrame, path):
    d = sens.sort_values("swing")
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.barh(d.driver, d.upside / 1000, color=BLUE, height=0.6, label="Upside")
    ax.barh(d.driver, d.downside / 1000, color=ORANGE, height=0.6, label="Downside")
    for y, (u, dn) in enumerate(zip(d.upside, d.downside, strict=True)):
        ax.text(u / 1000 + 1, y, f"+${u / 1000:.0f}k", va="center", fontsize=8)
        ax.text(dn / 1000 - 1, y, f"-${-dn / 1000:.0f}k", va="center", ha="right", fontsize=8)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_xlabel("Change in annual gross margin ($k CAD)")
    ax.grid(axis="y", visible=False)
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo - 15, hi + 15)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title("FY budget sensitivity (one driver at a time)", loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)

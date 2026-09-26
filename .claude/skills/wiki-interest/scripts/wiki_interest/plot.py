"""PNG charts via matplotlib, readable by non-technical users.

Plain numbers on the y axis (1 200, not 1.2×10³), month names on the x axis with a
tick step that depends on the period length, labels in the user's language.
"""

import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display needed when run by an agent

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.dates import MonthLocator
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

from .i18n import lang_name, month_label, t

LOG_SCALE_RATIO = 15  # switch to log axis only when languages differ this much in volume


def _plain(value: float, _pos=None) -> str:
    return f"{value:,.0f}".replace(",", " ")


def _month_step(n_months: int) -> int:
    if n_months <= 13:
        return 1
    if n_months <= 24:
        return 2
    if n_months <= 48:
        return 3
    return 6


def plot_trends(results: dict, output: str | None = None, lang: str = "en") -> bytes | None:
    """Monthly pageviews per language.

    Args:
        results: dict of {lang: analysis_result} from analyze(); uses the "monthly" series
        output: file path to save PNG, or None to return bytes
        lang: language of the labels (e.g. "uk", "en")
    """
    fig, ax = plt.subplots(figsize=(11, 4.2))
    medians = []
    first = last = None
    for code, data in sorted(results.items()):
        monthly = data.get("monthly") or {}
        if not monthly:
            continue
        months = pd.to_datetime(list(monthly.keys()), format="%Y-%m")
        ax.plot(months, list(monthly.values()), marker="o", markersize=3, linewidth=2,
                label=lang_name(code, lang))
        medians.append(max(pd.Series(list(monthly.values())).median(), 1))
        first = months.min() if first is None else min(first, months.min())
        last = months.max() if last is None else max(last, months.max())

    if not medians:
        ax.text(0.5, 0.5, t("no_data", lang), ha="center", va="center", transform=ax.transAxes)
    else:
        if max(medians) / min(medians) > LOG_SCALE_RATIO:
            ax.set_yscale("log")
            ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
            ax.yaxis.set_minor_formatter(NullFormatter())
        else:
            ax.set_ylim(bottom=0)
        ax.yaxis.set_major_formatter(FuncFormatter(_plain))
        # Ticks start at the first data month (not January) and never fall outside the data.
        n_months = (last.year - first.year) * 12 + last.month - first.month + 1
        step = _month_step(n_months)
        ax.xaxis.set_major_locator(MonthLocator(bymonth=sorted({
            (first.month - 1 + k * step) % 12 + 1 for k in range(12)
        })))
        pad = pd.Timedelta(days=12)
        ax.set_xlim(first - pad, last + pad)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _p: month_label(x, lang)))
        ax.legend(frameon=False)

    ax.set_ylabel(t("views_per_month", lang))
    ax.grid(True, alpha=0.3)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.autofmt_xdate()

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        return None
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()

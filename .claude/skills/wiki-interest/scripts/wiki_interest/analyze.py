"""Trend detection, normalization, anomaly marking, and confidence scoring.

Monthly series are used for trends. Daily series are used for anomaly detection only.
All statistics are computed per language independently.
"""

import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy import stats


@dataclass
class Anomaly:
    month: str  
    factor: float
    views: int


@dataclass
class TrendMetrics:
    yoy_change_pct: float | None
    trend_pct_per_year: float | None  
    ci95_lower: float | None
    ci95_upper: float | None
    mann_kendall_p: float | None
    mann_kendall_test: str


def month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def monthly_from_daily(daily: dict[date, int]) -> pd.Series:
    """Aggregate daily pageviews into months. Returns a Series indexed by month (YYYY-MM)."""
    if not daily:
        return pd.Series(dtype=int)
    days = pd.to_datetime(list(daily.keys()))
    views = list(daily.values())
    df = pd.DataFrame({"views": views}, index=days).sort_index()
    monthly = df.resample("MS").sum()["views"]
    return monthly.rename(lambda d: d.strftime("%Y-%m"))


def _mk_test(s: pd.Series) -> tuple[float, str]:
    """p-value and test name for trend in a monthly series.

    Seasonal Mann-Kendall (compares each calendar month with itself across years) needs
    at least two full years; with 12-23 months the plain Mann-Kendall test is used.
    """
    if len(s) < 12:
        return 1.0, "insufficient_data"
    values = s.values.astype(float)
    if len(s) >= 24:
        return float(mk.seasonal_test(values, period=12).p), "seasonal_mann_kendall"
    return float(mk.original_test(values).p), "mann_kendall"


def _trend_and_ci(
    s: pd.Series, seed: int = 42, n_boot: int = 1000
) -> tuple[float | None, float | None, float | None]:
    """OLS slope on log(views) per month, 95% CI via moving-block bootstrap of residuals.

    Residual blocks keep the autocorrelation (and seasonality) of the series, so the
    CI is wider than a naive i.i.d. bootstrap would give.
    """
    positive = s[s > 0]
    n = len(positive)
    if n < 3:
        return None, None, None
    x = np.arange(n)
    y = np.log(positive.values.astype(float))
    fit = stats.linregress(x, y)
    fitted = fit.intercept + fit.slope * x
    resid = y - fitted
    block = min(n, max(3, n // 4))
    rng = np.random.default_rng(seed)
    n_blocks = -(-n // block)
    slopes = np.empty(n_boot)
    for i in range(n_boot):
        starts = rng.integers(0, n - block + 1, size=n_blocks)
        boot_resid = np.concatenate([resid[j : j + block] for j in starts])[:n]
        slopes[i] = np.polyfit(x, fitted + boot_resid, 1)[0]
    ci_lo, ci_hi = np.percentile(slopes, [2.5, 97.5])
    return float(fit.slope), float(ci_lo), float(ci_hi)


def trend_metrics(s: pd.Series) -> TrendMetrics:
    """Trend and p-value for a monthly series."""
    if len(s) < 2:
        return TrendMetrics(None, None, None, None, None, "insufficient")
    yoy_change = None
    if len(s) >= 24:
        yoy_sum_recent = s.iloc[-12:].sum()
        yoy_sum_prev = s.iloc[-24:-12].sum()
        if yoy_sum_prev > 0:
            yoy_change = (yoy_sum_recent / yoy_sum_prev - 1) * 100
    slope, ci_lo, ci_hi = _trend_and_ci(s)
    p, test_name = _mk_test(s)
    trend_pct = None
    if slope is not None:
        trend_pct = (np.exp(slope * 12) - 1) * 100
    ci_pct_lo = (np.exp(ci_lo * 12) - 1) * 100 if ci_lo is not None else None
    ci_pct_hi = (np.exp(ci_hi * 12) - 1) * 100 if ci_hi is not None else None
    return TrendMetrics(
        yoy_change_pct=yoy_change,
        trend_pct_per_year=trend_pct,
        ci95_lower=ci_pct_lo,
        ci95_upper=ci_pct_hi,
        mann_kendall_p=p,
        mann_kendall_test=test_name,
    )


def detect_anomalies(daily: dict[date, int]) -> list[Anomaly]:
    """Daily spikes: rolling median ± MAD, threshold z > 5 or factor > 3."""
    if len(daily) < 30:
        return []
    s = pd.Series(daily).sort_index()
    rolling_med = s.rolling(window=31, center=True, min_periods=15).median()
    diff = (s - rolling_med).abs()
    mad = diff.rolling(window=31, center=True, min_periods=15).median() * 1.4826
    with np.errstate(divide="ignore", invalid="ignore"):
        z_score = np.abs(s - rolling_med) / (mad + 1e-9)
    outliers = (z_score > 5) | ((rolling_med > 0) & (s > rolling_med * 3))
    anomalies = []
    for d in s[outliers].index:
        if d in daily and rolling_med[d] > 0:
            factor = daily[d] / rolling_med[d]
            anomalies.append(Anomaly(month_key(d), factor, daily[d]))
    return anomalies[:10]


def _pct_vs(value: float, mean: float) -> float | None:
    return round((value / mean - 1) * 100, 1) if mean > 0 else None


def seasonality(series: pd.Series) -> dict | None:
    """Seasonal pattern of a monthly series, or None with fewer than 24 months.

    Seasons are complete 12-month windows counted back from the last month, so the last
    season is always the last 12 months; an incomplete leading remainder is dropped.
    Each season is compared with its own mean, so a long-term trend does not hide the pattern.
    `peak_above_neighbours` is False when the peak is not higher than the adjacent months
    (e.g. the first month of a season in a falling series): then the "peak" is just the trend.
    """
    n_seasons = len(series) // 12
    if n_seasons < 2:
        return None
    s = series.iloc[len(series) - n_seasons * 12:]

    by_month: dict[str, dict[str, int]] = {}
    for key, v in s.items():
        year, month = key.split("-")
        by_month.setdefault(month, {})[year] = int(v)

    seasons = []
    for i in range(n_seasons):
        w = s.iloc[i * 12:(i + 1) * 12]
        mean = float(w.mean())
        peak, low = w.idxmax(), w.idxmin()
        pos = series.index.get_loc(peak)
        if 0 < pos < len(series) - 1:
            above = bool(series.iloc[pos] > series.iloc[pos - 1] and series.iloc[pos] > series.iloc[pos + 1])
        else:
            above = None 
        seasons.append({
            "start": w.index[0],
            "end": w.index[-1],
            "mean": round(mean, 1),
            "peak_month": peak,
            "peak_views": int(w[peak]),
            "peak_vs_mean_pct": _pct_vs(float(w[peak]), mean),
            "peak_above_neighbours": above,
            "low_month": low,
            "low_views": int(w[low]),
            "low_vs_mean_pct": _pct_vs(float(w[low]), mean),
            "months_above_mean": [k for k, v in w.items() if v > mean],
        })

    peak_months = Counter(x["peak_month"][5:] for x in seasons)
    low_months = Counter(x["low_month"][5:] for x in seasons)
    return {
        "by_month": dict(sorted(by_month.items())),
        "seasons": seasons,
        "peak_calendar_month": peak_months.most_common(1)[0][0],
        "peak_repeats": len(peak_months) == 1,
        "low_calendar_month": low_months.most_common(1)[0][0],
        "low_repeats": len(low_months) == 1,
    }


def baseline(daily: dict[date, int]) -> dict:
    """YoY and trend of the whole language edition, to tell topic interest from site-wide drift."""
    if not daily:
        return {"yoy_change_pct": None, "trend_pct_per_year": None}
    series = monthly_from_daily(daily)
    m = trend_metrics(series)
    return {
        "yoy_change_pct": round(m.yoy_change_pct, 1) if m.yoy_change_pct is not None else None,
        "trend_pct_per_year": round(m.trend_pct_per_year, 1) if m.trend_pct_per_year is not None else None,
    }


def analyze(daily: dict[date, int]) -> dict:
    """Analyze pageviews for one language. Returns dict suitable for JSON output."""
    series = monthly_from_daily(daily)
    yoy = trend_metrics(series)
    anomalies = detect_anomalies(daily)
    caveats = []
    if len(series) < 24:
        caveats.append("short_history")
    med = statistics.median(series) if series.size > 0 else 0
    if med < 300:
        caveats.append("low_volume")
    if series.size > 1 and series.std() / (series.mean() + 1e-9) > 0.5:
        caveats.append("high_seasonality")
    if min(daily.keys()) < date(2020, 4, 1):
        caveats.append("bot_traffic_before_2020")
    score = 0
    if med >= 1000:
        score += 1
    if len(series) >= 24:
        score += 1
    if (
        yoy.mann_kendall_p is not None
        and yoy.mann_kendall_p < 0.05
        and yoy.ci95_lower is not None
        and yoy.ci95_upper is not None
        and (yoy.ci95_lower > 0 or yoy.ci95_upper < 0)
    ):
        score += 1
    confidence = {3: "high", 2: "medium"}.get(score, "low")
    return {
        "yoy_change_pct": round(yoy.yoy_change_pct, 1) if yoy.yoy_change_pct is not None else None,
        "trend_pct_per_year": round(yoy.trend_pct_per_year, 1)
        if yoy.trend_pct_per_year is not None
        else None,
        "ci95": [round(yoy.ci95_lower, 1), round(yoy.ci95_upper, 1)]
        if (yoy.ci95_lower is not None and yoy.ci95_upper is not None)
        else None,
        "mann_kendall_p": round(float(yoy.mann_kendall_p), 4)
        if yoy.mann_kendall_p is not None
        else None,
        "mann_kendall_test": yoy.mann_kendall_test,
        "anomalies": [
            {"month": a.month, "factor": round(float(a.factor), 1), "views": int(a.views)}
            for a in anomalies
        ],
        "confidence": confidence,
        "caveats": caveats,
        "seasonality": seasonality(series),
        "monthly": {month: int(v) for month, v in series.items()},
    }

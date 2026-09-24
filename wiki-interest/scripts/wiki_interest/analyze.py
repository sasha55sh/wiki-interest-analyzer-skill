"""Trend detection, normalization, anomaly marking, and confidence scoring.

Monthly series are used for trends. Daily series are used for anomaly detection only.
All statistics are computed per language independently.
"""

import statistics
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from scipy import stats

try:
    from pymannkendall import seasonal_mk
except ImportError:
    seasonal_mk = None


@dataclass
class Anomaly:
    month: str  
    factor: float
    views: int


@dataclass
class TrendMetrics:
    yoy_change_pct: float
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
    """p-value and test name for trend in a monthly series."""
    if len(s) < 12:
        return 1.0, "insufficient_data"
    if seasonal_mk is None:
        _, p = stats.spearmanr(range(len(s)), s)
        return p, "spearman"
    try:
        return seasonal_mk(s.values, alpha=0.05).p, "seasonal_mann_kendall"
    except (ValueError, RuntimeError):
        _, p = stats.spearmanr(range(len(s)), s)
        return p, "spearman_fallback"


def _trend_and_ci(s: pd.Series, seed: int = 42) -> tuple[float | None, float | None, float | None]:
    """Theil-Sen slope on log(views), ± 95% CI via block bootstrap."""
    positive = s[s > 0]
    if len(positive) < 3:
        return None, None, None
    x = np.arange(len(positive))
    slope, _intercept, _, _, _ = stats.linregress(x, np.log(positive.values))
    block_size = max(3, len(positive) // 4)
    np.random.seed(seed)
    slopes = []
    for _ in range(1000):
        start_idx = np.random.randint(0, len(positive) - block_size + 1)
        indices = np.arange(start_idx, min(start_idx + block_size, len(positive)))
        if len(indices) > 1:
            try:
                s_boot = stats.linregress(np.arange(len(indices)), np.log(positive.values[indices])).slope
                slopes.append(s_boot)
            except (ValueError, RuntimeWarning):
                pass
    if not slopes:
        return slope, None, None
    slopes = np.array(slopes)
    ci = np.percentile(slopes, [2.5, 97.5])
    return slope, ci[0], ci[1]


def trend_metrics(s: pd.Series) -> TrendMetrics:
    """Trend and p-value for a monthly series."""
    if len(s) < 2:
        return TrendMetrics(0.0, None, None, None, None, "insufficient")
    yoy_change = 0.0
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
        yoy.mann_kendall_p
        and yoy.mann_kendall_p < 0.05
        and yoy.ci95_lower is not None
        and yoy.ci95_upper is not None
        and (yoy.ci95_lower > 0 or yoy.ci95_upper < 0)
    ):
        score += 1
    confidence = ("low" if score < 2 else "medium" if score < 4 else "high")
    return {
        "yoy_change_pct": round(yoy.yoy_change_pct, 1),
        "trend_pct_per_year": round(yoy.trend_pct_per_year, 1) if yoy.trend_pct_per_year else None,
        "ci95": [round(yoy.ci95_lower, 1), round(yoy.ci95_upper, 1)]
        if (yoy.ci95_lower is not None and yoy.ci95_upper is not None)
        else None,
        "mann_kendall_p": round(yoy.mann_kendall_p, 4) if yoy.mann_kendall_p else None,
        "mann_kendall_test": yoy.mann_kendall_test,
        "anomalies": [{"month": a.month, "factor": round(a.factor, 1), "views": a.views} for a in anomalies],
        "confidence": confidence,
        "caveats": caveats,
    }

"""Test analyze: metrics, confidence, caveats."""

import json
from datetime import date

import pandas as pd
from wiki_interest.analyze import (
    analyze,
    baseline,
    detect_anomalies,
    monthly_from_daily,
    seasonality,
)


def _monthly(start_year: int, start_month: int, values: list[float]) -> pd.Series:
    keys = []
    y, m = start_year, start_month
    for _ in values:
        keys.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return pd.Series(values, index=keys)


def _season(nov: float = 250, jun: float = 50, other: float = 100) -> list[float]:
    """Sep..Aug with a November peak and a June low."""
    months = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8]
    return [nov if m == 11 else jun if m == 6 else other for m in months]


def test_seasonality_repeating_peak_vs_season_mean():
    s = _monthly(2023, 9, _season() * 3)
    r = seasonality(s)
    assert len(r["seasons"]) == 3
    assert r["peak_calendar_month"] == "11" and r["peak_repeats"]
    assert r["low_calendar_month"] == "06" and r["low_repeats"]
    first = r["seasons"][0]
    assert (first["start"], first["end"]) == ("2023-09", "2024-08")
    mean = (10 * 100 + 250 + 50) / 12
    assert first["mean"] == round(mean, 1)
    assert first["peak_month"] == "2023-11"
    assert first["peak_vs_mean_pct"] == round((250 / mean - 1) * 100, 1)  # +130.8%
    assert first["low_vs_mean_pct"] == round((50 / mean - 1) * 100, 1)  # -53.8%
    assert first["peak_above_neighbours"] is True
    assert first["months_above_mean"] == ["2023-11"]
    assert r["by_month"]["11"] == {"2023": 250, "2024": 250, "2025": 250}


def test_seasonality_each_season_uses_its_own_mean():
    """Declining level: the peak is still measured against its own season."""
    s = _monthly(2023, 9, _season() + [v / 2 for v in _season()] + [v / 4 for v in _season()])
    pcts = {x["peak_vs_mean_pct"] for x in seasonality(s)["seasons"]}
    assert len(pcts) == 1  # same shape, same relative peak, despite the lower level


def test_seasonality_peak_moves_between_months():
    oct_peak = [100, 250, 100, 100, 100, 100, 100, 100, 100, 50, 100, 100]
    r = seasonality(_monthly(2023, 9, _season() + oct_peak))
    assert not r["peak_repeats"]
    assert [x["peak_month"] for x in r["seasons"]] == ["2023-11", "2024-10"]


def test_seasonality_trend_peak_is_flagged():
    """Steady decline, no seasonality: each season's "peak" is its first month, not a real high."""
    s = _monthly(2023, 1, [1000 * 0.97**i for i in range(36)])
    seasons = seasonality(s)["seasons"]
    assert all(x["peak_month"].endswith("-01") for x in seasons)
    assert seasons[0]["peak_above_neighbours"] is None  # first month of the data: can't tell
    assert all(x["peak_above_neighbours"] is False for x in seasons[1:])


def test_seasonality_needs_two_full_seasons():
    assert seasonality(_monthly(2024, 1, [100] * 23)) is None
    r = seasonality(_monthly(2023, 7, [100] * 30))  # 30 months -> last 24 = 2 seasons
    assert [x["start"] for x in r["seasons"]] == ["2024-01", "2025-01"]


def test_analyze_includes_seasonality():
    daily = {date(2023 + (m - 1) // 12, (m - 1) % 12 + 1, 1): 100 * m for m in range(1, 25)}
    result = analyze(daily)
    assert result["seasonality"] is not None
    json.dumps(result)
    assert analyze({date(2025, 1, d): 10 for d in range(1, 29)})["seasonality"] is None


def test_monthly_from_daily():
    """Daily views are aggregated into months."""
    daily = {
        date(2025, 1, 1): 100,
        date(2025, 1, 15): 150,
        date(2025, 2, 1): 80,
    }
    monthly = monthly_from_daily(daily)
    assert "2025-01" in monthly.index
    assert monthly["2025-01"] == 250
    assert monthly["2025-02"] == 80


def test_trend_metrics_short_history():
    """Short history has insufficient data."""
    daily = {date(2025, 1, i): 100 for i in range(1, 11)}
    result = analyze(daily)
    assert result["confidence"] == "low"
    assert "short_history" in result["caveats"]


def test_trend_metrics_small_volume():
    """Small volume triggers low confidence."""
    daily = {date(2024, i, 1): 50 for i in range(1, 13)}
    daily.update({date(2025, i, 1): 55 for i in range(1, 13)})
    result = analyze(daily)
    assert "low_volume" in result["caveats"]


def test_trend_metrics_yoy_calculation():
    """YoY change is computed correctly."""
    daily = {}
    for m in range(1, 13):
        for d in range(1, 29):
            daily[date(2024, m, d)] = 100
    for m in range(1, 13):
        for d in range(1, 29):
            daily[date(2025, m, d)] = 120
    result = analyze(daily)
    assert 15 < result["yoy_change_pct"] < 25


def test_anomaly_detection():
    """Spikes above rolling median are detected."""
    daily = {date(2025, 1, i): 100 for i in range(1, 32)}
    daily[date(2025, 1, 15)] = 400 
    anomalies = detect_anomalies(daily)
    assert any(a.month == "2025-01" for a in anomalies)


def test_analyze_returns_json_compatible():
    """analyze() returns a dict with JSON-safe types."""
    daily = {date(2025, 1, i): 100 + i for i in range(1, 32)}
    daily.update({date(2025, 2, i): 120 + i for i in range(1, 29)})
    result = analyze(daily)
    json.dumps(result)
    assert result["yoy_change_pct"] is None  # < 24 months: YoY is not computable
    assert isinstance(result["confidence"], str)
    assert isinstance(result["caveats"], list)
    assert result["confidence"] in ["low", "medium", "high"]
    assert result["monthly"] == {"2025-01": sum(range(101, 132)), "2025-02": sum(range(121, 149))}


def test_confidence_high_is_reachable():
    """Big, long, steadily growing series gets all three points -> high."""
    daily = {}
    for m in range(36):
        y, mo = 2022 + m // 12, m % 12 + 1
        for d in range(1, 29):
            daily[date(y, mo, d)] = int(5000 * 1.02**m)
    result = analyze(daily)
    assert result["confidence"] == "high"
    assert result["ci95"][0] > 0
    assert 20 < result["trend_pct_per_year"] < 30  # 1.02**12 - 1 = 26.8%


def test_flat_noisy_series_is_not_significant():
    """No trend -> CI straddles zero, confidence at most medium."""
    daily = {}
    for m in range(24):
        y, mo = 2023 + m // 12, m % 12 + 1
        for d in range(1, 29):
            daily[date(y, mo, d)] = 3000 + (400 if m % 2 else -400)
    result = analyze(daily)
    assert result["ci95"][0] < 0 < result["ci95"][1]
    assert result["confidence"] == "medium"


def test_baseline():
    daily = {date(2025, 1, d): 100 for d in range(1, 29)}
    assert baseline(daily)["yoy_change_pct"] is None
    assert baseline({}) == {"yoy_change_pct": None, "trend_pct_per_year": None}


def test_analyze_bot_traffic_caveat():
    """Data from before 2020-04 gets bot_traffic caveat."""
    daily = {date(2019, 6, i): 100 for i in range(1, 31)}
    daily.update({date(2019, 7, i): 110 for i in range(1, 32)})
    result = analyze(daily)
    assert "bot_traffic_before_2020" in result["caveats"]

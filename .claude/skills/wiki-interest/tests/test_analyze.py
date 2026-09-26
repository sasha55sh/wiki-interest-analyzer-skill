"""Test analyze: metrics, confidence, caveats."""

import json
from datetime import date

from wiki_interest.analyze import (
    analyze,
    baseline,
    detect_anomalies,
    monthly_from_daily,
)


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

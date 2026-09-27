"""Confidence scoring and caveats on synthetic series with known properties.

Rules (references/methodology.md): one point each for median >= 1000 views/month,
>= 24 months of data, and a significant trend whose 95% CI excludes zero.
0-1 points = low, 2 = medium, 3 = high.
"""

from datetime import date

from wiki_interest.analyze import analyze


def _daily(monthly_views: list[int], start: tuple[int, int] = (2023, 1)) -> dict[date, int]:
    """One value per month spread evenly over 28 days."""
    out = {}
    y, m = start
    for views in monthly_views:
        for d in range(1, 29):
            out[date(y, m, d)] = views // 28
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def test_low_volume_gives_low_confidence():
    """112 views/month: below the 300 threshold, no volume point, flat -> 1 point."""
    result = analyze(_daily([112] * 24))
    assert "low_volume" in result["caveats"]
    assert result["confidence"] == "low"


def test_strong_seasonality_is_flagged_and_not_a_trend():
    """School-year pattern (high Sep-Apr, low May-Aug), same every year."""
    year = [8400 if m not in (5, 6, 7, 8) else 840 for m in range(1, 13)]
    result = analyze(_daily(year * 2))
    assert "high_seasonality" in result["caveats"]
    assert result["yoy_change_pct"] == 0.0
    assert result["confidence"] == "medium"  # volume + history, but no significant trend
    assert result["seasonality"]["low_calendar_month"] in {"05", "06", "07", "08"}


def test_stable_growth_is_measured_exactly():
    """Year 1: 28 000/month, year 2: 32 200 (+15%). No caveats, at least medium confidence."""
    result = analyze(_daily([28_000] * 12 + [32_200] * 12))
    assert result["yoy_change_pct"] == 15.0
    assert result["caveats"] == []
    assert result["confidence"] in {"medium", "high"}
    assert result["trend_pct_per_year"] > 0


def test_each_rule_adds_one_point():
    """Remove one ingredient at a time from a high-confidence series."""
    growing = [int(28_000 * 1.02**i) for i in range(36)]
    assert analyze(_daily(growing))["confidence"] == "high"
    assert analyze(_daily([v // 100 for v in growing]))["confidence"] == "medium"  # low volume
    assert analyze(_daily(growing[:18]))["confidence"] == "medium"  # short history

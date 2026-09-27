"""Test cache: SQLite storage and retrieval."""

import tempfile
from datetime import date
from pathlib import Path

from wiki_interest.cache import Cache


def test_cache_store_and_retrieve():
    """Daily views are stored and retrieved correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Cache(Path(tmpdir).joinpath("test.db"))
        try:
            views = {date(2025, 1, 15): 100, date(2025, 1, 16): 150}
            cache.store("uk.wikipedia", "Test", date(2025, 1, 1), date(2025, 1, 31), views)
            retrieved = cache.daily("uk.wikipedia", "Test", date(2025, 1, 1), date(2025, 1, 31))
            assert retrieved == views
        finally:
            cache.db.close()


def test_cache_coverage():
    """Coverage is tracked correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Cache(Path(tmpdir).joinpath("test.db"))
        try:
            cache.store("uk.wikipedia", "Test", date(2025, 1, 1), date(2025, 1, 31), {date(2025, 1, 15): 100})
            cov = cache.coverage("uk.wikipedia", "Test")
            assert cov == (date(2025, 1, 1), date(2025, 1, 31))
        finally:
            cache.db.close()


def test_cache_missing_ranges_uncached():
    """When nothing is cached, the entire range is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Cache(Path(tmpdir).joinpath("test.db"))
        try:
            missing = cache.missing_ranges("uk.wikipedia", "Test", date(2025, 1, 1), date(2025, 1, 31))
            assert missing == [(date(2025, 1, 1), date(2025, 1, 31))]
        finally:
            cache.db.close()


def test_cache_missing_ranges_partial():
    """Partial coverage: identify uncached ranges."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Cache(Path(tmpdir).joinpath("test.db"))
        try:
            cache.store("uk.wikipedia", "Test", date(2025, 1, 1), date(2025, 1, 10), {date(2025, 1, 5): 100})
            missing = cache.missing_ranges("uk.wikipedia", "Test", date(2025, 1, 1), date(2025, 1, 31))
            assert missing == [(date(2025, 1, 11), date(2025, 1, 31))]
        finally:
            cache.db.close()


def test_cache_extend_coverage():
    """When extending the range, only new days are marked missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Cache(Path(tmpdir).joinpath("test.db"))
        try:
            cache.store("uk.wikipedia", "Test", date(2025, 1, 1), date(2025, 1, 10), {date(2025, 1, 5): 100})
            missing = cache.missing_ranges("uk.wikipedia", "Test", date(2025, 1, 1), date(2025, 1, 20))
            assert missing == [(date(2025, 1, 11), date(2025, 1, 20))]
        finally:
            cache.db.close()


def test_cache_disjoint_range_does_not_bridge_gap():
    """A new range that doesn't touch the cached one must not mark the gap between them as fetched."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Cache(Path(tmpdir).joinpath("test.db"))
        try:
            cache.store("uk.wikipedia", "Test", date(2025, 1, 1), date(2025, 12, 31), {})
            cache.store("uk.wikipedia", "Test", date(2026, 3, 1), date(2026, 4, 30), {})
            missing = cache.missing_ranges("uk.wikipedia", "Test", date(2025, 1, 1), date(2026, 4, 30))
            assert missing == [(date(2025, 1, 1), date(2026, 2, 28))]  # Jan-Feb 2026 is fetched
        finally:
            cache.db.close()


def test_cache_store_without_coverage():
    """end < start: views are kept, but no day is marked as fetched."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Cache(Path(tmpdir).joinpath("test.db"))
        try:
            cache.store("uk.wikipedia", "Test", date(2025, 1, 10), date(2025, 1, 9), {date(2025, 1, 10): 7})
            assert cache.coverage("uk.wikipedia", "Test") is None
            assert cache.daily("uk.wikipedia", "Test", date(2025, 1, 1), date(2025, 1, 31)) == {date(2025, 1, 10): 7}
        finally:
            cache.db.close()


def test_cache_lookup():
    """Generic lookups (Wikidata, redirects) are cached."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Cache(Path(tmpdir).joinpath("test.db"))
        try:
            data = {"qid": "Q333", "label": "Astronomy"}
            cache.put_lookup("wikidata:Q333", data)
            retrieved = cache.get_lookup("wikidata:Q333")
            assert retrieved == data
        finally:
            cache.db.close()

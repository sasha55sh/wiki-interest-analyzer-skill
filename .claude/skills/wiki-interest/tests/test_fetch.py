"""Test fetch: days the API may not have published yet are not cached as zeros."""

from datetime import date, timedelta
from pathlib import Path

import httpx
from wiki_interest.cache import Cache
from wiki_interest.fetch import Client, daily_views


def _client(last_published: date) -> Client:
    """Pageviews API that has data only up to `last_published` (publication lag)."""

    def handler(request: httpx.Request) -> httpx.Response:
        s, e = request.url.path.rstrip("/").split("/")[-2:]
        day = date(int(s[:4]), int(s[4:6]), int(s[6:]))
        end = min(date(int(e[:4]), int(e[4:6]), int(e[6:])), last_published)
        items = []
        while day <= end:
            items.append({"timestamp": day.strftime("%Y%m%d00"), "views": 10})
            day += timedelta(days=1)
        return httpx.Response(200, json={"items": items})

    return Client(transport=httpx.MockTransport(handler))


def test_unpublished_days_are_fetched_again(tmp_path: Path):
    cache = Cache(tmp_path / "c.db")
    try:
        start, end, today = date(2026, 9, 1), date(2026, 9, 30), date(2026, 10, 1)
        target = [("uk.wikipedia", "X")]

        first = daily_views(_client(date(2026, 9, 29)), cache, target, start, end, today=today)
        assert date(2026, 9, 30) not in first[target[0]]  # not published yet
        assert cache.coverage("uk.wikipedia", "X")[1] < date(2026, 9, 29)

        later = daily_views(_client(date(2026, 10, 5)), cache, target, start, end, today=date(2026, 10, 6))
        assert later[target[0]][date(2026, 9, 30)] == 10  # re-fetched, not a cached zero
        assert cache.missing_ranges("uk.wikipedia", "X", start, end) == []
    finally:
        cache.db.close()

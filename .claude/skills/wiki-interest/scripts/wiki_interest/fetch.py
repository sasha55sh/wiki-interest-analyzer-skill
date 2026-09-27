"""Wikimedia HTTP client and pageview downloads.

Facts about the API that this module relies on:
- a descriptive User-Agent is mandatory (403 otherwise, even for python-httpx);
- per-article views exclude redirects, so redirects are fetched and summed;
- 404 means "no views recorded" and is treated as zeros;
- monthly buckets are clipped to the requested range, so we fetch daily data and
  aggregate months locally.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote

import httpx

from . import __version__
from .cache import Cache

USER_AGENT = (
    f"wiki-interest-skill/{__version__} "
    "(https://github.com/sasha55sh/wiki-interest-analyzer-skill; Agent Skill for pageview analysis)"
)
PAGEVIEWS = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
TOTAL = "__project_total__"
SETTLE_DAYS = 3  # the API publishes a day's views with a delay of up to a couple of days


class ApiError(RuntimeError):
    pass


class Client:
    """httpx client with User-Agent, retries and a request counter."""

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self.http = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=30, transport=transport, follow_redirects=True
        )
        self.requests = 0

    def get_json(self, url: str, params: dict | None = None) -> dict | None:
        """GET with retries on 429/5xx. Returns None on 404."""
        for attempt in range(4):
            self.requests += 1
            try:
                r = self.http.get(url, params=params)
            except httpx.TransportError as e:
                if attempt == 3:
                    raise ApiError(f"network error: {e}") from e
                time.sleep(2**attempt)
                continue
            if r.status_code == 404:
                return None
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2**attempt)
                continue
            if r.status_code != 200:
                raise ApiError(f"HTTP {r.status_code} for {r.url}: {r.text[:200]}")
            return r.json()
        raise ApiError(f"gave up after retries: {url}")


def _parse_items(payload: dict | None) -> dict[date, int]:
    if not payload:
        return {}
    return {datetime.strptime(i["timestamp"][:8], "%Y%m%d").date(): i["views"] for i in payload["items"]}  # noqa: DTZ007


def _download(client: Client, project: str, title: str, start: date, end: date) -> dict[date, int]:
    s, e = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    if title == TOTAL:
        url = f"{PAGEVIEWS}/aggregate/{project}/all-access/user/daily/{s}/{e}"
    else:
        article = quote(title.replace(" ", "_"), safe="")
        url = f"{PAGEVIEWS}/per-article/{project}/all-access/user/{article}/daily/{s}/{e}"
    return _parse_items(client.get_json(url))


def settled_day(today: date | None = None) -> date:
    """Last day whose pageviews are final; later days may still be missing from the API."""
    return (today or datetime.now(UTC).date()) - timedelta(days=SETTLE_DAYS)


def daily_views(
    client: Client, cache: Cache, targets: list[tuple[str, str]], start: date, end: date, workers: int = 6,
    today: date | None = None,
) -> dict[tuple[str, str], dict[date, int]]:
    """Daily views for each (project, title), downloading only uncached days.

    Days after `settled_day()` are not marked as cached, so they are fetched again next time
    instead of being kept as zeros forever.
    """
    settled = settled_day(today)
    jobs = [(p, t, s, e) for p, t in targets for s, e in cache.missing_ranges(p, t, start, end)]
    if jobs:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda j: _download(client, *j), jobs))
        for (p, t, s, e), views in zip(jobs, results, strict=True):
            cache.store(p, t, s, min(e, settled), views)
    return {(p, t): cache.daily(p, t, start, end) for p, t in targets}

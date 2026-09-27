"""Test resolve: topic search and article discovery."""

from unittest.mock import MagicMock

import pytest
from wiki_interest.cache import Cache
from wiki_interest.fetch import ApiError, Client
from wiki_interest.resolve import TopicError, pick, search


def test_search_returns_candidates():
    """search() returns candidates with Wikipedia presence."""
    client = MagicMock(spec=Client)
    cache = MagicMock(spec=Cache)
    client.get_json.side_effect = lambda url, params: {
        "search": [
            {"id": "Q333", "label": "Astronomy", "description": "natural science"},
            {"id": "Q1234", "label": "Astrology", "description": "belief system"},
        ]
    }
    cache.get_lookup.return_value = None
    cache.put_lookup.return_value = None
    candidates = search(client, cache, "Astronomy", ["uk"])
    assert isinstance(candidates, list)


def test_api_error_is_not_cached(tmp_path):
    """MediaWiki errors come with HTTP 200; they must not be cached as "nothing found"."""
    client = MagicMock(spec=Client)
    client.get_json.return_value = {"error": {"code": "maxlag", "info": "Waiting for a database server"}}
    cache = Cache(tmp_path / "c.db")
    try:
        with pytest.raises(ApiError, match="maxlag"):
            search(client, cache, "Astronomy", ["uk"])
        assert cache.db.execute("SELECT COUNT(*) FROM lookups").fetchone()[0] == 0
    finally:
        cache.db.close()


def test_pick_ambiguous_topic():
    """pick() raises TopicError for ambiguous topics."""
    candidates = [
        {"qid": "Q308", "label": "Mercury", "wikipedias": 100},
        {"qid": "Q925", "label": "mercury", "wikipedias": 50},  # > 30% of top
    ]
    with pytest.raises(TopicError) as exc_info:
        pick(candidates, "Mercury")
    assert exc_info.value.code == "ambiguous_topic"
    assert len(exc_info.value.candidates) == 2


def test_pick_unambiguous_topic():
    """pick() returns the top candidate if rivals are much smaller."""
    candidates = [
        {"qid": "Q333", "label": "Astronomy", "wikipedias": 100},
        {"qid": "Q1234", "label": "Astrology", "wikipedias": 5},  # < 30% of top
    ]
    result = pick(candidates, "Astronomy")
    assert result["qid"] == "Q333"


def test_pick_unknown_topic():
    """pick() raises TopicError when no candidates exist."""
    with pytest.raises(TopicError) as exc_info:
        pick([], "xyz-nonexistent")
    assert exc_info.value.code == "unknown_topic"

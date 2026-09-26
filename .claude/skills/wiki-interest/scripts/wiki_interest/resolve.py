"""Topic text or QIDs -> Wikipedia article titles (plus redirects) per language."""

from dataclasses import dataclass, field

from .cache import Cache
from .fetch import Client

WIKIDATA = "https://www.wikidata.org/w/api.php"
AMBIGUITY_RATIO = 0.3


class TopicError(ValueError):
    """User-facing resolution problem (ambiguous or unknown topic)."""

    def __init__(self, code: str, message: str, hint: str, candidates: list | None = None):
        super().__init__(message)
        self.code, self.hint, self.candidates = code, hint, candidates or []


@dataclass
class Article:
    qid: str
    lang: str
    title: str
    redirects: list[str] = field(default_factory=list)

    @property
    def project(self) -> str:
        return f"{self.lang}.wikipedia"


@dataclass
class Resolution:
    items: list[dict]
    articles: dict[str, list[Article]]
    missing: dict[str, list[str]] 

def _cached(client: Client, cache: Cache, url: str, params: dict) -> dict:
    key = url + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
    value = cache.get_lookup(key)
    if value is None:
        value = client.get_json(url, params) or {}
        cache.put_lookup(key, value)
    return value


def _entities(client: Client, cache: Cache, qids: list[str], langs: list[str]) -> dict:
    data = _cached(
        client, cache, WIKIDATA,
        {"action": "wbgetentities", "ids": "|".join(qids), "props": "sitelinks|labels|descriptions",
         "languages": "|".join(["en", *langs]), "format": "json"},
    )
    return data.get("entities", {})


def _wiki_sitelinks(entity: dict) -> int:
    skip = ("commonswiki", "specieswiki", "metawiki", "wikidatawiki", "mediawikiwiki", "sourceswiki")
    return sum(1 for k in entity.get("sitelinks", {}) if k.endswith("wiki") and k not in skip)


def _label(entity: dict, langs: list[str], kind: str = "labels") -> str:
    values = entity.get(kind, {})
    for lang in ["en", *langs]:
        if lang in values:
            return values[lang]["value"]
    return ""


def search(client: Client, cache: Cache, topic: str, langs: list[str]) -> list[dict]:
    """Candidate entities for a topic, best first, each with its Wikipedia sitelink count."""
    ids: list[str] = []
    for lang in dict.fromkeys(["en", *langs]):
        data = _cached(
            client, cache, WIKIDATA,
            {"action": "wbsearchentities", "search": topic, "language": lang, "uselang": lang,
             "limit": 7, "type": "item", "format": "json"},
        )
        for hit in data.get("search", []):
            if hit["id"] not in ids:
                ids.append(hit["id"])
    if not ids:
        return []
    entities = _entities(client, cache, ids[:50], langs)
    out = []
    for qid in ids:
        e = entities.get(qid, {})
        en_desc = e.get("descriptions", {}).get("en", {}).get("value", "")
        if en_desc.startswith("Wikimedia "):
            continue
        n = _wiki_sitelinks(e)
        if n:
            out.append({"qid": qid, "label": _label(e, langs), "description": _label(e, langs, "descriptions"),
                        "wikipedias": n})
    return out


def pick(candidates: list[dict], topic: str) -> dict:
    """Choose the main candidate or raise if the topic is ambiguous."""
    if not candidates:
        raise TopicError(
            "unknown_topic", f"No Wikipedia article found for '{topic}'.",
            "Try an English name of the topic, a more specific phrase, or pass --qids.",
        )
    top = candidates[0]
    rivals = [c for c in candidates[1:4] if c["wikipedias"] >= AMBIGUITY_RATIO * top["wikipedias"]]
    if rivals:
        options = [top, *rivals]
        raise TopicError(
            "ambiguous_topic", f"'{topic}' can mean several things.",
            "Pick the intended meaning (ask the user if unclear) and re-run with --qids <QID>.",
            [{"qid": c["qid"], "label": c["label"], "description": c.get("description", "")} for c in options],
        )
    return top


def _redirects(client: Client, cache: Cache, lang: str, titles: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {t: [] for t in titles}
    for i in range(0, len(titles), 50):
        data = _cached(
            client, cache, f"https://{lang}.wikipedia.org/w/api.php",
            {"action": "query", "prop": "redirects", "titles": "|".join(titles[i:i + 50]), "rdlimit": "max",
             "rdnamespace": 0, "format": "json", "formatversion": 2},
        )
        for page in data.get("query", {}).get("pages", []):
            if page.get("title") in out:
                out[page["title"]] = [r["title"] for r in page.get("redirects", [])]
    return out


def resolve(
    client: Client, cache: Cache, langs: list[str], topic: str | None = None, qids: list[str] | None = None
) -> Resolution:
    if not qids:
        qids = [pick(search(client, cache, topic or "", langs), topic or "")["qid"]]
    entities = _entities(client, cache, qids, langs)
    items, articles, missing = [], {lang: [] for lang in langs}, {lang: [] for lang in langs}
    for qid in qids:
        e = entities.get(qid)
        if not e or "missing" in e:
            raise TopicError("unknown_qid", f"Wikidata item {qid} does not exist.", "Check the QID.")
        items.append({"qid": qid, "label": _label(e, langs), "description": _label(e, langs, "descriptions")})
        for lang in langs:
            link = e.get("sitelinks", {}).get(f"{lang}wiki")
            if link:
                articles[lang].append(Article(qid, lang, link["title"]))
            else:
                missing[lang].append(qid)
    for lang, arts in articles.items():
        if arts:
            redirects = _redirects(client, cache, lang, [a.title for a in arts])
            for a in arts:
                a.redirects = redirects.get(a.title, [])
    return Resolution(items, articles, missing)

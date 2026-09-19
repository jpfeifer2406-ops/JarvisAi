from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

from ddgs import DDGS


@dataclass(frozen=True)
class NewsRegion:
    key: str
    label: str
    query: str
    ddgs_region: str
    lat: float
    lng: float
    altitude: float
    aliases: tuple[str, ...]


REGIONS: dict[str, NewsRegion] = {
    "world": NewsRegion(
        key="world",
        label="WELT",
        query="Welt Nachrichten",
        ddgs_region="de-de",
        lat=18.0,
        lng=10.0,
        altitude=2.15,
        aliases=("welt", "global", "international", "internationalen", "weltweit"),
    ),
    "germany": NewsRegion(
        key="germany",
        label="DEUTSCHLAND",
        query="Deutschland Nachrichten",
        ddgs_region="de-de",
        lat=51.1657,
        lng=10.4515,
        altitude=0.58,
        aliases=("deutschland", "germany", "bundesrepublik"),
    ),
    "nrw": NewsRegion(
        key="nrw",
        label="NORDRHEIN-WESTFALEN",
        query="Nordrhein-Westfalen Nachrichten",
        ddgs_region="de-de",
        lat=51.4332,
        lng=7.6616,
        altitude=0.34,
        aliases=("nordrhein-westfalen", "nordrhein westfalen", "nrw"),
    ),
    "europe": NewsRegion(
        key="europe",
        label="EUROPA",
        query="Europa Nachrichten",
        ddgs_region="de-de",
        lat=54.0,
        lng=15.0,
        altitude=0.92,
        aliases=("europa", "eu", "europäisch", "europaeisch"),
    ),
    "usa": NewsRegion(
        key="usa",
        label="USA",
        query="USA Nachrichten",
        ddgs_region="us-en",
        lat=39.8,
        lng=-98.6,
        altitude=0.72,
        aliases=("usa", "vereinigte staaten", "amerika", "united states"),
    ),
    "uk": NewsRegion(
        key="uk",
        label="VEREINIGTES KÖNIGREICH",
        query="United Kingdom Nachrichten",
        ddgs_region="uk-en",
        lat=55.4,
        lng=-3.4,
        altitude=0.56,
        aliases=("großbritannien", "grossbritannien", "vereinigtes königreich", "uk", "england"),
    ),
    "france": NewsRegion(
        key="france",
        label="FRANKREICH",
        query="Frankreich Nachrichten",
        ddgs_region="fr-fr",
        lat=46.2,
        lng=2.2,
        altitude=0.56,
        aliases=("frankreich", "france"),
    ),
}

_NEWS_TRIGGER = re.compile(r"\b(nachrichten|news|schlagzeilen|lagebericht)\b", re.IGNORECASE)


def _normalize(text: str) -> str:
    text = text.lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-zäöüß0-9\- ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_news_region(text: str) -> NewsRegion | None:
    """Return a configured news region when the utterance is a news request."""
    normalized = _normalize(text)
    if not _NEWS_TRIGGER.search(normalized):
        return None

    # Most specific aliases first so NRW wins over broad/global wording.
    for key in ("nrw", "germany", "europe", "usa", "uk", "france", "world"):
        region = REGIONS[key]
        if any(
            re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized)
            for alias in region.aliases
        ):
            return region

    return REGIONS["world"]


def _clean_result(raw: dict[str, Any]) -> dict[str, str]:
    title = str(raw.get("title") or "").strip()
    body = re.sub(r"\s+", " ", str(raw.get("body") or "")).strip()
    return {
        "title": title,
        "summary": body[:360],
        "source": str(raw.get("source") or "").strip(),
        "date": str(raw.get("date") or "").strip(),
        "url": str(raw.get("url") or raw.get("href") or "").strip(),
        "image": str(raw.get("image") or "").strip(),
    }


def fetch_news(region: NewsRegion, max_results: int = 6) -> list[dict[str, str]]:
    """Fetch recent headlines for a region with a one-week fallback."""
    ddgs = DDGS()
    results: list[dict[str, Any]] = []

    try:
        results = ddgs.news(
            region.query,
            region=region.ddgs_region,
            safesearch="moderate",
            timelimit="d",
            max_results=max_results,
        )
    except Exception:
        results = []

    if len(results) < 3:
        try:
            weekly = ddgs.news(
                region.query,
                region=region.ddgs_region,
                safesearch="moderate",
                timelimit="w",
                max_results=max_results,
            )
            seen = {str(item.get("url") or item.get("title")) for item in results}
            for item in weekly:
                token = str(item.get("url") or item.get("title"))
                if token not in seen:
                    results.append(item)
                    seen.add(token)
                if len(results) >= max_results:
                    break
        except Exception:
            pass

    cleaned = [_clean_result(item) for item in results]
    return [item for item in cleaned if item["title"]][:max_results]


def build_news_payload(text: str, max_results: int = 6) -> dict[str, Any] | None:
    region = detect_news_region(text)
    if region is None:
        return None

    items = fetch_news(region, max_results=max_results)
    return {
        "region": asdict(region),
        "items": items,
    }


def build_spoken_briefing(payload: dict[str, Any], max_spoken: int = 3) -> str:
    """Create a deliberately short spoken overview; detail is opt-in."""
    region = payload["region"]["label"]
    items = payload.get("items", [])
    if not items:
        return f"Captain, für {region} konnten aktuell keine Nachrichten geladen werden."

    ordinals = ("Erstens", "Zweitens", "Drittens", "Viertens", "Fünftens")
    lines = [f"Captain, Nachrichtenlage {region}."]
    for idx, item in enumerate(items[:max_spoken]):
        prefix = ordinals[idx] if idx < len(ordinals) else f"Meldung {idx + 1}"
        lines.append(f"{prefix}: {item['title']}.")
    lines.append("Details auf Befehl.")
    return " ".join(lines)

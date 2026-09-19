from jarvis.news import (
    REGIONS,
    build_spoken_briefing,
    detect_news_region,
    fetch_news,
)


def test_detect_news_region_defaults_to_world():
    region = detect_news_region("Computer, die Nachrichten.")
    assert region is not None
    assert region.key == "world"


def test_detect_news_region_germany_and_nrw():
    assert detect_news_region("Nachrichten für Deutschland").key == "germany"
    assert detect_news_region("Zeig mir die News aus NRW").key == "nrw"


def test_non_news_request_is_ignored():
    assert detect_news_region("Öffne Spotify") is None


def test_spoken_briefing_is_intentionally_short():
    payload = {
        "region": {"label": "DEUTSCHLAND"},
        "items": [
            {"title": "A"},
            {"title": "B"},
            {"title": "C"},
            {"title": "D"},
        ],
    }
    text = build_spoken_briefing(payload)
    assert "A" in text and "B" in text and "C" in text
    assert "D" not in text
    assert text.endswith("Details auf Befehl.")


def test_fetch_news_falls_back_and_deduplicates(monkeypatch):
    daily = [
        {"title": "A", "body": "Kurz A", "url": "https://a", "source": "S1", "date": "2026-09-19"},
    ]
    weekly = [
        {"title": "A", "body": "Kurz A", "url": "https://a", "source": "S1", "date": "2026-09-19"},
        {"title": "B", "body": "Kurz B", "url": "https://b", "source": "S2", "date": "2026-09-18"},
        {"title": "C", "body": "Kurz C", "url": "https://c", "source": "S3", "date": "2026-09-18"},
    ]

    class FakeDDGS:
        def news(self, query, **kwargs):
            return daily if kwargs.get("timelimit") == "d" else weekly

    monkeypatch.setattr("jarvis.news.DDGS", FakeDDGS)
    items = fetch_news(REGIONS["germany"], max_results=6)

    assert [item["title"] for item in items] == ["A", "B", "C"]

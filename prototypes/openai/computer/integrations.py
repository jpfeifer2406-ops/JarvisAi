import time
from .contracts import ToolResult
from .network import fetch_public, public_url

FEEDS = {
    "Deutschland": "https://www.tagesschau.de/xml/rss2/",
    "Europa": "https://www.tagesschau.de/ausland/europa/index~rss2.xml",
    "Welt": "https://www.tagesschau.de/ausland/index~rss2.xml",
}


class Integrations:
    def __init__(self, drive_reader=None):
        self.tabs = {}
        self.drive_reader = drive_reader

    def share_tab(self, session_id, title, url):
        public_url(url)
        self.tabs[session_id] = {"title": title[:300], "url": url, "received": time.monotonic()}

    def browser_status(self, session_id):
        tab = self.tabs.get(session_id)
        if not tab or time.monotonic() - tab["received"] > 120:
            return ToolResult(status="unavailable", message="Kein aktueller, explizit geteilter Browser-Tab.")
        return ToolResult(
            status="ok",
            message="Geteilter Tab; keine Browsersteuerung.",
            data={k: v for k, v in tab.items() if k != "received"},
        )

    async def news(self, region):
        from defusedxml.ElementTree import fromstring

        xml = await fetch_public(FEEDS[region])
        root = fromstring(xml)
        items = [
            {
                "title": node.findtext("title", ""),
                "url": node.findtext("link", ""),
                "date": node.findtext("pubDate", ""),
            }
            for node in root.findall(".//item")[:8]
        ]
        return ToolResult(
            status="ok",
            message="Quellenmeldungen; keine erfundenen Ersatznachrichten.",
            data={"region": region, "items": items, "source": FEEDS[region]},
        )

    async def drive_list(self):
        if not self.drive_reader:
            return ToolResult(status="unavailable", message="Google Drive ist nicht autorisiert.")
        return await self.drive_reader.list()

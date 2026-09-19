# COMPUTER News Globe — experimental feature specification

Branch: feature-news-globe

## User experience

A command such as:

- Computer, die Nachrichten.
- Computer, Nachrichten für Deutschland.
- Computer, Nachrichten für NRW.

switches the cockpit into a dedicated visual situation view.

The left side shows an interactive Earth globe with a satellite-style Blue
Marble texture. COMPUTER animates the camera to the requested region and marks
the target. The right side shows fresh headlines, source and timestamp.

COMPUTER speaks only a short briefing (maximum three headlines by default) and
ends with: Details auf Befehl.

If the user explicitly asks to expand a specific item, the previous headline
payload is supplied as temporary context to the normal agent. The agent should
then verify current source material with tools before giving a deeper answer.

## Current region presets

- World
- Germany
- North Rhine-Westphalia
- Europe
- USA
- United Kingdom
- France

More countries can be added to jarvis/news.py.

## Data path

Voice/Web input
→ process_request()
→ jarvis.news.detect_news_region()
→ DDGS news search
→ WebSocket news_mode event
→ globe focus + headline cards
→ concise Kokoro briefing

The UI can also refresh a region through GET /api/news?region=<key>.

## Status

Implemented in code, not yet validated on the Captain's Windows target machine.

The globe currently uses a pinned CDN dependency for the experimental build.
A later packaging pass should vendor the approved JS and imagery assets for
reproducible/offline-capable installs.

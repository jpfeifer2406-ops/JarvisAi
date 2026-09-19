from __future__ import annotations

import re


def _normalize(text: str) -> str:
    text = text.lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-zäöüß0-9\- ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_OPEN_PHRASES = (
    "eingabe öffnen",
    "eingabe oeffnen",
    "texteingabe öffnen",
    "texteingabe oeffnen",
    "chat öffnen",
    "chat oeffnen",
    "konsole öffnen",
    "konsole oeffnen",
    "open input",
    "open chat",
)

_CLOSE_PHRASES = (
    "eingabe schließen",
    "eingabe schliessen",
    "texteingabe schließen",
    "texteingabe schliessen",
    "chat schließen",
    "chat schliessen",
    "konsole schließen",
    "konsole schliessen",
    "close input",
    "close chat",
)


def detect_ui_command(text: str) -> bool | None:
    """Return True=open, False=close, None=not a COMPUTER UI command."""
    normalized = _normalize(text)
    if any(phrase in normalized for phrase in _OPEN_PHRASES):
        return True
    if any(phrase in normalized for phrase in _CLOSE_PHRASES):
        return False
    return None

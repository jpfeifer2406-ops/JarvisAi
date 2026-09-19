from __future__ import annotations

import re


def _normalize(text: str) -> str:
    text = text.lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-zäöüß0-9\- ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_CHAT_OPEN = (
    "eingabe öffnen", "eingabe oeffnen", "texteingabe öffnen",
    "texteingabe oeffnen", "chat öffnen", "chat oeffnen",
    "open input", "open chat",
)
_CHAT_CLOSE = (
    "eingabe schließen", "eingabe schliessen", "texteingabe schließen",
    "texteingabe schliessen", "chat schließen", "chat schliessen",
    "close input", "close chat",
)


def detect_ui_command(text: str) -> bool | None:
    """Backward-compatible chat-panel detector."""
    normalized = _normalize(text)
    if any(phrase in normalized for phrase in _CHAT_OPEN):
        return True
    if any(phrase in normalized for phrase in _CHAT_CLOSE):
        return False
    return None


def detect_overlay_command(text: str) -> tuple[str, bool] | None:
    """Detect deterministic cockpit overlay commands.

    Returns (panel, open) where panel is settings, workshop or call.
    """
    normalized = _normalize(text)

    groups = {
        "settings": (
            ("einstellungen öffnen", "einstellungen oeffnen", "konsole öffnen",
             "konsole oeffnen", "settings öffnen", "settings oeffnen", "open settings"),
            ("einstellungen schließen", "einstellungen schliessen", "konsole schließen",
             "konsole schliessen", "settings schließen", "settings schliessen", "close settings"),
        ),
        "workshop": (
            ("werkstatt öffnen", "werkstatt oeffnen", "creative werkstatt öffnen",
             "creative werkstatt oeffnen", "kreativwerkstatt öffnen",
             "kreativwerkstatt oeffnen", "creative workshop öffnen",
             "creative workshop oeffnen", "open workshop"),
            ("werkstatt schließen", "werkstatt schliessen", "creative werkstatt schließen",
             "creative werkstatt schliessen", "kreativwerkstatt schließen",
             "kreativwerkstatt schliessen", "close workshop"),
        ),
        "call": (
            ("anruf öffnen", "anruf oeffnen", "anrufmodus öffnen", "anrufmodus oeffnen",
             "call öffnen", "call oeffnen", "open call"),
            ("anruf schließen", "anruf schliessen", "anrufmodus schließen",
             "anrufmodus schliessen", "call schließen", "call schliessen", "close call"),
        ),
    }

    for panel, (open_phrases, close_phrases) in groups.items():
        if any(phrase in normalized for phrase in open_phrases):
            return panel, True
        if any(phrase in normalized for phrase in close_phrases):
            return panel, False
    return None

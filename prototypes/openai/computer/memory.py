"""Explicit, session-local preferences only. No transcript mining or disk writes.

Free-form memory is intentionally absent until retention/encryption/DLP is designed.
"""

from typing import Literal
from .contracts import StrictModel


class Preferences(StrictModel):
    response_length: Literal["kurz", "normal", "ausführlich"] = "normal"
    address: Literal["Captain", "neutral"] = "Captain"


class Memory:
    def __init__(self):
        self.preferences = Preferences()

    def set(self, raw):
        self.preferences = Preferences.model_validate(raw)

    def clear(self):
        self.preferences = Preferences()

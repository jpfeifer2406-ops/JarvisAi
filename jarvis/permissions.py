from __future__ import annotations

import re
import time
from dataclasses import dataclass
from threading import Lock

READ = "READ"
PREPARE = "PREPARE"
EXECUTE = "EXECUTE"
CRITICAL = "CRITICAL"

TOOL_RISK = {
    # Read-only / observational
    "web_search": READ,
    "fetch_page": READ,
    "get_weather": READ,
    "read_screen": READ,
    "find_on_screen": READ,
    "get_open_windows": READ,
    "read_file": READ,
    "list_files": READ,
    "read_document": READ,
    "list_documents": READ,
    "get_clipboard": READ,
    "get_volume": READ,
    "get_system_info": READ,
    # Local drafts / reversible preparation
    "create_document": PREPARE,
    "revise_document": PREPARE,
    "screenshot": PREPARE,
    "delegate_task": PREPARE,
    # State changes requiring explicit Captain approval
    "open_url": EXECUTE,
    "open_app": EXECUTE,
    "click_at": EXECUTE,
    "scroll_screen": EXECUTE,
    "move_mouse": EXECUTE,
    "focus_window": EXECUTE,
    "type_text": EXECUTE,
    "press_key": EXECUTE,
    "media_control": EXECUTE,
    "set_clipboard": EXECUTE,
    "set_volume": EXECUTE,
    "set_brightness": EXECUTE,
    "show_notification": EXECUTE,
    "set_timer": EXECUTE,
    # Destructive / arbitrary execution
    "kill_process": CRITICAL,
    "write_file": CRITICAL,
    "run_python": CRITICAL,
    "lock_screen": CRITICAL,
    "power_command": CRITICAL,
}


def risk_for_tool(name: str) -> str:
    # Fail closed for a newly added tool until its risk is deliberately classified.
    return TOOL_RISK.get(name, CRITICAL)


def requires_approval(name: str) -> bool:
    return risk_for_tool(name) in {EXECUTE, CRITICAL}


def _normalize(text: str) -> str:
    text = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def approval_intent(text: str, risk: str) -> str | None:
    """Return approve/cancel only for deliberately explicit phrases."""
    cleaned = _normalize(text)
    cancel = (
        "aktion abbrechen", "ausfuehrung abbrechen", "nicht ausfuehren",
        "nicht freigeben", "abbrechen",
    )
    if any(phrase in cleaned for phrase in cancel):
        return "cancel"

    if risk == CRITICAL:
        strong = (
            "kritische aktion bestaetigen",
            "kritische aktion freigeben",
            "kritische ausfuehrung bestaetigen",
            "kritische ausfuehrung freigeben",
            "ich bestaetige die kritische aktion",
        )
        return "approve" if any(phrase in cleaned for phrase in strong) else None

    normal = (
        "aktion freigeben", "aktion ausfuehren", "ausfuehrung freigeben",
        "ausfuehrung bestaetigen", "ich gebe die aktion frei",
    )
    return "approve" if any(phrase in cleaned for phrase in normal) else None


@dataclass
class PendingAction:
    name: str
    args: dict
    risk: str
    created_at: float


class PermissionBroker:
    def __init__(self, ttl_seconds: int = 120):
        self.ttl_seconds = ttl_seconds
        self._pending: PendingAction | None = None
        self._lock = Lock()

    def stage(self, name: str, args: dict) -> PendingAction:
        with self._lock:
            now = time.monotonic()
            if self._pending and now - self._pending.created_at <= self.ttl_seconds:
                return self._pending
            self._pending = PendingAction(name=name, args=dict(args), risk=risk_for_tool(name), created_at=now)
            return self._pending

    def get(self) -> PendingAction | None:
        with self._lock:
            if self._pending and time.monotonic() - self._pending.created_at > self.ttl_seconds:
                self._pending = None
            return self._pending

    def clear(self) -> None:
        with self._lock:
            self._pending = None

    def decide(self, text: str) -> tuple[str | None, PendingAction | None]:
        pending = self.get()
        if not pending:
            return None, None
        decision = approval_intent(text, pending.risk)
        if decision in {"approve", "cancel"}:
            self.clear()
        return decision, pending


def approval_message(action: PendingAction) -> str:
    if action.risk == CRITICAL:
        return (
            f"Captain, kritische Aktion vorbereitet: {action.name}. "
            "Ausführung blockiert. Sagen Sie „Kritische Aktion bestätigen“ oder „Aktion abbrechen“."
        )
    return (
        f"Captain, die Aktion ist vorbereitet: {action.name}. "
        "Ausführung wartet auf Ihre Freigabe. Sagen Sie „Aktion freigeben“ oder „Aktion abbrechen“."
    )

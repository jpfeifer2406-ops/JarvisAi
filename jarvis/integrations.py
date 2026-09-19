from __future__ import annotations

import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent
_DATA_DIR = Path(__file__).parent / "data"
_BROWSER_STATE: dict[str, Any] = {"last_seen": 0.0, "title": "", "url": ""}
_LOCK = threading.Lock()


def _find_kde_connect() -> str | None:
    candidates = (
        shutil.which("kdeconnect-cli"),
        shutil.which("kdeconnect-cli.exe"),
        str(Path.home() / "scoop" / "apps" / "kdeconnect" / "current" / "bin" / "kdeconnect-cli.exe"),
        r"C:\Program Files\KDE Connect\bin\kdeconnect-cli.exe",
        r"C:\Program Files\KDE\KDE Connect\bin\kdeconnect-cli.exe",
    )
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def note_browser_ping(title: str = "", url: str = "") -> None:
    with _LOCK:
        _BROWSER_STATE.update({
            "last_seen": time.time(),
            "title": title[:300],
            "url": url[:2000],
        })


def get_integrations_status(config: dict | None = None) -> dict:
    config = config or {}
    phone_bin = _find_kde_connect()
    phone_connected = False
    phone_detail = "Kostenlose KDE-Connect-App noch nicht erkannt."
    if phone_bin:
        phone_detail = "KDE Connect erkannt; noch kein erreichbares Gerät bestätigt."
        try:
            result = subprocess.run(
                [phone_bin, "-a"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            output = (result.stdout or "").strip()
            if output and "0 devices found" not in output.lower():
                phone_connected = True
                phone_detail = output.splitlines()[0][:300]
        except Exception:
            pass

    now = time.time()
    with _LOCK:
        browser = dict(_BROWSER_STATE)

    browser_connected = bool(browser["last_seen"] and now - float(browser["last_seen"]) < 90)
    drive_cfg = config.get("integrations", {}).get("google_drive", {})
    client_secret = _PROJECT_ROOT / drive_cfg.get("client_secret_path", "jarvis/data/google_client_secret.json")
    token = _PROJECT_ROOT / drive_cfg.get("token_path", "jarvis/data/google_drive_token.json")

    return {
        "phone": {
            "provider": "KDE Connect",
            "state": "connected" if phone_connected else ("available" if phone_bin else "not_installed"),
            "connected": phone_connected,
            "detail": phone_detail,
            "setup_url": "https://kdeconnect.kde.org/",
        },
        "browser": {
            "provider": "COMPUTER Browser Bridge",
            "state": "connected" if browser_connected else "not_connected",
            "connected": browser_connected,
            "detail": browser.get("title") or "Lokale Erweiterung noch nicht verbunden.",
            "url": browser.get("url", ""),
        },
        "google_drive": {
            "provider": "Google Drive OAuth",
            "state": "connected" if token.exists() else ("ready" if client_secret.exists() else "credentials_required"),
            "connected": token.exists(),
            "detail": (
                "OAuth-Token vorhanden."
                if token.exists()
                else "OAuth-Client vorhanden; Anmeldung noch ausstehend."
                if client_secret.exists()
                else "Google-OAuth-Clientdatei fehlt."
            ),
            "credential_path": str(client_secret.relative_to(_PROJECT_ROOT)),
        },
    }

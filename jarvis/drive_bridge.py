from __future__ import annotations

from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent
_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _paths(config: dict) -> tuple[Path, Path]:
    drive = config.get("integrations", {}).get("google_drive", {})
    client_secret = _PROJECT_ROOT / drive.get(
        "client_secret_path", "jarvis/data/google_client_secret.json"
    )
    token = _PROJECT_ROOT / drive.get(
        "token_path", "jarvis/data/google_drive_token.json"
    )
    return client_secret, token


def connect_google_drive(config: dict) -> str:
    """Run an explicit local-browser OAuth flow for read-only Drive access."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_secret, token = _paths(config)
    if not client_secret.exists():
        raise FileNotFoundError(
            "Google OAuth client file missing: "
            + str(client_secret.relative_to(_PROJECT_ROOT))
        )

    token.parent.mkdir(parents=True, exist_ok=True)
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), _SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    token.write_text(creds.to_json(), encoding="utf-8")
    return "Google Drive verbunden (READ-ONLY)."


def list_drive_files(config: dict, limit: int = 20) -> list[dict[str, Any]]:
    """Return a small read-only listing from the authorized Drive."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    _client_secret, token = _paths(config)
    if not token.exists():
        raise FileNotFoundError("Google Drive ist noch nicht autorisiert.")

    creds = Credentials.from_authorized_user_file(str(token), _SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token.write_text(creds.to_json(), encoding="utf-8")

    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    response = service.files().list(
        pageSize=max(1, min(int(limit), 100)),
        fields="files(id,name,mimeType,modifiedTime,webViewLink)",
        orderBy="modifiedTime desc",
    ).execute()
    return response.get("files", [])

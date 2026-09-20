"""Explicit desktop OAuth; token stays in the OS credential store.

No Drive writes, no plaintext token fallback, no status inferred from mere files.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from ..contracts import ToolResult

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SERVICE = "COMPUTER-Prototype-A"
ACCOUNT = "google-drive-readonly"


def credential_store():
    import keyring

    backend = keyring.get_keyring()
    module = type(backend).__module__
    if module not in ("keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.SecretService"):
        raise RuntimeError("OS credential backend required; plaintext/chained fallback disabled")
    return keyring


class DriveReader:
    async def list(self):
        with tempfile.TemporaryDirectory(prefix="computer-drive-") as folder:
            output = Path(folder) / "result.json"
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "computer.adapters.drive",
                "list",
                str(output),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                async with asyncio.timeout(25):
                    await process.wait()
                if process.returncode:
                    return ToolResult(
                        status="unavailable", message="Drive nicht autorisiert oder nicht erreichbar."
                    )
                return ToolResult(
                    status="ok",
                    message="Google Drive mit Read-only OAuth gelesen.",
                    data=json.loads(output.read_text()),
                )
            finally:
                if process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), 3)
                    except TimeoutError:
                        process.kill()
                        await process.wait()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Explizite lokale Drive-Read-only-Einrichtung")
    parser.add_argument("action", choices=["authorize", "list", "forget"])
    parser.add_argument("path", nargs="?")
    args = parser.parse_args()
    store = credential_store()
    if args.action == "authorize":
        from google_auth_oauthlib.flow import InstalledAppFlow

        credentials = InstalledAppFlow.from_client_secrets_file(args.path, SCOPES).run_local_server(
            host="127.0.0.1", port=0, open_browser=True
        )
        store.set_password(SERVICE, ACCOUNT, credentials.to_json())
        print("Drive Read-only autorisiert. Token im OS-Credential-Store.")
    elif args.action == "forget":
        store.delete_password(SERVICE, ACCOUNT)
        print("Lokaler Drive-Token entfernt. Providerseitiger Widerruf bleibt separat.")
    else:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        raw = store.get_password(SERVICE, ACCOUNT)
        if not raw:
            raise RuntimeError("Not authorized")
        info = json.loads(raw)
        if set(info.get("scopes", [])) != set(SCOPES):
            raise RuntimeError("Unexpected OAuth scope")
        credentials = Credentials.from_authorized_user_info(info, SCOPES)
        if credentials.expired:
            credentials.refresh(Request())
        store.set_password(SERVICE, ACCOUNT, credentials.to_json())
        with build("drive", "v3", credentials=credentials, cache_discovery=False) as service:
            result = (
                service.files()
                .list(
                    pageSize=20,
                    q="trashed = false",
                    orderBy="modifiedTime desc",
                    fields="files(id,name,mimeType,modifiedTime)",
                )
                .execute()
            )
        Path(args.path).write_text(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

import argparse
import secrets
from pathlib import Path
import uvicorn
from .api import create_app


def main():
    parser = argparse.ArgumentParser(description="COMPUTER Prototyp A — experimenteller lokaler Kern")
    parser.add_argument("--data", type=Path, default=Path(".runtime"))
    args = parser.parse_args()
    token = secrets.token_urlsafe(32)
    print("COMPUTER · Prototyp A · NICHT hardwarevalidiert")
    print("Cockpit: http://127.0.0.1:7861")
    print("Lokaler Zugangscode (nicht teilen):", token)
    # One process owns sessions, broker and audio. Never start multiple workers.
    uvicorn.run(create_app(args.data, token), host="127.0.0.1", port=7861, workers=1, access_log=False)


if __name__ == "__main__":
    main()

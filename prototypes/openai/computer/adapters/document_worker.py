"""Fixed document renderer process. Not an arbitrary-code sandbox."""

import json
import sys
from pathlib import Path
from computer.documents import Documents

if __name__ == "__main__":
    payload = json.load(sys.stdin)
    Path(sys.argv[1]).write_bytes(Documents.render(payload["text"], payload["format"]))

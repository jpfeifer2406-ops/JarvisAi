"""Disposable optional-native-import probe; stdout contains sanitized JSON only."""
import contextlib
import importlib
import json
import os
import sys
from .diagnostics import failure

MODULES = {'pipecat': 'computer.adapters.livekit_voice', 'stt': 'faster_whisper',
           'qwen': 'qwen_tts', 'wake': 'openwakeword'}


def main():
    result = {'status': 'READY', 'message': 'Import erfolgreich; kein Geräte-/Inferenztest.'}
    try:
        with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            importlib.import_module(MODULES[sys.argv[1]])
    except Exception as exc:
        result = {'status': 'UNAVAILABLE', **failure(exc)}
    print(json.dumps(result))


if __name__ == '__main__':
    main()

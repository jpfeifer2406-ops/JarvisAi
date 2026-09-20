"""Optional native imports run outside the text process. No automatic installs."""
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import httpx
from .diagnostics import failure


async def import_check(name):
    process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'computer.import_probe', name,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), 20)
        if process.returncode:
            return {'status': 'UNAVAILABLE', 'message': 'Importprozess abgebrochen; native DLL/Windows-Ereignisprotokoll prüfen.'}
        return json.loads(stdout)
    except TimeoutError:
        return {'status': 'DEGRADED', 'message': 'Importprüfung nach 20 Sekunden abgebrochen.'}
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def startup_checks():
    checks = {'python': {'status': 'READY' if (3, 11) <= sys.version_info[:2] < (3, 13) else 'UNAVAILABLE',
                         'message': '.'.join(map(str, sys.version_info[:3]))}}
    for package in ['openai-agents', 'openai', 'fastapi', 'pipecat-ai', 'livekit', 'loudness', 'faster-whisper', 'qwen-tts', 'openwakeword']:
        try:
            version = importlib.metadata.version(package)
            checks[package] = {'status': 'READY', 'message': 'Installiert: ' + version}
        except importlib.metadata.PackageNotFoundError:
            checks[package] = {'status': 'UNAVAILABLE', 'message': 'Nicht installiert.'}
    checks['openai_key'] = {'status': 'READY' if os.environ.get('OPENAI_API_KEY') else 'UNAVAILABLE',
                             'message': 'Umgebungs-Key konfiguriert.' if os.environ.get('OPENAI_API_KEY') else 'Kein Umgebungs-Key; im Cockpit nur für eigene Sitzung eintragen.'}
    checks['livekit_config'] = {'status': 'DEGRADED' if all(os.environ.get(k) for k in ['LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET']) else 'UNAVAILABLE',
                                'message': 'Konfiguration vorhanden; Verbindung separat prüfen.' if all(os.environ.get(k) for k in ['LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET']) else 'LiveKit-URL/Key/Secret fehlen.'}
    for name, variable, directory in [('stt_model','COMPUTER_STT_MODEL',True),('qwen_model','COMPUTER_QWEN_MODEL',True),
                                     ('voice_reference','COMPUTER_VOICE_REFERENCE',False),('wake_model','COMPUTER_WAKE_MODEL',False)]:
        path = os.environ.get(variable, '')
        exists = bool(path) and (Path(path).is_dir() if directory else Path(path).is_file())
        checks[name] = {'status': 'DEGRADED' if exists else 'UNAVAILABLE',
                        'message': 'Vorhanden; Integrität/Modellladen noch prüfen.' if exists else variable + ' fehlt oder Pfad nicht vorhanden.'}
    try:
        async with httpx.AsyncClient(timeout=2, trust_env=False, follow_redirects=False) as client:
            r = await client.get('http://127.0.0.1:11434/api/version')
            r.raise_for_status()
        checks['ollama'] = {'status': 'READY', 'message': 'Lokaler Ollama-Dienst antwortet; ausgewähltes Modell separat prüfen.'}
    except Exception as exc:
        checks['ollama'] = {'status': 'UNAVAILABLE', **failure(exc)}
    # Sequential keeps startup RAM load low on the 13 GB target.
    for name in ['pipecat', 'stt', 'qwen', 'wake']:
        checks[name + '_import'] = await import_check(name)
    return checks

"""Bounded metadata probe. No generation, redirects, proxies or arbitrary endpoints."""
import os
from urllib.parse import quote
import httpx


def api_key(session_or_run):
    return session_or_run.api_key or os.environ.get('OPENAI_API_KEY', '')


async def check_provider(provider, key=''):
    if provider.kind == 'demo':
        return {'status': 'SIMULATED', 'message': 'Offline-Demo; keine freie AI-Unterhaltung.'}
    if not provider.model:
        return {'status': 'UNAVAILABLE', 'message': 'Modellnamen eingeben.'}
    if provider.kind == 'openai' and not key:
        return {'status': 'UNAVAILABLE', 'message': 'OpenAI-API-Schlüssel fehlt.'}
    async with httpx.AsyncClient(timeout=8, trust_env=False, follow_redirects=False) as client:
        if provider.kind == 'openai':
            response = await client.get('https://api.openai.com/v1/models/' + quote(provider.model, safe=''),
                                        headers={'Authorization': 'Bearer ' + key})
            response.raise_for_status()
            if response.json().get('id') != provider.model:
                return {'status': 'DEGRADED', 'message': 'Modellantwort unerwartet; Modellname prüfen.'}
        else:
            response = await client.post('http://127.0.0.1:11434/api/show', json={'model': provider.model})
            response.raise_for_status()
            capabilities = response.json().get('capabilities', [])
            if 'tools' not in capabilities:
                return {'status': 'DEGRADED', 'message': 'Ollama-Modell erreichbar; Toolfähigkeit nicht bestätigt. Anderes toolfähiges Modell wählen oder Gespräch testen.'}
    return {'status': 'READY', 'message': 'Modell-Metadaten erreichbar. Echte Antwort und Tools über Testauftrag prüfen; noch nicht VALIDATED.'}

"""Allowlisted metadata only. Never format exception messages, requests or locals."""
from collections import deque
from datetime import datetime, timezone
import re


def identifier(value):
    value = str(value or '')
    if re.search(r'(?i)(sk-|bearer|token|secret|password)', value):
        return '[redacted]'
    return value[:120] if re.fullmatch(r'[\w.:/<>\-]*', value) else '[redacted]'


def failure(exc):
    name = type(exc).__name__
    raw = str(exc).lower()  # Classification only; never retained or emitted.
    status = getattr(exc, 'status_code', None)
    status = status if isinstance(status, int) and 400 <= status <= 599 else None
    code, message = 'internal_error', 'Interner Fehler. Diagnoseansicht öffnen.'
    if 'anwendungssteuerungsrichtlinie' in raw or 'application control' in raw or getattr(exc, 'winerror', None) == 4551:
        code, message = 'windows_policy_block', 'Windows-Anwendungssteuerung blockiert eine native Voice-Komponente. Text bleibt verfügbar.'
    elif 'dll load failed' in raw:
        code, message = 'native_dll_load', 'Native DLL kann nicht geladen werden. Architektur, Paket und Windows-Ereignisprotokoll prüfen.'
    elif isinstance(exc, (ImportError, ModuleNotFoundError)):
        code, message = 'dependency_import', 'Optionale Abhängigkeit fehlt oder kann nicht importiert werden.'
    elif status == 401:
        code, message = 'authentication', 'API-Schlüssel ungültig oder abgelaufen.'
    elif status == 403:
        code, message = 'permission', 'Provider verweigert Zugriff. Projekt- und Modellberechtigungen prüfen.'
    elif status == 404:
        code, message = 'model_missing', 'Modell oder API-Endpunkt nicht gefunden. Modellname prüfen.'
    elif status == 429:
        code, message = 'rate_or_quota', 'Provider-Limit oder Kontingent erreicht. Abrechnung und Rate-Limit prüfen.'
    elif status == 400:
        code, message = 'provider_arguments', 'Provider lehnt Parameter ab. Modell, Toolfähigkeit und Temperatur prüfen.'
    elif status and status >= 500:
        code, message = 'provider_service', 'Provider meldet einen Serverfehler. Später erneut versuchen.'
    elif 'timeout' in name.lower() or isinstance(exc, TimeoutError):
        code, message = 'timeout', 'Zeitlimit erreicht. Dienst, Modellladezeit oder Netzwerk prüfen.'
    elif 'connect' in name.lower():
        code, message = 'connection', 'Dienst nicht erreichbar. Netzwerk oder lokalen Ollama-/LiveKit-Dienst prüfen.'
    elif isinstance(exc, FileNotFoundError):
        code, message = 'file_missing', 'Benötigte lokale Datei oder Modell fehlt.'
    elif isinstance(exc, ValueError):
        code, message = 'invalid_state', 'Eingabe oder aktueller Zustand ungültig. Konfiguration und aktiven Auftrag prüfen.'
    elif isinstance(exc, PermissionError):
        code, message = 'permission', 'Zugriff verweigert.'
    frames = []
    tb = exc.__traceback__
    while tb is not None:
        f = tb.tb_frame
        frames.append({'module': identifier(f.f_globals.get('__name__', 'unknown')),
                       'function': identifier(f.f_code.co_name), 'line': tb.tb_lineno})
        tb = tb.tb_next
    # No filenames/usernames, source lines, exception args, chaining or locals.
    return dict(code=code, message=message, exception_type=identifier(name), http_status=status,
                trace=frames[-20:])


class Diagnostics:
    def __init__(self, diagnosis_id):
        self.id = diagnosis_id
        self.events = deque(maxlen=500)
        self.sequence = 0

    def emit(self, component, event, *, level='INFO', run=None, provider=None, error=None):
        self.sequence += 1
        p = run.provider if run else provider
        row = dict(sequence=self.sequence, time=datetime.now(timezone.utc).isoformat(),
                   level=level, component=identifier(component), event=identifier(event),
                   diagnosis_id=self.id, run_id=run.id if run else None,
                   provider=p.kind if p else None, model=identifier(p.model) if p else None)
        if error is not None:
            row['error'] = failure(error)
        self.events.append(row)
        return row

    def export(self):
        return {'diagnosis_id': self.id, 'events': list(self.events),
                'privacy': 'Metadaten; keine Inhalte, Argumente, Credentials oder rohe Exception-Texte.'}

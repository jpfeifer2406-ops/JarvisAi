# Auftrag 002 — Prototyp A: pausierter Zwischenstand

Stand: 20. September 2026. Auf ausdrücklichen Wunsch des Captains gesichert und pausiert.
**Unfertiger Implementierungsentwurf, nicht startfähig, nicht sicherheitsvalidiert.**

## Verbindlicher Umfang

Nur Prototyp A: eigener COMPUTER-Kern, OpenAI Agents SDK, Pipecat, LiveKit.
Prototyp B/Pydantic AI erst nach gesondertem Auftrag. Kein Sieger vor Vergleich.
Branch: `prototype-computer-openai`, Referenz `feature-v0.6.0` bei
`7701906c30d28249e6c60a42203580494de0e22b`. main und Referenz bleiben unverändert.
Kein Merge ohne ausdrückliche Freigabe.

Aktuelle Stimmentscheidung ersetzt Victoria als Ziel: Qwen3-TTS Voice Design,
German, ausschließlich weiblich, keine Stimmwahl im Prototyp.
Der Captain hat eine generierte Hörprobe audio.wav im Gespräch bereitgestellt.
Sie liegt nicht im Git-Checkpoint. Genaue Modellrevision/Seed noch unbekannt;
identische Reproduktion ist nicht belegt.

Stil-Prompt:

> Speak in clear, natural German with a calm, composed, and matter-of-fact delivery. Use a smooth, slightly lower-pitched female voice with subtle warmth and quiet confidence. Keep the pacing measured but conversational, with precise articulation and short, natural pauses. Sound like an attentive, highly competent computer assistant aboard a research spacecraft. Use restrained intonation without sounding flat or robotic. Avoid panic, disbelief, dramatic emphasis, breathiness, and exaggerated cheerfulness.

## Vorhandener Code (IMPLEMENTED als Entwurf, nicht TESTED)

- `contracts.py`: strikte Toolresultate, Risikoklassen, Provider- und Run-Verträge, Agent-Port.
- `broker.py`: asynchrone, sitzungs-/aktionsgebundene einmalige Freigaben, Argument-Digest,
  genaue Bestätigungsphrasen, Ablaufzeit und Stornierung.
- `documents.py`: neue UUID-Entwürfe, TXT/DOCX/PDF, kanonischer Volltext,
  Integritätsprüfung, Revision als neue Kopie.
- `network.py`: öffentliche HTTPS-Lesezugriffe, Prüfung im DNS-Resolver,
  gesperrte Redirects/Proxies/private Adressen.
- `tools.py`: zentraler Broker-Dispatch, Schema-/Resultatprüfung, Dokument-/News-/
  Browser-/Drive-Verträge und ausdrücklich simulierte Geräte-/Freigabeproben.
- `integrations.py`: RSS-Leseentwurf, explizit geteilter Tab mit Ablaufzeit,
  Drive-Reader-Schnittstelle ohne OAuth-Implementierung.
- `memory.py`: ausschließlich explizite strukturierte Sitzungsvorlieben;
  keine freie Langzeit-Memory und kein automatisches Speichern von Gesprächen.
- `pyproject.toml`, lokales `.gitignore`, Paketmarker.

Kein bestehender Jarvis-Code geändert oder zur Laufzeit importiert.
Das alte Dateibaum-Erbe bleibt lediglich Referenz im Branch.

## Tatsächlich geprüft

In einer separaten temporären Python-3.12-Umgebung installiert:
OpenAI Agents SDK 0.22.3, Pipecat 1.11.0, LiveKit API 1.2.1,
FastAPI 0.141.1, Uvicorn 0.53.0 und Testwerkzeuge.
SDK-Signaturen von Runner.run, FunctionTool und Model.get_response sowie
Pipecat-Audioframes und LiveKitTransport per Import inspiziert.
Das bestätigt nur deren Import-/Schnittstellenverfügbarkeit in dieser Umgebung.

Keine Regressionstests geschrieben oder ausgeführt, kein Anwendungsstart,
keine echten Provider-, Voice-, OAuth-, LiveKit- oder Windows-Gerätetests.
Keine Credentials verwendet. Keine Hardwarevalidierung.

## Noch offen / nächster Wiedereinstieg

1. Vorhandenen Entwurf reviewen und gemeinsame Regressionstests erstellen.
   Broker-Races, Abbruch/Resume, Sitzungsgrenzen, Toolargumente/-resultate,
   URL-Bypässe und Dokumentintegrität zuerst absichern.
2. Session-/Job-Laufzeit und authentifizierte API implementieren. Origin/CSRF,
   unabhängiger Stop-Kanal, Session-Ablauf und Ressourcenlimits fehlen noch.
3. OpenAI-Agents-Adapter mit echter SDK-Ausführung, Providerwechsel und
   Pause/Resume; keine Autorisierung durch das Modell oder Framework selbst.
4. Voice-Zustandsmaschine und Pipecat/LiveKit-Adapter; Wake, STT, Qwen-TTS,
   Playback, Barge-in, eindeutiger Audio-Owner und Recovery.
5. Cockpit, Settings, Browser-Erweiterung, Drive Read-only OAuth und
   Windows-Startanleitung vervollständigen.
6. Vollständige Funktionsmatrix, Tests/CI, Screenshots und Abschlussbericht.
   IMPLEMENTED/TESTED/VALIDATED/PLANNED strikt auseinanderhalten.

Bekannte Grenzen dieses Zwischenstands: Dokument-Rendering läuft noch synchron,
keine vollständige Unicode-PDF-Abdeckung zugesichert, kein Resource-/Quota-Konzept,
keine persistente Job-/Approval-Wiederaufnahme, keine isolierte Python-Ausführung
(auch kein run_python registriert). Direkte Abhängigkeiten teilweise festgelegt,
aber kein vollständiger Lock und Voice-Extras noch nicht installiert/verifiziert.
Der konfigurierte CLI-Einstieg verweist auf ein noch fehlendes __main__.py.

Fortsetzen ausschließlich nach neuem Signal des Captains.

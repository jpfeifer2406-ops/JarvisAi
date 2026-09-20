# COMPUTER · Prototyp A

Experimenteller eigener COMPUTER-Kern mit **OpenAI Agents SDK + Pipecat + LiveKit**.
Kein Release, kein Merge, keine Hardwarevalidierung. Prototyp B ist nicht implementiert.

Der frühere Jarvis-Dateibaum im Repository ist ausschließlich eingefrorene Referenz.
**Nicht `start.bat` oder `install.bat` im Repository-Stamm verwenden.**
Dieser Prototyp liegt vollständig unter `prototypes/openai` und importiert kein `jarvis.*`.

## Schnellstart: prüfbarer Text-/Cockpitbetrieb

Python 3.12 empfohlen (unterstützt 3.11–3.12). In PowerShell:

```powershell
cd prototypes/openai
./start.ps1
```

Alternativ ohne PowerShell-Skript:

```text
cd prototypes/openai
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test,transport]"
.venv\Scripts\python -m computer
```

Linux/macOS: `.venv/bin/python` statt `.venv\Scripts\python` verwenden.
`http://127.0.0.1:7861` öffnen und den **lokal angezeigten Zugangscode** eingeben.
Dieser Code ist ein Credential, kein öffentlicher Link. Nicht in Issues/Logs posten.
COMPUTER startet ausdrücklich in **Offline-Demo**, ohne kostenpflichtige API-Aufrufe.

Die Demo verwendet den echten SDK-Runner mit einem deterministischen Modelladapter.
`/entwurf`, `/dokumente`, `/execute`, `/critical`, `/news`, `/browser`, `/drive` sind
Demo-Befehle; freie Sprach-/Textgespräche benötigen einen konfigurierten LLM-Provider.
News benötigt Internet. EXECUTE/CRITICAL-Proben haben keine externe Wirkung.

## Provider

- **OpenAI:** `OPENAI_API_KEY` vor dem Start im lokalen Prozess setzen, im Cockpit
  OpenAI und einen tatsächlich verfügbaren Modellnamen auswählen. Schlüssel werden
  nicht an das Cockpit ausgegeben. Keine automatische Modellwahl oder Ausgabenfreigabe.
- **Lokal:** Ollama mit OpenAI-kompatibler Chat-Completions-Schnittstelle unter
  `http://127.0.0.1:11434/v1`, expliziter Modellname. Toolfähigkeit des Modells muss
  praktisch geprüft werden. Keine beliebigen Endpoint-URLs aus UI/LLM-Argumenten.
- Providerwechsel nur ohne aktiven Auftrag; alter Gesprächskontext wird nicht an den
  neuen Provider weitergegeben. Pro Run neuer Client, auch nach Key-Rotation.
- Modellabhängige Unterstützung von Temperatur/Tools bleibt ein Live-Test.

## Was ausprobiert werden kann

1. Nachricht oder Demo-Befehl senden.
2. Werkstatt: TXT, DOCX oder PDF erstellen und herunterladen; Revision erstellt neue Kopie.
3. EXECUTE-/CRITICAL-Test: Argumente sehen, exakte Phrase eingeben oder ablehnen.
4. Pause anfordern, Fortsetzen, Stop oder Escape. Pause greift am nächsten Kontrollpunkt;
   laufende I/O wird dadurch nicht nachträglich angehalten. Stop cancelt den Auftrag.
5. Zweiten Browserkontext separat anmelden und Sitzungsisolation prüfen.
6. In Einstellungen strukturierte Sitzungsvorlieben setzen.
7. Browser-Erweiterung aus `browser_extension/` als entpackte Erweiterung laden,
   im Cockpit Kopplungscode erzeugen, im Popup einen HTTPS-Tab explizit teilen.

## Voice: optionaler experimenteller Hardwarepfad

Die weibliche deutsche Qwen-Stimme ist das Ziel; **Victoria ist nicht Standard und
kein männlicher Voice-Modus ist vorgesehen**. Profil: `computer/profiles/voice.json`.
Die vom Captain bestätigte Hörprobe ist eine separate Gesprächsanlage; keine Stimme
wird hier aus einer anderen Quelle ersetzt. Keine Reproduktionsgarantie ohne Test.

Installieren (große optionale Modellabhängigkeiten, bewusst nicht beim Textstart):

```text
python -m pip install -e ".[voice,qwen,transport]"
```

Modelle lokal bereitstellen und Operator-Umgebung setzen:

| Variable | Bedeutung |
|---|---|
| `COMPUTER_STT_MODEL` | Lokales faster-whisper-Modellverzeichnis; Deutsch, CPU/int8 |
| `COMPUTER_QWEN_MODEL` | Lokales Qwen3-TTS VoiceDesign-Modell; mit Referenz stattdessen Base-Modell |
| `COMPUTER_VOICE_REFERENCE` | Optionaler lokaler Pfad zu Captains bestätigter weiblicher audio.wav |
| `COMPUTER_VOICE_DEVICE` | `cpu` Standard, optional getestetes CUDA-Gerät |
| `COMPUTER_VOICE_PYTHON` | Optional eigener Python-Interpreter mit Paket und Voice-Dependencies |
| `COMPUTER_WAKE_MODEL` | Lokaler `computer_v2.onnx` mit Prüfsumme aus Voice-Profil |
| `LIVEKIT_URL` | Lokaler LiveKit-Server `ws://127.0.0.1:7880` oder ausdrücklich konfiguriertes WSS |
| `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | Lokale Server-Credentials; nicht in Dateien/Chat eintragen |

Wake-Modellquelle der Referenz:
https://github.com/fwartner/home-assistant-wakewords-collection/blob/8bcd2f20bb7b76c351b2eff871fa1ce873fe9be2/en/computer/computer_v2.onnx
Trainingsdaten-/kommerzielle Lizenzfreigabe ist weiterhin offen. openWakeWord benötigt
zusätzlich seine Feature-Modelle; deren Installation ist Teil des offenen Hardware-Setups.
Keine Modelldownloads werden durch den COMPUTER-Start automatisch durchgeführt.

Im Cockpit **Mikrofon verbinden**, Browserrecht erlauben, `Computer` sagen oder
**Sprechen** anklicken. Browser → LiveKit → Pipecat → COMPUTER-Wake/Aufnahme → STT →
Agents SDK/Broker → Qwen-TTS → Pipecat/LiveKit → Browser. Spracheingaben genehmigen
keine kritischen Aktionen; Freigaben erfolgen im authentifizierten Cockpit.
`Ruhemodus` beendet die aktive Sprachsitzung; nach 120 Sekunden Leerlauf erneut Wake.
**Stop trennt im Browser zusätzlich das Audio**, sodass kein gepufferter Ton weiterläuft.

Qwen-Inferenz läuft in abbrechbaren Hilfsprozessen. Das ist keine Python-Sandbox.
Modelle und Referenzprompt bleiben zwischen normalen Turns im warmen Hilfsprozess;
nach Stop während Inferenz wird neu geladen. Streaming-Optimierung folgt nach Messungen. Energie-basierte Aufnahme/Barge-in ist ein
experimenteller Fallback, kein akustisch validiertes VAD-/Echo-Konzept. Headset empfohlen
für den ersten Test; keine Latenz- oder Echofreiheitszusage.

## Google Drive (nur lesend)

```text
python -m pip install -e ".[drive]"
python -m computer.adapters.drive authorize PFAD_ZUR_EIGENEN_DESKTOP_OAUTH_JSON
```

Expliziter Browser-OAuth, Scope `drive.readonly`. Token ausschließlich im unterstützten
OS-Credential-Store (Windows/macOS/SecretService), kein Klartext-Fallback. Anschließend
im Cockpit Dateien lesen. Entfernen: `python -m computer.adapters.drive forget`.
Kein Upload, Löschen oder sonstiger Drive-Schreibzugriff. Auth/Refresh noch nicht live geprüft.

## Sicherheit und Daten

Ein lokaler Prozess/Worker. Keine Mehrprozessbereitstellung, kein öffentliches Hosting.
Die lokalen Sitzungen gehören dem Operator, der den Zugangscode besitzt. Nicht als
Mandantensystem einsetzen. Session-Cookies HttpOnly/SameSite Strict, Origin/Host-Prüfung,
kein CORS-Wildcard, keine WebSocket-Steuerung mit ungeschütztem Receive-Loop.
LiveKit-Tokens sind auf einen Sitzungsraum und Mikrofon-Audio beschränkt und ersetzen
keine COMPUTER-Anmeldung oder Toolfreigabe.

Dokumente liegen unter `.runtime/<session>/documents`. Sie werden nicht automatisch
beim Logout gelöscht, sind nach neuer Sitzung aber nicht automatisch wieder im Cockpit
zugeordnet. **Wichtige Entwürfe herunterladen.** Persistente Benutzerbibliothek und
Wiederherstellung sind noch offen. Gesprächshistorie, Freigaben und Präferenzen sind
nur im RAM. Dateiverschlüsselung/Windows-ACL-Härtung sind nicht implementiert.
Kein beliebiges `run_python`, keine generische Desktop-Automation, kein Finanz-/Kauf-/
Rechtsabschluss. Geräteeffekte sind als `simulated` gekennzeichnet.

## Prüfen

```text
python -m pytest -q
python -m ruff check computer tests
node --check computer/static/app.js
```

Tests verwenden synthetische Daten, echten SDK-Runner und Pipecat-Frameverträge,
aber keine API-Schlüssel oder realen Geräte. Bericht: `docs/REPORT.md`.

## Captains Hardwareprofil (20.09.2026)

Gemeldet: **AMD Ryzen 5 PRO 3500U, Radeon Vega 8, ca. 13 GB nutzbarer RAM**.
`start-ryzen.ps1` setzt einen CPU-Ausgangspunkt mit zwei Inferenzthreads. Keine CUDA-
oder ungetestete AMD-GPU-Abhängigkeit. Zunächst faster-whisper base/int8, beam 1;
falls gemessen zu langsam, tiny als Vergleich. Qwen3-TTS **0.6B Base** mit der bestätigten
weiblichen Hörprobe ist der kleinere Kandidat; kein automatischer Wechsel zu einer
anderen Stimme. Hörprobe lokal als `.runtime/voice-reference.wav` bereitstellen.

Der Speech-Hilfsprozess hält Modelle und Referenzprompt zwischen normalen Turns warm.
Stop während Inferenz beendet den Prozess vollständig; der nächste Turn lädt neu.
Gesprochene Antworten sind auf 600 Zeichen begrenzt, der vollständige Text bleibt im
Cockpit. Modellpfade im Ryzen-Starter sind Konventionen, keine automatischen Downloads.
Der genannte RAM ist keine zugesicherte freie Laufzeitreserve. Gleichzeitiger Browser,
LLM und TTS müssen unter Last gemessen werden. Es gibt noch **keine gemessene Echtzeit-
 oder Klanggarantie** auf diesem Gerät.

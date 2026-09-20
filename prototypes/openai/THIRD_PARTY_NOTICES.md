# Drittkomponenten — Prototyp A

Keine neue Lizenz für den gesamten bestehenden Fork wird mit diesem Experiment erklärt.
Der alte Jarvis-Dateibaum bleibt unverändert, wird aber nicht vom neuen Paket importiert.
Die kommerzielle Gesamtfreigabe ist ausdrücklich offen.

| Komponente | Version / Lizenzbasis | Verwendung |
|---|---|---|
| OpenAI Agents SDK | 0.22.3 / MIT | Agentenadapter |
| OpenAI Python | 3.16.2 / Apache-2.0 | Providerclient |
| Pipecat | 1.11.0 / BSD-2-Clause | Voice-Pipeline |
| LiveKit Python API | 1.2.1 / Apache-2.0 | Audio-Raumtoken |
| LiveKit JS Client | 2.22.3 / Apache-2.0 | Lokal vendored Browsertransport |
| Qwen3-TTS | qwen-tts 0.1.1 / Apache-2.0 Projektbasis | Optionale lokale TTS; Gewichte nicht enthalten |
| openWakeWord | 0.6.0 / Apache-2.0 Code | Optionaler Wake-Adapter; Modellrechte separat |
| Computer-v2-ONNX | fixierte v0.6.0-Prüfsumme | Nicht enthalten; Provenienz/kommerzielle Rechte offen |

Die Lizenz der vendorten LiveKit-JS-Datei liegt unverändert unter
`computer/static/livekit-client.LICENSE`. Quelle: npm-Paket livekit-client@2.22.3,
Datei dist/livekit-client.umd.js. Keine externen CDN-Laufzeitimporte.

Weitere Python-Abhängigkeiten werden durch pip bezogen, nicht als Quellcode kopiert.
Für eine Distribution müssen vollständiger SBOM-/Lizenz-/Modellreview und die
jeweiligen Noticepflichten erfüllt werden. Paket- und Modelllizenz sind getrennt zu prüfen.

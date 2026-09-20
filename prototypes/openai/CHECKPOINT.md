# Auftrag 002 — Fortsetzungsstand, 20.09.2026

Der Captain hat nach der Sicherungsbitte ausdrücklich Fortsetzung angeordnet.
Nur Prototyp A, keine Änderungen an main/feature-v0.6.0, kein Merge.

## Verbindliche Entscheidungen

OpenAI Agents SDK + Pipecat + LiveKit; eigener COMPUTER-Broker.
Weibliche Qwen-Stimme, Prompt unter computer/profiles/voice.json; bestätigte audio.wav
liegt als Gesprächsanlage vor, nicht im Repository. Hardware: Ryzen 5 PRO 3500U,
Vega 8, ca. 13 GB nutzbarer RAM. CPU-Profil mit zwei Threads, faster-whisper base/int8,
Qwen3-TTS 0.6B Base mit weiblicher Referenz als kleinerer Kandidat.

## Stand

Kern, API, SDK-Adapter, Cockpit, Dokumente, Browser-Erweiterung, Drive-Read-only-Adapter,
Voice-/LiveKit-Adapter und Windows-Starter geschrieben. Kein Jarvis-Laufzeitimport.
Letzter abgeschlossener Testlauf: 46 Tests bestanden, vor der neuesten Warmworker-
Optimierung. Echte SDK-HITL/Resume- und synthetische Pipecat-Frame-Tests eingeschlossen.
Aktuelle Python-Syntax geparst. Die neue Warmworker-/Ryzen-Konfiguration noch nicht
vollständig nachgetestet. Keine echten Provider-, OAuth-, Voice-/Hardwaretests.

## Nächste konkrete Schritte

1. Warmworker-Cancellation, Prozess-Cleanup und Wiederanlauf testen; Profile/README/Report
   mit der neuesten Änderung synchronisieren. Kein Pro-Turn-Neuladen mehr im Normalfall.
2. Ruff, pytest und JS-Syntaxchecks erneut durchführen. UI über lokalen Testserver
   starten, Freigabe/Dokumentworkflow im Browser prüfen; Screenshots fehlen noch.
3. GitHub-Experiment aktualisieren und neue CI lesen. Referenzbranch unverändert prüfen.
4. Hardware-Setup/Modellpfade/Referenzdatei mit Captain testen; keine Echtzeitgarantie.
5. Abschlussbericht mit ehrlichen Funktions-/Validierungsgrenzen, keine Siegerwahl.

README.md und docs/REPORT.md enthalten Startanleitung und ausführliche Grenzen.
Report kann bei Warmworker/Hardwareabschnitten noch den Voränderungsstand enthalten.
Temporäre Browser-Testdownloads und Python-Umgebung gehören nicht in Git.

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
Letzter abgeschlossener Testlauf: 48 Tests bestanden, einschließlich Warmworker-
Wiederverwendung, Cancel und Wiederanlauf mit synthetischem Hilfsprozess. Echte SDK-HITL/Resume- und synthetische Pipecat-Frame-Tests eingeschlossen.
Aktuelle Python-Syntax geparst. Warmworker-Kontrollfluss nachgetestet; echte Modell-
Performance des Ryzen-Profils noch nicht gemessen. Keine echten Provider-, OAuth-, Voice-/Hardwaretests.

## Nächste konkrete Schritte

1. Warmworker-Kontrollfluss und UI bereits geprüft. Keine erneute Modellinstallation
   ohne Bedarf; konkrete Restgrenzen im Report beachten.
2. Letzte Checks und GitHub-CI abschließen. Browserprüfung erfolgreich, Screenshots
   liegen unter docs/. Keine Hardwarevalidierung aus UI-Tests ableiten.
3. GitHub-Experiment aktualisieren und neue CI lesen. Referenzbranch unverändert prüfen.
4. Hardware-Setup/Modellpfade/Referenzdatei mit Captain testen; keine Echtzeitgarantie.
5. Abschlussbericht mit ehrlichen Funktions-/Validierungsgrenzen, keine Siegerwahl.

README.md und docs/REPORT.md enthalten Startanleitung und ausführliche Grenzen.
Report wurde für Warmworker und gemeldete Hardware nachgeführt.
Temporäre Browser-Testdownloads und Python-Umgebung gehören nicht in Git.

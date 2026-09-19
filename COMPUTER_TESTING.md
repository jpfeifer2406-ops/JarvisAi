# COMPUTER v0.5.1 TEST

This branch is a real modification of the forked **PanPenek/JarvisAi** codebase.
The internal Python package remains named `jarvis` intentionally so upstream
updates can still be compared and rebased cleanly.

## What this test build changes

- visible identity: COMPUTER
- Captain persona and German default language
- German faster-whisper transcription
- original JarvisAi Kokoro voice remains active (`af_heart`)
- original JarvisAi HUD structure retained, visually redesigned as the COMPUTER cockpit
- one wake activation opens an active multi-turn voice session
- follow-up speech no longer needs another wake word
- `Ruhemodus` returns immediately to standby
- 120 seconds without follow-up speech returns to standby
- Downloads added to allowed file roots
- provider API keys are no longer returned by the provider-list API
- read-only diagnostics script added

## Temporary wake word

For this test build the wake detector intentionally remains the original
openWakeWord model:

**Hey Jarvis**

This is temporary. Renaming the text in the UI would not create a working
`Computer` wake model. The next wake-word task is a real keyword model for
`Computer`.

## Install

On Windows PowerShell:

```powershell
git clone https://github.com/jpfeifer2406-ops/JarvisAi.git
cd JarvisAi
git checkout computer-test
install.bat
```

If the repository is already cloned:

```powershell
git checkout computer-test
git pull
```

Then run:

```powershell
start.bat
```

Cockpit:

`http://localhost:7860`

## Voice test

1. Say **Hey Jarvis**
2. COMPUTER should answer **Bereit, Captain.**
3. Ask a normal question in German.
4. After COMPUTER answers, speak another sentence without saying Hey Jarvis again.
5. Say **Ruhemodus**.
6. The cockpit should return to **STANDBY**.
7. Repeat activation.
8. Leave the session silent for two minutes; it should return to standby.

## Diagnostics

Run:

```powershell
diagnose.bat
```

The report is written to:

`computer_diagnostics.txt`

The diagnostics intentionally do **not** print API keys.

## Known test limitations

- the exact `Computer` wake word is not yet implemented
- Kokoro's upstream voice is being tested as requested; German pronunciation quality must be evaluated on the target PC
- microphone, speaker, CUDA/CPU fallback and wake-word behavior require real Windows hardware testing
- the full READ / PREPARE / EXECUTE / CRITICAL approval broker is not yet enforced for every upstream JarvisAi tool; use this experimental branch only for controlled testing and do not authorize destructive actions
- upstream package/module names may still contain `jarvis`; these are internal compatibility names, not the product identity

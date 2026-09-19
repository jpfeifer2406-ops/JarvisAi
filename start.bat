@echo off
title COMPUTER v0.6.0 TEST
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo [COMPUTER] Virtual environment not found.
  echo Run install.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
echo.
echo  ============================================
echo   COMPUTER v0.6.0 TEST - CPU Profile
echo  ============================================
echo   Wake word:           COMPUTER
echo   Active session:      120 seconds
echo   End session:         RUHEMODUS
echo   Voice:               Victoria German / CPU
echo   STT:                 faster-whisper base / CPU int8
echo   Input panel:         "Eingabe oeffnen" or F2
echo   Settings:            gear icon or "Einstellungen oeffnen"
echo   Creative workshop:   "Werkstatt oeffnen"
echo   Call overlay:        "Anrufmodus oeffnen"
echo   Web cockpit:         http://localhost:7860
echo.
python -m jarvis.main
pause

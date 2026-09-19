@echo off
title COMPUTER v0.5.2 TEST
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
echo   COMPUTER v0.5.2 TEST - JarvisAi Fork
echo  ============================================
echo   Temporary wake word: HEY JARVIS
echo   Active session:      120 seconds
echo   End session:         RUHEMODUS
echo   Voice:               Victoria (German, experimental)
echo   Input panel:         "Eingabe oeffnen" or F2
echo   Web cockpit:         http://localhost:7860
echo.
python -m jarvis.main
pause

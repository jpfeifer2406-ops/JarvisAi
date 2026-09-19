@echo off
title COMPUTER Diagnostics
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo [COMPUTER] Virtual environment not found. Run install.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python computer_doctor.py
echo.
echo Copy computer_diagnostics.txt into the chat if something fails.
pause

@echo off
setlocal EnableExtensions
title COMPUTER Updater
cd /d "%~dp0"

echo.
echo  ============================================
echo   COMPUTER - Single Folder Update
echo  ============================================
echo.

where git >nul 2>nul
if %errorlevel% neq 0 (
  echo [ERROR] Git is not available in PATH.
  pause
  exit /b 1
)

git status --porcelain >nul 2>nul
if %errorlevel% neq 0 (
  echo [ERROR] This folder is not a Git clone.
  pause
  exit /b 1
)

git diff --quiet
if %errorlevel% neq 0 (
  echo [ERROR] Tracked files contain local changes.
  echo Review or stash them before updating. Runtime settings and workspace files are ignored automatically.
  pause
  exit /b 1
)
git diff --cached --quiet
if %errorlevel% neq 0 (
  echo [ERROR] Staged local changes detected. Commit or stash them before updating.
  pause
  exit /b 1
)

echo [1/3] Updating current branch...
git pull --ff-only
if %errorlevel% neq 0 (
  echo [ERROR] Git update stopped. Local changes may need review.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
  echo [INFO] No virtual environment yet. Run install.bat once.
  pause
  exit /b 0
)

echo [2/3] Activating existing environment...
call .venv\Scripts\activate.bat

echo [3/3] Synchronizing dependencies without deleting the environment...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
  echo [ERROR] Dependency update failed.
  pause
  exit /b 1
)

echo.
echo [OK] COMPUTER updated in this same folder.
echo Start with: start.bat
echo.
pause

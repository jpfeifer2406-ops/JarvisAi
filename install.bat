@echo off
setlocal EnableExtensions
title COMPUTER v0.6.0 TEST Installer
cd /d "%~dp0"

echo.
echo  ============================================
echo   COMPUTER v0.6.0 TEST - JarvisAi Fork
echo  ============================================
echo.
echo  Kokoro currently requires Python 3.11 or 3.12.
echo  Python 3.13/3.14 cannot be used for this test build.
echo.

set "PYTHON_CMD="

where py >nul 2>nul
if %errorlevel%==0 (
    py -3.12 -c "import sys; print(sys.version)" >nul 2>nul
    if %errorlevel%==0 set "PYTHON_CMD=py -3.12"
    if not defined PYTHON_CMD (
        py -3.11 -c "import sys; print(sys.version)" >nul 2>nul
        if %errorlevel%==0 set "PYTHON_CMD=py -3.11"
    )
)

if not defined PYTHON_CMD (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Compatible Python not found.
    echo Install Python 3.12 x64 from python.org, then run install.bat again.
    echo Do not use Python 3.13 or 3.14 for this build because Kokoro does not support them yet.
    pause
    exit /b 1
)

echo [OK] Using: %PYTHON_CMD%
echo.

if exist ".venv" (
    echo [INFO] Removing incomplete virtual environment...
    rmdir /s /q ".venv"
)

echo [1/4] Creating virtual environment...
%PYTHON_CMD% -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/4] Activating environment...
call .venv\Scripts\activate.bat

echo [3/4] Installing dependencies (this may take a few minutes)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [4/4] Preparing lightweight wake-word runtime...
python -c "import openwakeword, os, urllib.request; d=os.path.join(os.path.dirname(openwakeword.__file__),'resources','models'); os.makedirs(d,exist_ok=True); [urllib.request.urlretrieve('https://github.com/dscripka/openWakeWord/raw/main/openwakeword/resources/models/'+f, os.path.join(d,f)) for f in ['melspectrogram.onnx','embedding_model.onnx'] if not os.path.exists(os.path.join(d,f))]" 2>nul

echo.
echo  ============================================
echo   Installation complete!
echo  ============================================
echo.
echo  Start COMPUTER with: start.bat
echo  Web cockpit: http://localhost:7860
echo  Wake word: Computer
echo  Default TTS: German Victoria / CPU
 echo  COMPUTER downloads the small custom Computer wake model on first start.
echo.
pause

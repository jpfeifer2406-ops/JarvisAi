$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 und venv werden benötigt.' }
    & .venv\Scripts\python.exe -m pip install -e '.[test,transport]'
    if ($LASTEXITCODE -ne 0) { throw 'Installation fehlgeschlagen. Umgebung bleibt zur Diagnose erhalten.' }
}
& .venv\Scripts\python.exe -m computer
if ($LASTEXITCODE -ne 0) { throw 'COMPUTER wurde mit einem Fehler beendet.' }

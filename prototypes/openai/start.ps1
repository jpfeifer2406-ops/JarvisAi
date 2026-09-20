$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 und venv werden benötigt.' }
}
$projectHash = (Get-FileHash 'pyproject.toml' -Algorithm SHA256).Hash
$stampPath = '.venv\computer-core.sha256'
$installedHash = if (Test-Path $stampPath) { (Get-Content $stampPath -Raw).Trim() } else { '' }
if ($installedHash -ne $projectHash) {
    & .venv\Scripts\python.exe -m pip install -e '.'
    if ($LASTEXITCODE -ne 0) { throw 'Installation fehlgeschlagen. Umgebung bleibt erhalten; nächster Start versucht erneut.' }
    Set-Content -Path $stampPath -Value $projectHash
}
& .venv\Scripts\python.exe -m computer
if ($LASTEXITCODE -ne 0) { throw 'COMPUTER wurde mit einem Fehler beendet.' }

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:COMPUTER_VOICE_DEVICE = 'cpu'
$env:COMPUTER_CPU_THREADS = '2'
$env:OMP_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:TOKENIZERS_PARALLELISM = 'false'
if (-not $env:COMPUTER_STT_MODEL) { $env:COMPUTER_STT_MODEL = Join-Path $PSScriptRoot 'models\faster-whisper-base' }
if (-not $env:COMPUTER_QWEN_MODEL) { $env:COMPUTER_QWEN_MODEL = Join-Path $PSScriptRoot 'models\qwen3-tts-0.6b-base' }
if (-not $env:COMPUTER_VOICE_REFERENCE) { $env:COMPUTER_VOICE_REFERENCE = Join-Path $PSScriptRoot '.runtime\voice-reference.wav' }
& "$PSScriptRoot\start.ps1"

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend virtual environment not found. Follow docs/DEMO_RUNBOOK.md first."
}
& $python (Join-Path $PSScriptRoot "bootstrap_demo.py")
Write-Host "Open two terminals and use the startup commands printed above."

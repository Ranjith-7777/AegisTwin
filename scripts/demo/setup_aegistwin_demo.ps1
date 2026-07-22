param(
    [switch]$SkipFrontendInstall, [switch]$SkipBackendInstall,
    [switch]$InstallPlaywright, [switch]$ForceReinstall, [switch]$NonInteractive
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "demo_common.ps1")
$paths = Initialize-DemoDirectories
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) { throw "Python 3.11-3.14 is required." }
$node = Get-CommandVersion "node" @("--version")
$npm = Get-CommandVersion "npm.cmd" @("--version")
if (-not $node -or -not $npm) { throw "Node.js 20-24 and npm are required." }
$venv = Join-Path $paths.Root "backend\.venv\Scripts\python.exe"
if ($ForceReinstall -and (Test-Path $venv) -and -not $NonInteractive) {
    $answer = Read-Host "Recreate the backend virtual environment? Type YES"
    if ($answer -ne "YES") { throw "Setup cancelled." }
}
if (-not $SkipBackendInstall) {
    if (-not (Test-Path $venv)) { & $pythonCommand.Source -m venv (Join-Path $paths.Root "backend\.venv") }
    & $venv -m pip install -r (Join-Path $paths.Root "backend\requirements-dev.txt")
    if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }
}
if (-not $SkipFrontendInstall) {
    Push-Location (Join-Path $paths.Root "frontend")
    try { npm.cmd install; if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." } }
    finally { Pop-Location }
}
if ($InstallPlaywright) {
    Push-Location (Join-Path $paths.Root "frontend")
    try { npm.cmd exec playwright install chromium; if ($LASTEXITCODE -ne 0) { throw "Playwright installation failed." } }
    finally { Pop-Location }
}
Write-Host "AegisTwin demo setup complete. No administrator privileges were used."
Write-Host "Next: START_AEGISTWIN_DEMO.bat"

param(
    [ValidateSet("Development", "Production")][string]$Mode = "Production",
    [int]$BackendPort = 8000, [int]$FrontendPort = 5173,
    [switch]$NoBrowser, [switch]$Reset, [switch]$SkipModelBootstrap,
    [ValidateSet("overview", "digital-twin", "response-centre", "response-operations", "audit-trail")]
    [string]$OpenPage = "overview"
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "demo_common.ps1")
$launched = @()
try {
    $requirements = Assert-DemoPrerequisites
    $paths = Initialize-DemoDirectories
    $existing = Read-DemoProcesses
    if (($existing -and (Test-RecordedProcess $existing.backend)) -or ($existing -and (Test-RecordedProcess $existing.frontend))) {
        throw "An AegisTwin demo is already running. Use STATUS_AEGISTWIN_DEMO.bat or STOP_AEGISTWIN_DEMO.bat."
    }
    if ($Reset) { & (Join-Path $PSScriptRoot "reset_aegistwin_demo.ps1") -Force -SkipModelBootstrap:$SkipModelBootstrap }
    if (-not (Test-PortAvailable $BackendPort)) { throw "Backend port $BackendPort is unavailable. Choose -BackendPort; the unknown listener was not stopped." }
    if (-not (Test-PortAvailable $FrontendPort)) { throw "Frontend port $FrontendPort is unavailable. Choose -FrontendPort; the unknown listener was not stopped." }
    Write-DemoLog "Starting $Mode demo on backend $BackendPort and frontend $FrontendPort."
    $env:DATABASE_URL = "sqlite:///$($paths.Database.Replace('\','/'))"
    $env:MODEL_ARTIFACT_DIR = $paths.Artifacts
    $env:SIMULATION_ONLY = "true"; $env:DEMO_MODE = "true"; $env:ENVIRONMENT = "demo"
    $env:DEBUG = "false"; $env:BACKEND_HOST = "127.0.0.1"; $env:BACKEND_PORT = "$BackendPort"
    $env:CORS_ORIGINS = "http://127.0.0.1:$FrontendPort"
    $env:VITE_API_BASE_URL = "http://127.0.0.1:$BackendPort"
    $env:VITE_WS_BASE_URL = "ws://127.0.0.1:$BackendPort"
    $env:VITE_DEMO_MODE = "true"; $env:VITE_DEPLOYMENT_ENV = "local-demo"
    $env:AEGISTWIN_BUILD_MODE = $Mode.ToLowerInvariant()
    $commit = git -C $paths.Root rev-parse --short HEAD 2>$null
    if ($LASTEXITCODE -eq 0) { $env:AEGISTWIN_GIT_COMMIT = $commit }
    if (-not $SkipModelBootstrap) {
        $bootstrap = Start-Process -FilePath $requirements.Python -ArgumentList @((Join-Path $PSScriptRoot "bootstrap_demo_model.py"), "--database", $paths.Database, "--artifacts", $paths.Artifacts) -WorkingDirectory $paths.Root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $paths.Logs "bootstrap.log") -RedirectStandardError (Join-Path $paths.Logs "bootstrap-error.log") -Wait -PassThru
        if ($bootstrap.ExitCode -ne 0) { throw "Model bootstrap failed. See $($paths.Logs)\bootstrap-error.log" }
    }
    $backend = Start-Process -FilePath $requirements.Python -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") -WorkingDirectory (Join-Path $paths.Root "backend") -WindowStyle Hidden -RedirectStandardOutput (Join-Path $paths.Logs "backend.log") -RedirectStandardError (Join-Path $paths.Logs "backend-error.log") -PassThru
    $launched += $backend
    Wait-Http "http://127.0.0.1:$BackendPort/api/health" | Out-Null
    $status = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/system/status"
    if ($status.mode -ne "simulation" -or -not $status.operational) { throw "Backend did not confirm simulation-only readiness." }
    Push-Location (Join-Path $paths.Root "frontend")
    try {
        if ($Mode -eq "Production") { npm.cmd run build *>> (Join-Path $paths.Logs "frontend-build.log"); if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." } }
    } finally { Pop-Location }
    $npmArguments = if ($Mode -eq "Production") { @("run", "preview", "--", "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort") } else { @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort") }
    $frontend = Start-Process -FilePath "npm.cmd" -ArgumentList $npmArguments -WorkingDirectory (Join-Path $paths.Root "frontend") -WindowStyle Hidden -RedirectStandardOutput (Join-Path $paths.Logs "frontend.log") -RedirectStandardError (Join-Path $paths.Logs "frontend-error.log") -PassThru
    $launched += $frontend
    Wait-Http "http://127.0.0.1:$FrontendPort" | Out-Null
    $metadata = [ordered]@{
        synthetic_only = $true; demo_mode = $true; mode = $Mode; started_utc = (Get-Date).ToUniversalTime().ToString("o")
        backend_port = $BackendPort; frontend_port = $FrontendPort
        backend = @{ pid = $backend.Id }; frontend = @{ pid = $frontend.Id }
    }
    $metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $paths.ProcessFile
    $route = if ($OpenPage -eq "overview") { "" } else { $OpenPage }
    $url = "http://127.0.0.1:$FrontendPort/$route"
    if (-not $NoBrowser) { Start-Process $url }
    Write-Host "AegisTwin Judge Demo READY: $url"
    Write-Host "Scenario staged-compromise-demo; seed 84; all outputs computed and synthetic."
    Write-Host "Approval gates remain enabled. Logs: $($paths.Logs)"
} catch {
    foreach ($process in $launched) { if (-not $process.HasExited) { Stop-RecordedProcessTree $process.Id } }
    Write-DemoLog "STARTUP FAILED: $($_.Exception.Message)"
    Write-Error "Startup failed: $($_.Exception.Message) Recovery: STOP_AEGISTWIN_DEMO.bat, then retry."
    exit 1
}

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "demo_common.ps1")
$paths = Get-DemoPaths; $metadata = Read-DemoProcesses
$backendRunning = $metadata -and (Test-RecordedProcess $metadata.backend)
$frontendRunning = $metadata -and (Test-RecordedProcess $metadata.frontend)
$backendHealth = $false; $frontendHealth = $false
if ($backendRunning) { try { $health = Invoke-RestMethod "http://127.0.0.1:$($metadata.backend_port)/api/health" -TimeoutSec 3; $backendHealth = $health.status -eq "healthy" -and $health.simulation_only } catch {} }
if ($frontendRunning) { try { $frontendHealth = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$($metadata.frontend_port)" -TimeoutSec 3).StatusCode -eq 200 } catch {} }
$modelCount = if (Test-Path $paths.Artifacts) { @(Get-ChildItem $paths.Artifacts -Filter *.joblib -File -ErrorAction SilentlyContinue).Count } else { 0 }
[pscustomobject]@{
    Backend = if ($backendRunning) { "running" } else { "stopped" }; BackendPid = $metadata.backend.pid
    BackendHealthy = $backendHealth; Frontend = if ($frontendRunning) { "running" } else { "stopped" }
    FrontendPid = $metadata.frontend.pid; FrontendAvailable = $frontendHealth
    DatabaseReady = Test-Path $paths.Database; ModelsAvailable = $modelCount
    DemoMode = [bool]$metadata.demo_mode; SimulationOnly = if ($metadata) { [bool]$metadata.synthetic_only } else { $true }
} | Format-List

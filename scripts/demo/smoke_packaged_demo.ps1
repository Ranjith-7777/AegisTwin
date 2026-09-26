param([int]$BackendPort = 8030, [int]$FrontendPort = 5200)
$ErrorActionPreference = "Stop"
$temporary = Join-Path $env:TEMP "aegistwin-packaged-smoke-$PID"
$env:AEGISTWIN_DEMO_ROOT = $temporary
try {
    & (Join-Path $PSScriptRoot "start_aegistwin_demo.ps1") -Mode Production -BackendPort $BackendPort -FrontendPort $FrontendPort -NoBrowser
    $health = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/health"
    $safety = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/safety"
    $scenarios = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/v1/simulation/scenarios"
    $models = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/v1/detection/models"
    if ($health.status -ne "healthy" -or -not $health.simulation_only) { throw "Backend health is not safely ready." }
    if (-not $safety.simulation_only -or $safety.real_world_actions_enabled) { throw "Simulation safety contract failed." }
    if (-not ($scenarios.scenario_id -contains "staged-compromise-demo")) { throw "Staged demonstration scenario missing." }
    if (@($models).Count -ne 1) { throw "Expected exactly one deterministic demo model." }
    $frontend = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$FrontendPort"
    if ($frontend.StatusCode -ne 200) { throw "Packaged frontend unavailable." }
    & (Join-Path $PSScriptRoot "audit_offline_resources.ps1")
    Write-Host "Packaged demo smoke passed: isolated database/model, local health, safety, scenario, frontend, and offline resources."
} finally {
    & (Join-Path $PSScriptRoot "stop_aegistwin_demo.ps1")
    Start-Sleep -Milliseconds 500
    if (Test-Path -LiteralPath $temporary) {
        $resolved = [IO.Path]::GetFullPath($temporary)
        if ($resolved.StartsWith([IO.Path]::GetFullPath($env:TEMP))) { Remove-Item -LiteralPath $resolved -Recurse -Force }
    }
    Remove-Item Env:AEGISTWIN_DEMO_ROOT -ErrorAction SilentlyContinue
}

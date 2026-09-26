param([switch]$Force, [switch]$KeepLogs, [switch]$KeepReports, [switch]$SkipModelBootstrap)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "demo_common.ps1")
$paths = Get-DemoPaths
if (-not $Force) { if ((Read-Host "Reset only $($paths.Demo)? Type RESET") -ne "RESET") { Write-Host "Reset cancelled."; exit 0 } }
& (Join-Path $PSScriptRoot "stop_aegistwin_demo.ps1")
$savedLogs = $null; $savedReports = $null
if ($KeepLogs -and (Test-Path $paths.Logs)) { $savedLogs = Join-Path $env:TEMP "aegistwin-demo-logs-$PID"; Move-Item -LiteralPath $paths.Logs -Destination $savedLogs }
if ($KeepReports -and (Test-Path $paths.Reports)) { $savedReports = Join-Path $env:TEMP "aegistwin-demo-reports-$PID"; Move-Item -LiteralPath $paths.Reports -Destination $savedReports }
$resolvedRoot = [IO.Path]::GetFullPath($paths.Root).TrimEnd('\')
$resolvedDemo = [IO.Path]::GetFullPath($paths.Demo).TrimEnd('\')
if (-not $resolvedDemo.StartsWith($resolvedRoot + '\') -or (Split-Path -Leaf $resolvedDemo) -ne ".aegistwin-demo") { throw "Refusing unsafe reset target: $resolvedDemo" }
if (Test-Path -LiteralPath $resolvedDemo) { Remove-Item -LiteralPath $resolvedDemo -Recurse -Force }
$paths = Initialize-DemoDirectories
if ($savedLogs) { Remove-Item $paths.Logs -Force; Move-Item $savedLogs $paths.Logs }
if ($savedReports) { Remove-Item $paths.Reports -Force; Move-Item $savedReports $paths.Reports }
$requirements = Assert-DemoPrerequisites
if (-not $SkipModelBootstrap) {
    $bootstrap = Start-Process -FilePath $requirements.Python -ArgumentList @((Join-Path $PSScriptRoot "bootstrap_demo_model.py"), "--database", $paths.Database, "--artifacts", $paths.Artifacts) -WorkingDirectory $paths.Root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $paths.Logs "bootstrap.log") -RedirectStandardError (Join-Path $paths.Logs "bootstrap-error.log") -Wait -PassThru
    if ($bootstrap.ExitCode -ne 0) { throw "Reset model bootstrap failed. See bootstrap-error.log." }
} else {
    $env:DATABASE_URL = "sqlite:///$($paths.Database.Replace('\','/'))"
    Push-Location (Join-Path $paths.Root "backend"); try { & $requirements.Python -m alembic upgrade head } finally { Pop-Location }
}
Write-Host "Reset complete. Only .aegistwin-demo was recreated; developer data and tracked reports were untouched."

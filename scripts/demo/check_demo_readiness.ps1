param([int]$BackendPort = 8000, [int]$FrontendPort = 5173, [switch]$RequireFreePorts)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "demo_common.ps1")
$critical = @(); $warnings = @(); $paths = Initialize-DemoDirectories
try { $requirements = Assert-DemoPrerequisites; Write-Host "[PASS] Python $($requirements.PythonVersion), Node $($requirements.NodeVersion), npm $($requirements.NpmVersion)" } catch { $critical += $_.Exception.Message; Write-Host "[FAIL] $($_.Exception.Message)" }
$drive = Get-PSDrive -Name ([IO.Path]::GetPathRoot($paths.Root).TrimEnd(':\'))
if ($drive.Free -lt 1GB) { $critical += "Less than 1 GB disk space is free." } else { Write-Host "[PASS] Free disk space: $([math]::Round($drive.Free / 1GB, 1)) GB" }
foreach ($port in @($BackendPort, $FrontendPort)) { if (-not (Test-PortAvailable $port)) { if ($RequireFreePorts) { $critical += "Port $port is occupied." } else { $warnings += "Port $port is occupied (possibly by the running demo)." } } }
$required = @("START_AEGISTWIN_DEMO.bat", "STOP_AEGISTWIN_DEMO.bat", "docs\LOCAL_DEMO_GUIDE.md", "reports\final_benchmark_report.md")
foreach ($item in $required) { if (-not (Test-Path (Join-Path $paths.Root $item))) { $critical += "Missing $item" } }
if (-not (Test-Path (Join-Path $paths.Root "frontend\dist\index.html"))) { $warnings += "Frontend production build is absent; startup will create it." }
if (-not (Test-Path $paths.Database)) { $warnings += "Demo database is not initialized; startup will create it." }
if (@(Get-ChildItem $paths.Artifacts -Filter *.joblib -File -ErrorAction SilentlyContinue).Count -eq 0) { $warnings += "Demo model is absent; startup will create it." }
git -C $paths.Root status --short | Select-String -Pattern '\.env(?!.*example)' | ForEach-Object { $critical += "Potential uncommitted environment file: $_" }
& (Join-Path $PSScriptRoot "audit_offline_resources.ps1")
foreach ($warning in $warnings) { Write-Host "[WARN] $warning" }
if ($critical.Count) { Write-Host "NOT READY"; $critical | ForEach-Object { Write-Host "[FAIL] $_" }; exit 1 }
if ($warnings.Count) { Write-Host "READY WITH WARNINGS"; exit 0 }
Write-Host "READY"

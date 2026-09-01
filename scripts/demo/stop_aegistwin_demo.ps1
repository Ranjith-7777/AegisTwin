$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "demo_common.ps1")
$paths = Get-DemoPaths
$metadata = Read-DemoProcesses
$stopped = @()
foreach ($name in @("frontend", "backend")) {
    $record = if ($metadata) { $metadata.$name } else { $null }
    if (Test-RecordedProcess $record) {
        Stop-RecordedProcessTree ([int]$record.pid)
        $stopped += "$name PID $($record.pid)"
    }
}
if (Test-Path -LiteralPath $paths.ProcessFile) { Remove-Item -LiteralPath $paths.ProcessFile -Force }
if ($stopped.Count) { Write-Host "Stopped: $($stopped -join ', '). Demo data and logs were preserved." }
else { Write-Host "AegisArena demo was already stopped. Stale metadata was cleaned." }

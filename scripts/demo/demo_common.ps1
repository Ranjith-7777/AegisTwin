$ErrorActionPreference = "Stop"

function Get-AegisTwinRoot { return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path }

function Get-DemoPaths {
    $root = Get-AegisTwinRoot
    $demo = if ($env:AEGISTWIN_DEMO_ROOT) { [IO.Path]::GetFullPath($env:AEGISTWIN_DEMO_ROOT) } else { Join-Path $root ".aegistwin-demo" }
    return [ordered]@{
        Root = $root; Demo = $demo; Data = Join-Path $demo "data"
        Artifacts = Join-Path $demo "model-artifacts"; Reports = Join-Path $demo "reports"
        Logs = Join-Path $demo "logs"; Runtime = Join-Path $demo "runtime"
        Database = Join-Path $demo "data\aegistwin-demo.db"
        ProcessFile = Join-Path $demo "runtime\processes.json"
    }
}

function Initialize-DemoDirectories {
    $paths = Get-DemoPaths
    @($paths.Data, $paths.Artifacts, $paths.Reports, $paths.Logs, $paths.Runtime) | ForEach-Object {
        New-Item -ItemType Directory -Force -Path $_ | Out-Null
    }
    return $paths
}

function Write-DemoLog([string]$Message, [string]$Name = "launcher.log") {
    $paths = Initialize-DemoDirectories
    "$(Get-Date -Format o) $Message" | Add-Content -LiteralPath (Join-Path $paths.Logs $Name)
}

function Get-CommandVersion([string]$Command, [string[]]$Arguments) {
    $tool = Get-Command $Command -ErrorAction SilentlyContinue
    if (-not $tool) { return $null }
    $value = (& $tool.Source @Arguments 2>$null | Select-Object -First 1)
    return [pscustomobject]@{ Path = $tool.Source; Text = [string]$value }
}

function Assert-DemoPrerequisites {
    $paths = Get-DemoPaths
    $python = Join-Path $paths.Root "backend\.venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) { throw "Backend virtual environment missing. Run SETUP_AEGISTWIN_DEMO.bat." }
    $pythonVersion = & $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ([version]$pythonVersion -lt [version]"3.11" -or [version]$pythonVersion -ge [version]"3.15") { throw "Python 3.11-3.14 is required; found $pythonVersion." }
    $node = Get-CommandVersion "node" @("--version")
    $npm = Get-CommandVersion "npm.cmd" @("--version")
    if (-not $node -or -not $npm) { throw "Node.js and npm are required. Install Node.js 20-24, then run setup." }
    $nodeMajor = [int]($node.Text.TrimStart("v").Split(".")[0])
    if ($nodeMajor -lt 20 -or $nodeMajor -gt 24) { throw "Node.js 20-24 is required; found $($node.Text)." }
    if (-not (Test-Path (Join-Path $paths.Root "frontend\node_modules"))) { throw "Frontend dependencies missing. Run SETUP_AEGISTWIN_DEMO.bat." }
    return [pscustomobject]@{ Paths = $paths; Python = $python; PythonVersion = $pythonVersion; NodeVersion = $node.Text; NpmVersion = $npm.Text }
}

function Test-PortAvailable([int]$Port) {
    return -not [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Test-RecordedProcess($Record) {
    if (-not $Record -or -not $Record.pid) { return $false }
    return [bool](Get-Process -Id ([int]$Record.pid) -ErrorAction SilentlyContinue)
}

function Stop-RecordedProcessTree([int]$ProcessId) {
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue)
    foreach ($child in $children) { Stop-RecordedProcessTree ([int]$child.ProcessId) }
    if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $ProcessId -Timeout 10 -ErrorAction SilentlyContinue
    }
}

function Read-DemoProcesses {
    $file = (Get-DemoPaths).ProcessFile
    if (-not (Test-Path -LiteralPath $file)) { return $null }
    try { return Get-Content -Raw -LiteralPath $file | ConvertFrom-Json } catch { return $null }
}

function Wait-Http([string]$Url, [int]$TimeoutSeconds = 45) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try { $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3; if ($response.StatusCode -eq 200) { return $response } } catch {}
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for $Url"
}

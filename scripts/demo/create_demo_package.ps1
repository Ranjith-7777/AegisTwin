param([string]$OutputDirectory, [switch]$IncludeModelArtifacts)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "demo_common.ps1")
$paths = Get-DemoPaths
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $paths.Root "demo-package-output" }
$staging = Join-Path $env:TEMP "aegistwin-package-$PID"
if (Test-Path $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging | Out-Null
$tracked = git -C $paths.Root ls-files --cached --others --exclude-standard
foreach ($relative in $tracked) {
    if ($relative -match '(^|/)(\.git|node_modules|\.venv|dist|test-results|playwright-report|\.aegistwin-demo)(/|$)' -or $relative -match '\.(db|sqlite|sqlite3|joblib|pkl)$') { continue }
    $source = Join-Path $paths.Root $relative; if (-not (Test-Path $source -PathType Leaf)) { continue }
    $destination = Join-Path $staging $relative; New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null; Copy-Item -LiteralPath $source -Destination $destination
}
if ($IncludeModelArtifacts -and (Test-Path $paths.Artifacts)) { Copy-Item -Recurse $paths.Artifacts (Join-Path $staging "optional-synthetic-model-artifacts") }
$manifest = [ordered]@{ created_utc = (Get-Date).ToUniversalTime().ToString("o"); git_commit = (git -C $paths.Root rev-parse HEAD); synthetic_only = $true; file_count = @(Get-ChildItem $staging -Recurse -File).Count; model_artifacts_included = [bool]$IncludeModelArtifacts }
$manifest | ConvertTo-Json | Set-Content (Join-Path $staging "DEMO_PACKAGE_MANIFEST.json")
Get-ChildItem $staging -Recurse -File | ForEach-Object { "$(Get-FileHash $_.FullName -Algorithm SHA256 | Select-Object -ExpandProperty Hash)  $($_.FullName.Substring($staging.Length + 1))" } | Set-Content (Join-Path $staging "SHA256SUMS.txt")
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$archive = Join-Path $OutputDirectory "AegisTwin-offline-demo.zip"; if (Test-Path $archive) { Remove-Item $archive -Force }
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $archive
Remove-Item -LiteralPath $staging -Recurse -Force
Write-Host "Created $archive. Dependencies are intentionally excluded; run SETUP_AEGISTWIN_DEMO.bat after extraction."

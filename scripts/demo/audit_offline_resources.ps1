$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "demo_common.ps1")
$paths = Get-DemoPaths
$source = Join-Path $paths.Root "frontend\src"
$matches = Get-ChildItem $source -Recurse -File | Select-String -Pattern 'https?://(?!127\.0\.0\.1|localhost|www\.w3\.org)|wss?://(?!127\.0\.0\.1|localhost)'
if (Test-Path (Join-Path $paths.Root "frontend\dist")) {
    $matches += Get-ChildItem (Join-Path $paths.Root "frontend\dist") -Recurse -File -Include *.html,*.css |
        Select-String -Pattern '(src|href|url\()\s*[=:]\s*["'']?https?://(?!127\.0\.0\.1|localhost)'
}
if ($matches) { $matches | Format-Table Path, LineNumber, Line; throw "Unexpected non-local URL found in frontend resources." }
Write-Host "Offline resource audit passed: no external runtime URLs found."

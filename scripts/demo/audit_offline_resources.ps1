$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "demo_common.ps1")
$paths = Get-DemoPaths
$source = Join-Path $paths.Root "frontend\src"
$sourceFiles = Get-ChildItem $source -Recurse -File | Where-Object {
    $_.FullName -notmatch '[\\/]test[\\/]' -and $_.Name -notmatch '\.test\.'
}
$matches = $sourceFiles |
    Select-String -Pattern 'https?://(?!127\.0\.0\.1|localhost|www\.w3\.org)|wss?://(?!127\.0\.0\.1|localhost)' |
    # This URL is an origin-only sentinel for validating local redirect paths.
    # new URL() never contacts it and the value is not rendered as a resource.
    Where-Object { $_.Line -notmatch 'new URL\([''"]https://aegisarena\.local[''"]\)' }
if (Test-Path (Join-Path $paths.Root "frontend\dist")) {
    $matches += Get-ChildItem (Join-Path $paths.Root "frontend\dist") -Recurse -File -Include *.html,*.css |
        Select-String -Pattern '(src|href|url\()\s*[=:]\s*["'']?https?://(?!127\.0\.0\.1|localhost)'
}
if ($matches) { $matches | Format-Table Path, LineNumber, Line; throw "Unexpected non-local URL found in frontend resources." }
Write-Host "Offline resource audit passed: no external runtime URLs found."

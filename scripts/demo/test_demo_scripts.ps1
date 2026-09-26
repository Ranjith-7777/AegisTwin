$ErrorActionPreference = "Stop"
$files = Get-ChildItem $PSScriptRoot -Filter *.ps1 -File
foreach ($file in $files) {
    $tokens = $null; $errors = $null
    [Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors.Count) { throw "PowerShell syntax failure in $($file.Name): $($errors[0].Message)" }
}
Write-Host "PowerShell syntax validation passed for $($files.Count) demo scripts."

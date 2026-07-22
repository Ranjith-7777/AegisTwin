$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) { throw "Backend virtual environment is missing." }

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE." }
}

Push-Location $backend
try {
    & $python -m ruff format --check app tests alembic
    Assert-NativeSuccess "Backend format check"
    & $python -m ruff check app tests alembic
    Assert-NativeSuccess "Backend lint"
    & $python -m mypy app
    Assert-NativeSuccess "Backend type check"
    & $python -m pytest -q
    Assert-NativeSuccess "Backend tests"
    $env:DATABASE_URL = "sqlite:///./.release-validation.db"
    & $python -m alembic upgrade head
    Assert-NativeSuccess "Clean database migration"
    Remove-Item Env:DATABASE_URL
    Remove-Item -LiteralPath ".release-validation.db" -Force
} finally { Pop-Location }

Push-Location $frontend
try {
    npm.cmd run format:check
    Assert-NativeSuccess "Frontend format check"
    npm.cmd run lint
    Assert-NativeSuccess "Frontend lint"
    npm.cmd run typecheck
    Assert-NativeSuccess "Frontend type check"
    npm.cmd run test:run
    Assert-NativeSuccess "Frontend unit tests"
    npm.cmd run build
    Assert-NativeSuccess "Frontend production build"
    npm.cmd run test:e2e
    Assert-NativeSuccess "Frontend browser E2E"
} finally { Pop-Location }

Push-Location $root
try {
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\demo\test_demo_scripts.ps1
    Assert-NativeSuccess "Demo script syntax validation"
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\demo\check_demo_readiness.ps1
    Assert-NativeSuccess "Demo readiness check"
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\demo\audit_offline_resources.ps1
    Assert-NativeSuccess "Offline resource audit"
    if ($env:RUN_PACKAGED_DEMO_SMOKE -eq "true") {
        powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\demo\smoke_packaged_demo.ps1
        Assert-NativeSuccess "Packaged demo smoke"
    }
    & $python scripts\final_benchmark.py
    Assert-NativeSuccess "Final benchmark"
    git diff --check
    Assert-NativeSuccess "Git whitespace audit"
    $trackedArtifacts = git ls-files | Select-String -Pattern '\.(db|sqlite|sqlite3|joblib|pkl)$|artifacts/models'
    if ($trackedArtifacts) { throw "Generated databases or model artifacts are tracked." }
    $secrets = git grep -n -I -E '(BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|AKIA[0-9A-Z]{16})' -- . ':!scripts/validate_release.ps1'
    if ($LASTEXITCODE -eq 0 -and $secrets) { throw "Potential secret pattern found." }
    $absolutePaths = git grep -n -I -E '([A-Z]:\\Users\\|/home/[^/]+/|/Users/[^/]+/)' -- . ':!docs/RELEASE_AUDIT.md' ':!backend/Dockerfile' ':!scripts/validate_release.ps1'
    if ($LASTEXITCODE -eq 0 -and $absolutePaths) { throw "Machine-specific absolute path found." }
    $realExecutionWording = git grep -n -I -E '(execute|executed|execution) (on|against|in) (real|production|live) (infrastructure|systems?|environment)' -- frontend/src backend/app simulator
    if ($LASTEXITCODE -eq 0 -and $realExecutionWording) { throw "Prohibited real-execution wording found in runtime source." }
} finally { Pop-Location }

Write-Host "AegisTwin release validation passed. All exercised workflows are synthetic."

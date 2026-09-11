$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = if ($env:MATRIX_PYTHON) { $env:MATRIX_PYTHON } else { 'python' }
Push-Location $projectRoot
try {
    & $python -m pytest -q
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

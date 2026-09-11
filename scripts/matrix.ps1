param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = if ($env:MATRIX_PYTHON) { $env:MATRIX_PYTHON } else { 'python' }
& $python (Join-Path $projectRoot 'matrix_tool.py') @CommandArgs
exit $LASTEXITCODE

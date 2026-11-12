# Forward Python arguments verbatim, including --help and subcommand options.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'From the template root, create .venv with python -m venv .venv, then run .venv/Scripts/python.exe -m pip install -r requirements.txt.'
}
& $python (Join-Path $PSScriptRoot 'fea.py') @args
exit $LASTEXITCODE

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv is required" }
if (-not (Test-Path ".env.local")) { python .\scripts\init_secrets.py --target .env.local }
uv sync --extra dev
uv run pytest -q
Write-Host "Offline controls verified. Add OPENAI_API_KEY securely, then run with PORT=8421."

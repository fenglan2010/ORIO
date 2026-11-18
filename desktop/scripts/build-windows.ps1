# Reproducible Windows desktop build (run on Windows with Node 20+ and Python venv prepared).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Building frontend..."
Push-Location ..\frontend
npm ci
npm run build
Pop-Location

if (-not (Test-Path "..\.venv")) {
  Write-Host "Create backend venv from repo root: python -m venv .venv && pip install -r backend/requirements.txt"
}

$env:OIRO_DISTRIBUTION = "packaged"
npm ci
npm run pack:win

Write-Host "Artifacts in desktop/dist"
# Create Python 3.12 venv and install bot dependencies
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot | Split-Path -Parent
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host "Creating Python 3.12 virtual environment..." -ForegroundColor Cyan
if (Test-Path (Join-Path $Root ".venv")) {
    Write-Host "  .venv already exists, reusing." -ForegroundColor DarkGray
} else {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Could not create venv. Install Python 3.12 from python.org" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Installing requirements (may take a few minutes)..." -ForegroundColor Cyan
& $VenvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Done. Python:" -ForegroundColor Green
& $VenvPython --version
Write-Host "Venv: $VenvPython" -ForegroundColor Green
Write-Host ""
Write-Host "Next: .\start-paper-bot.ps1" -ForegroundColor Cyan

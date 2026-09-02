# Finance-Vibe Paper Bot launcher (Windows)
# Uses .venv Python 3.12 (pandas_ta does not support Python 3.14)

param(
    [switch]$SkipCheck,
    [switch]$NoRunner,
    [switch]$NoBrowser,
    [switch]$SkipPrepare,
    [switch]$Resume
)

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$SetupScript = Join-Path $Root "scripts\setup-venv.ps1"

if (-not (Test-Path $VenvPython)) {
    Write-Host ""
    Write-Host "No .venv found - setting up Python 3.12 environment..." -ForegroundColor Yellow
    Write-Host "(Required: pandas_ta does not work on Python 3.14)" -ForegroundColor DarkGray
    Write-Host ""
    & powershell -NoProfile -ExecutionPolicy Bypass -File $SetupScript
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) {
        Write-Host "ERROR: venv setup failed. Run: .\scripts\setup-venv.ps1" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

$Python = $VenvPython
$Check = Join-Path $Root "src\finance_vibe\bot\check_setup.py"
$Dashboard = Join-Path $Root "src\finance_vibe\bot\dashboard.py"
$Runner = Join-Path $Root "src\finance_vibe\bot\runner.py"

function Start-BotWindow {
    param(
        [string]$Title,
        [string]$Script,
        [string[]]$ScriptArgs = @()
    )
    $argList = @($Script) + $ScriptArgs
    $argStr = ($argList | ForEach-Object { "'$_'" }) -join ", "
    $cmd = "Set-Location '$Root'; `$Host.UI.RawUI.WindowTitle = '$Title'; & '$Python' $argStr"
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $cmd)
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Finance-Vibe Paper Bot" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
& $Python --version
Write-Host ""

if (-not $SkipCheck) {
    Write-Host "Running setup check..." -ForegroundColor Yellow
    & $Python $Check
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Setup check FAILED. Read FAIL lines above." -ForegroundColor Red
        Write-Host "Re-run venv setup: .\scripts\setup-venv.ps1" -ForegroundColor Yellow
        Write-Host "Or skip check: .\start-paper-bot.ps1 -SkipCheck" -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }
    Write-Host ""
}

Write-Host "Ollama: use the desktop app. Skip ollama serve if port 11434 is busy." -ForegroundColor DarkGray
Write-Host ""

Start-BotWindow -Title "FV Bot - Dashboard" -Script $Dashboard
Start-Sleep -Seconds 2

if (-not $NoRunner) {
    if ($Resume) {
        Write-Host 'RESUME mode - cancel stuck orders, KEEP positions + day PnL...' -ForegroundColor Yellow
        & $Python $Runner resume-session
        if ($LASTEXITCODE -ne 0) {
            Write-Host "resume-session failed." -ForegroundColor Red
            exit 1
        }
        Write-Host ""
    }
    elseif (-not $SkipPrepare) {
        Write-Host 'Preparing clean session (cancel orders, flatten, reset day PnL)...' -ForegroundColor Yellow
        & $Python $Runner prepare-session
        if ($LASTEXITCODE -ne 0) {
            Write-Host "prepare-session failed. Fix errors or use -SkipPrepare / -Resume" -ForegroundColor Red
            exit 1
        }
        Write-Host ""
    }
    Start-BotWindow -Title "FV Bot - Runner" -Script $Runner -ScriptArgs @("daemon")
}

Write-Host "Started:" -ForegroundColor Green
Write-Host "  [1] Dashboard  ->  http://127.0.0.1:5001"
if (-not $NoRunner) {
    Write-Host "  [2] Runner     ->  trades every 20 min (market hours)"
}
Write-Host ""
Write-Host "Close those windows to stop the bot." -ForegroundColor DarkGray
Write-Host ""

if (-not $NoBrowser) {
    Start-Sleep -Seconds 2
    Start-Process 'http://127.0.0.1:5001'
}

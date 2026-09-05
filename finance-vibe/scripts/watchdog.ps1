# Finance-Vibe runner watchdog.
# Polls runner.pid; if the market is open and the runner is gone, resumes it.
# Always -Resume semantics: resume-session keeps positions and day P&L.
# A plain prepare-session here would flatten live positions.

param(
    [int]$IntervalSeconds = 120,
    [int]$MaxRestartsPerDay = 5
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Runner = Join-Path $Root "src\finance_vibe\bot\runner.py"

if (-not (Test-Path $Python)) {
    Write-Host "ERROR: .venv not found at $Python" -ForegroundColor Red
    exit 1
}

$restarts = 0
$restartDay = (Get-Date).Date

Write-Host "Watchdog active - checking every $IntervalSeconds s" -ForegroundColor Cyan
Write-Host "Max $MaxRestartsPerDay restarts/day. Close this window to stop." -ForegroundColor DarkGray
Write-Host ""

while ($true) {
    Start-Sleep -Seconds $IntervalSeconds

    if ((Get-Date).Date -ne $restartDay) {
        $restartDay = (Get-Date).Date
        $restarts = 0
    }

    & $Python $Runner watchdog-check 2>&1 | Out-Null
    $code = $LASTEXITCODE

    if ($code -ne 10) { continue }

    $stamp = (Get-Date).ToString("HH:mm:ss")
    if ($restarts -ge $MaxRestartsPerDay) {
        Write-Host "$stamp Runner down but restart limit ($MaxRestartsPerDay) reached - not restarting." -ForegroundColor Red
        Write-Host "         Something is crashing repeatedly. Investigate before the next session." -ForegroundColor Yellow
        continue
    }

    $restarts++
    Write-Host "$stamp Runner is down during market hours - resuming (restart $restarts/$MaxRestartsPerDay)" -ForegroundColor Yellow

    & $Python $Runner resume-session
    if ($LASTEXITCODE -ne 0) {
        Write-Host "$stamp resume-session failed - NOT starting the daemon." -ForegroundColor Red
        continue
    }

    $cmd = "Set-Location '$Root'; `$Host.UI.RawUI.WindowTitle = 'FV Bot - Runner'; & '$Python' '$Runner' daemon"
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $cmd)
    Write-Host "$stamp Runner relaunched." -ForegroundColor Green

    Start-Sleep -Seconds 60
}

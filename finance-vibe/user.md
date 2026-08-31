# Paper Trading Bot — Quick Start

## One-time setup

1. **Python 3.12 venv** (required — `pandas_ta` does not work on Python 3.14):
   ```powershell
   .\scripts\setup-venv.ps1
   ```
   Or just run `.\start-paper-bot.ps1` — it creates the venv automatically on first launch.

2. Copy `.env.example` → `.env` and add Alpaca keys

3. **Ollama on Windows**: use the **Ollama desktop app** (don't run `ollama serve` if port 11434 is busy)

**Do not use system `python` (3.14)** for the bot. Always use `.venv\Scripts\python.exe` or the launcher.

## Start everything (recommended)

From the project folder in PowerShell:

```powershell
cd C:\Users\sheel\Documents\Projects\finance-vibe
.\start-paper-bot.ps1
```

Or double-click **`start-paper-bot.bat`**.

This will:
1. Run a setup check (Alpaca + Ollama + database)
2. Open **Dashboard** terminal → http://127.0.0.1:5001
3. Open **Runner** terminal → 15-min trading cycles during market hours
4. Open the dashboard in your browser

**No `PYTHONPATH` needed** — scripts bootstrap paths automatically.

### Launcher options

| Flag | Effect |
|------|--------|
| `-SkipCheck` | Skip setup check, start windows anyway |
| `-NoRunner` | Dashboard only (no trading daemon) |
| `-NoBrowser` | Don't auto-open browser |

```powershell
.\start-paper-bot.ps1 -SkipCheck
.\start-paper-bot.ps1 -NoRunner
```

If PowerShell blocks the script:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# or
powershell -ExecutionPolicy Bypass -File .\start-paper-bot.ps1
```

## Manual commands (optional)

These work from the project root **without** setting `PYTHONPATH`:

```powershell
python src\finance_vibe\bot\check_setup.py
python src\finance_vibe\bot\check_setup.py --deep
python src\finance_vibe\bot\dashboard.py
python src\finance_vibe\bot\runner.py daemon
python src\finance_vibe\bot\runner.py status
python src\finance_vibe\bot\runner.py cycle --force
```

## What you provide in `.env`

| Variable | Required |
|----------|----------|
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Yes |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` (Windows Ollama) |
| `OLLAMA_MODEL` | Must match `ollama list` (e.g. `qwen3-coder:30b`) |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No module named 'pandas_ta'` | You're on Python 3.14. Run `.\scripts\setup-venv.ps1` then `.\start-paper-bot.ps1` |
| Dashboard says online but runner crashes | Fixed — health check now tests `pandas_ta` + runner imports |
| `No module named 'finance_vibe'` | Use `.\start-paper-bot.ps1` (handles paths automatically) |
| `ollama serve` port in use | Ollama app already running — skip `ollama serve` |
| Setup check fails | Run `python src\finance_vibe\bot\check_setup.py` and read FAIL lines |
| Ollama offline | Open Ollama desktop app; test: `curl http://127.0.0.1:11434/api/tags` |

## Daily workflow (2-week paper trial)

1. Run `.\start-paper-bot.ps1` before 9:30 ET
2. Watch dashboard during the day
3. Close terminals when done (or leave runner for EOD report)

See `architecture.md` for design details.

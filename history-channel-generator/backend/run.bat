@echo off
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Installing dependencies...
venv\Scripts\python.exe -m pip install -r requirements.txt

echo Starting server at http://localhost:8000
venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

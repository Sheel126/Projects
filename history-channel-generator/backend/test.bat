@echo off
cd /d "%~dp0"
set PYTHONPATH=src
venv\Scripts\python.exe -m unittest discover -s tests -v

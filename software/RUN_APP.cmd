@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Create the environment first:
    echo py -3.11 -m venv .venv
    echo .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause

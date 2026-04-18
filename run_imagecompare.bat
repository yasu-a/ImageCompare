@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
  set "PY=venv\Scripts\python.exe"
) else (
  echo Python venv not found. Create .venv or venv in this folder.
  exit /b 1
)

"%PY%" -m pip install -r requirements.txt
"%PY%" main.py

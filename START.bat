@echo off
if not exist .venv\Scripts\python.exe (
  echo Once SETUP.bat calistirin.
  pause
  exit /b 1
)
start "" http://127.0.0.1:8765
.venv\Scripts\python.exe run.py
pause

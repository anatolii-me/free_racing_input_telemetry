@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo First install the dependencies using the commands in README.md.
  pause
  exit /b 1
)
start "ACC Trace" ".venv\Scripts\pythonw.exe" -m acc_trace

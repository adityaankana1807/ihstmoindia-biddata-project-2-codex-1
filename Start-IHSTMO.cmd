@echo off
cd /d "%~dp0"
if exist "dist\I-HSTMO-India.exe" (
  "dist\I-HSTMO-India.exe"
) else (
  python run.py
)
if errorlevel 1 pause

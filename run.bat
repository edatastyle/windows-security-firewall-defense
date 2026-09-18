@echo off
title aThemeArt Security Firewall Defense
cd /d "%~dp0"

REM Prefer virtual environment if present
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "src\main.py"
) else (
    python "src\main.py"
)

if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)

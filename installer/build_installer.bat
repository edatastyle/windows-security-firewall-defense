@echo off
setlocal
cd /d "%~dp0"

echo Building installer with Inno Setup...
echo.

REM Common Inno Setup locations
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe

if "%ISCC%"=="" (
    echo ERROR: Inno Setup 6 not found.
    echo Download from https://jrsoftware.org/isinfo.php
    echo and install, then re-run this script.
    exit /b 1
)

if not exist "..\dist\SecurityFirewallDefense.exe" (
    echo ERROR: dist\SecurityFirewallDefense.exe not found.
    echo Run scripts\build_exe.bat first.
    exit /b 1
)

"%ISCC%" "SecurityFirewallDefense.iss"
if errorlevel 1 (
    echo Installer build failed.
    exit /b 1
)

echo.
echo Installer created in installer\output\
dir /b output\*.exe
pause

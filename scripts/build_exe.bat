@echo off
setlocal EnableExtensions

cd /d "%~dp0.."

echo ============================================
echo  Security Firewall Defense
echo  Building Windows Application
echo  Developed by aThemeArt
echo  https://athemeart.com
echo ============================================
echo.

REM ==================================================
REM [0/5] Check Python
REM ==================================================

where py >nul 2>&1

if errorlevel 1 (
    echo ERROR: Python Launcher ^(py.exe^) not found.
    echo.
    echo Install Python from:
    echo https://www.python.org/downloads/windows/
    echo.
    pause
    exit /b 1
)

echo Python detected:
py --version
echo.

REM ==================================================
REM [1/5] Create virtual environment
REM ==================================================

echo [1/5] Checking virtual environment...

if not exist ".venv\Scripts\python.exe" (
    echo Creating .venv...
    py -m venv .venv

    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Virtual environment:
python --version
echo.

REM ==================================================
REM [2/5] Install dependencies
REM ==================================================

echo [2/5] Installing dependencies...

python -m pip install --upgrade pip

if errorlevel 1 (
    echo ERROR: Failed to upgrade pip.
    pause
    exit /b 1
)

if exist "requirements.txt" (
    python -m pip install -r requirements.txt

    if errorlevel 1 (
        echo ERROR: Failed to install requirements.
        pause
        exit /b 1
    )
)

python -m pip install --upgrade pyinstaller

if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller.
    pause
    exit /b 1
)

echo.

REM ==================================================
REM [3/5] Clean previous build
REM ==================================================

echo [3/5] Cleaning previous build...

if exist "build" (
    rmdir /S /Q "build"
)

if exist "dist\SecurityFirewallDefense" (
    rmdir /S /Q "dist\SecurityFirewallDefense"
)

if exist "dist\SecurityFirewallDefense.exe" (
    del /F /Q "dist\SecurityFirewallDefense.exe"
)

echo Clean complete.
echo.

REM ==================================================
REM [4/5] Build application
REM ==================================================

echo [4/5] Building Security Firewall Defense...
echo.
echo Build mode: ONEDIR
echo.

set "ICON_OPT="

if exist "src\assets\icon.ico" (
    set "ICON_OPT=--icon src\assets\icon.ico"
    echo Application icon detected.
) else (
    echo WARNING: src\assets\icon.ico not found.
)

echo.

python -m PyInstaller --noconfirm --clean ^
    --name "SecurityFirewallDefense" ^
    --windowed ^
    --onedir ^
    --paths "src" ^
    %ICON_OPT% ^
    --add-data "scripts\Security-Firewall-Defense.ps1;scripts" ^
    --add-data "src\assets;assets" ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    --collect-all customtkinter ^
    --collect-submodules core ^
    "src\main.py"

if errorlevel 1 (
    echo.
    echo ============================================
    echo  BUILD FAILED
    echo ============================================
    echo.
    pause
    exit /b 1
)

REM ==================================================
REM [5/5] Copy runtime files
REM ==================================================

echo.
echo [5/5] Preparing runtime files...

if not exist "dist\SecurityFirewallDefense\data" (
    mkdir "dist\SecurityFirewallDefense\data"
)

if not exist "dist\SecurityFirewallDefense\scripts" (
    mkdir "dist\SecurityFirewallDefense\scripts"
)

if exist "scripts\Security-Firewall-Defense.ps1" (
    copy /Y "scripts\Security-Firewall-Defense.ps1" ^
        "dist\SecurityFirewallDefense\scripts\" >nul
)

echo.
echo ============================================
echo  BUILD COMPLETE
echo ============================================
echo.
echo Application:
echo %CD%\dist\SecurityFirewallDefense\SecurityFirewallDefense.exe
echo.
echo Build type:
echo ONEDIR
echo.
echo Next step:
echo Test the EXE before creating the installer.
echo.
echo ============================================

pause

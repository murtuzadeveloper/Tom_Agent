@echo off
setlocal enabledelayedexpansion

title murtuzadeveloper Smart Leads - Launcher
echo ==============================================================================
echo              murtuzadeveloper Smart Leads
echo    AI-Powered Screen Intelligence & Contact Extraction for Windows 11
echo ==============================================================================
echo.

:: 1. Check Python installation
where py >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=py -3.11
    py -3.11 --version >nul 2>&1
    if %errorlevel% neq 0 (
        set PY_CMD=py -3
    )
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PY_CMD=python
    ) else (
        echo [ERROR] Python was not found in PATH!
        echo Please install Python 3.11 (64-bit) from https://www.python.org/
        pause
        exit /b 1
    )
)

echo [INFO] Using Python interpreter: %PY_CMD%

:: 2. Check Virtual Environment
if not exist ".venv" (
    echo [INFO] Creating Python virtual environment in .venv ...
    %PY_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
)

:: 3. Activate Virtual Environment
call .venv\Scripts\activate.bat

:: 4. Check & Install Dependencies
echo [INFO] Verifying application dependencies...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [WARNING] Some dependencies had warnings during install. Continuing...
)

:: 5. Launch Application
echo [INFO] Launching murtuzadeveloper Smart Leads...
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application exited with code %errorlevel%.
    pause
)

deactivate

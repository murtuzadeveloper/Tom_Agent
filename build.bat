@echo off
setlocal enabledelayedexpansion

title Building murtuzadeveloper Smart Leads (Windows 11)
echo ==============================================================================
echo        Building Standalone Package: murtuzadeveloper Smart Leads
echo ==============================================================================
echo.

:: Activate Virtual Environment if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo [INFO] Installing PyInstaller...
pip install pyinstaller --quiet

echo [INFO] Running PyInstaller build...
pyinstaller --noconfirm --onedir --windowed ^
    --name "murtuzadeveloper Smart Leads" ^
    --add-data "config.py;." ^
    --hidden-import "PySide6.QtCore" ^
    --hidden-import "PySide6.QtGui" ^
    --hidden-import "PySide6.QtWidgets" ^
    --hidden-import "email_validator" ^
    --hidden-import "phonenumbers" ^
    --hidden-import "mss" ^
    --hidden-import "PIL" ^
    --hidden-import "requests" ^
    main.py

if %errorlevel% equ 0 (
    echo.
    echo ==============================================================================
    echo [SUCCESS] Build completed successfully!
    echo Standalone executable is available at:
    echo "dist\murtuzadeveloper Smart Leads\murtuzadeveloper Smart Leads.exe"
    echo ==============================================================================
) else (
    echo.
    echo [ERROR] Build failed with error code %errorlevel%!
)

pause

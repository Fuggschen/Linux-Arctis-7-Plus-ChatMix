@echo off
REM Build script for Windows ChatMix portable executable
REM This script packages the Windows ChatMix rewrite into a single .exe file using PyInstaller.
REM
REM Requirements:
REM   - Python 3.9+
REM   - PyInstaller: pip install pyinstaller
REM   - All dependencies in requirements.txt installed
REM
REM Usage:
REM   build.bat
REM
REM Output:
REM   dist/ChatMixWindows.exe

setlocal enabledelayedexpansion

echo.
echo ========================================
echo  ChatMix Windows Build Script
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.9+ and add it to your system PATH.
    pause
    exit /b 1
)

echo [1/5] Checking dependencies...
pip list | find "PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo WARNING: PyInstaller not found. Installing...
    pip install pyinstaller
)

echo.
echo [2/5] Checking requirements...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo [3/5] Removing old build artifacts...
if exist build rmdir /s /q build >nul 2>&1
if exist dist rmdir /s /q dist >nul 2>&1
if exist *.spec del *.spec >nul 2>&1

echo.
echo [4/5] Building executable...
REM Build the main executable with PyInstaller (without icon)
pyinstaller --onefile ^
    --windowed ^
    --name ChatMixWindows ^
    --add-data "windows:windows" ^
    --collect-all pycaw ^
    --collect-all usb ^
    --hidden-import=pycaw.pycaw ^
    --hidden-import=usb.core ^
    --hidden-import=usb.backend ^
    --hidden-import=usb.backend.libusb1 ^
    windows/chatmix_windows.py

if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    pause
    exit /b 1
)

echo.
echo [5/5] Cleaning up build artifacts...
rmdir /s /q build >nul 2>&1
del *.spec >nul 2>&1

echo.
echo ========================================
echo  Build Complete!
echo ========================================
echo.
echo Executable created at: dist\ChatMixWindows.exe
echo.
echo Usage:
echo   ChatMixWindows.exe --ui              (open configuration UI)
echo   ChatMixWindows.exe --tray            (run in background)
echo   ChatMixWindows.exe --install-autostart (add to Windows startup)
echo.
pause

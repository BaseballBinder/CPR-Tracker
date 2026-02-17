@echo off
echo ============================================
echo  CPR Performance Tracker - Build Script
echo ============================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check for virtual environment
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo WARNING: No virtual environment found. Using system Python.
)

REM Install/update dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

REM Convert PNG to ICO if needed
if not exist "static\images\logos\JcLS.ico" (
    echo.
    echo Converting JcLS.png to JcLS.ico...
    python -c "from PIL import Image; img = Image.open('static/images/logos/JcLS.png'); img.save('static/images/logos/JcLS.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])" 2>nul
    if errorlevel 1 (
        echo WARNING: Could not convert icon. Install Pillow: pip install Pillow
        echo Building without custom icon...
    ) else (
        echo Icon created successfully.
    )
)

REM Run PyInstaller
echo.
echo Building executable...
pyinstaller cpr_tracker.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build complete!
echo  Output: dist\CPR-Tracker.exe
echo ============================================
echo.

REM Show file size
for %%A in (dist\CPR-Tracker.exe) do echo File size: %%~zA bytes

pause

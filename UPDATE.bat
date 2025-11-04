@echo off
REM One-Click Update Script for GitHub Profile
REM Double-click this file to update your profile automatically!

echo ============================================================
echo ONE-CLICK GITHUB PROFILE UPDATER v2
echo Improved with modular agent system
echo ============================================================
echo.

REM Check if virtual environment exists
if exist venv (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [WARNING] No virtual environment found
    echo Proceeding with global Python installation...
)

echo.
echo Starting automated update process...
echo.

python auto_updater.py

echo.
echo ============================================================
echo Press any key to exit...
pause > nul

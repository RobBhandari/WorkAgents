@echo off
REM Weekly DOE Bug Tracker Report
REM Runs the DOE tracker and sends email report
REM To be scheduled for 7am every Friday

echo ============================================================
echo DOE Weekly Bug Tracker Report
echo Running at: %date% %time%
echo ============================================================
echo.

REM Change to script directory
cd /d "%~dp0\.."

REM Activate virtual environment and run tracker
echo [1/2] Calculating weekly metrics...
.venv\Scripts\python.exe execution\ado_doe_tracker.py
if errorlevel 1 (
    echo ERROR: DOE tracker failed
    exit /b 1
)

echo.
echo [2/2] Sending email report...
.venv\Scripts\python.exe execution\send_doe_report.py
if errorlevel 1 (
    echo ERROR: Email send failed
    exit /b 1
)

echo.
echo ============================================================
echo DOE report completed successfully at: %date% %time%
echo ============================================================

exit /b 0

@echo off
REM ArmorCode Vulnerability Tracking Report
REM Retrieves HIGH and CRITICAL vulnerabilities and sends HTML report via email
REM To be scheduled for recurring execution

echo ============================================================
echo ArmorCode Vulnerability Tracking Report
echo Running at: %date% %time%
echo ============================================================
echo.

REM Change to project root directory
cd /d "%~dp0\.."

REM Activate virtual environment if it exists
if exist .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Step 1: Query current vulnerabilities
echo [1/3] Querying ArmorCode for current vulnerabilities...
.venv\Scripts\python.exe execution\armorcode_query_vulns.py
if errorlevel 1 (
    echo ERROR: ArmorCode query failed
    echo Check log file in .tmp\ directory for details
    exit /b 1
)
echo.

REM Step 2: Find the latest query JSON file
echo [2/3] Generating HTML report...
FOR /F "tokens=*" %%i IN ('dir /b /od .tmp\armorcode_query_*.json 2^>nul') DO SET LATEST_JSON=%%i

if not defined LATEST_JSON (
    echo ERROR: No query JSON file found in .tmp\ directory
    exit /b 1
)

echo Using query file: .tmp\%LATEST_JSON%
.venv\Scripts\python.exe execution\armorcode_report_to_html.py .tmp\%LATEST_JSON%
if errorlevel 1 (
    echo ERROR: HTML report generation failed
    echo Check log file in .tmp\ directory for details
    exit /b 1
)
echo.

REM Step 3: Find the latest HTML report file
echo [3/3] Sending email report...
FOR /F "tokens=*" %%i IN ('dir /b /od .tmp\armorcode_report_*.html 2^>nul') DO SET LATEST_HTML=%%i

if not defined LATEST_HTML (
    echo ERROR: No HTML report file found in .tmp\ directory
    exit /b 1
)

echo Using HTML file: .tmp\%LATEST_HTML%
.venv\Scripts\python.exe execution\send_armorcode_report.py .tmp\%LATEST_HTML% --json-summary .tmp\%LATEST_JSON%
if errorlevel 1 (
    echo ERROR: Email sending failed
    echo Check log file in .tmp\ directory for details
    exit /b 1
)
echo.

echo ============================================================
echo ArmorCode report completed successfully at: %date% %time%
echo ============================================================
echo Report file: .tmp\%LATEST_HTML%
echo Query data: .tmp\%LATEST_JSON%
echo.
echo Check email inbox for the report.
echo ============================================================

exit /b 0

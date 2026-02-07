@echo off
REM Simple Task Scheduler Setup for DOE Weekly Report
REM Creates scheduled task to run every Friday at 7am

echo Creating scheduled task: DOE_Weekly_Bug_Report
echo Schedule: Every Friday at 7:00 AM
echo.

schtasks /create ^
    /tn "DOE_Weekly_Bug_Report" ^
    /tr "cmd.exe /c \"c:\DEV\Agentic-Test\execution\run_weekly_doe_report.bat\" >> \"c:\DEV\Agentic-Test\.tmp\scheduled_doe_report.log\" 2>&1" ^
    /sc weekly ^
    /d FRI ^
    /st 07:00 ^
    /f

if errorlevel 1 (
    echo.
    echo ERROR: Failed to create scheduled task
    echo You may need to run this as Administrator
    echo Right-click this file and select "Run as administrator"
    pause
    exit /b 1
)

echo.
echo ============================================================
echo SUCCESS! Scheduled task created.
echo ============================================================
echo.
echo Task will run every Friday at 7:00 AM
echo Logs will be saved to: .tmp\scheduled_doe_report.log
echo.
echo To test now, run: schtasks /run /tn "DOE_Weekly_Bug_Report"
echo To view task: taskschd.msc
echo To delete task: schtasks /delete /tn "DOE_Weekly_Bug_Report" /f
echo.
pause

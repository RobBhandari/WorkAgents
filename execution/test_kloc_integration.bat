@echo off
REM Test KLOC Integration - Complete Workflow
REM This script tests the full KLOC calculation and integration with Quality Dashboard

echo ================================================================================
echo KLOC Integration Test - Complete Workflow
echo ================================================================================
echo.

REM Step 1: Calculate KLOC
echo [STEP 1/3] Calculating KLOC from Git repositories...
echo --------------------------------------------------------------------------------
python execution\calculate_kloc.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] KLOC calculation failed!
    pause
    exit /b 1
)
echo.
echo [SUCCESS] KLOC calculation complete
echo.

REM Step 2: Collect Quality Metrics (with KLOC integration)
echo [STEP 2/3] Collecting quality metrics with KLOC data...
echo --------------------------------------------------------------------------------
python execution\ado_quality_metrics.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Quality metrics collection failed!
    pause
    exit /b 1
)
echo.
echo [SUCCESS] Quality metrics collection complete
echo.

REM Step 3: Generate Quality Dashboard
echo [STEP 3/3] Generating Quality Dashboard with KLOC metrics...
echo --------------------------------------------------------------------------------
python execution\generate_quality_dashboard.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Dashboard generation failed!
    pause
    exit /b 1
)
echo.
echo [SUCCESS] Dashboard generation complete
echo.

REM Summary
echo ================================================================================
echo TEST COMPLETE - Summary
echo ================================================================================
echo.
echo [✓] KLOC calculated from Git repositories
echo [✓] Quality metrics collected with defect density
echo [✓] Quality Dashboard generated with KLOC display
echo.
echo Output files:
echo   - KLOC Data:         .tmp\observatory\kloc_data.json
echo   - Quality Metrics:   .tmp\observatory\quality_history.json
echo   - Dashboard:         .tmp\observatory\dashboards\quality_dashboard.html
echo.
echo To view the dashboard:
echo   start .tmp\observatory\dashboards\quality_dashboard.html
echo.

pause

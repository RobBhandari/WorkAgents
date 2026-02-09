@echo off
REM Refresh all Observatory dashboards
REM This script runs all metrics collectors and dashboard generators

echo ============================================================
echo Director Observatory - Dashboard Refresh
echo ============================================================
echo.

py execution\refresh_all_dashboards.py

echo.
echo ============================================================
echo Press any key to exit...
pause >nul

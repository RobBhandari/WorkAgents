# PowerShell Script to Set Up DOE Weekly Report Scheduled Task
# Schedules the DOE bug tracker report to run at 7am every Friday

# Configuration
$TaskName = "DOE_Weekly_Bug_Report"
$TaskDescription = "Runs DOE bug tracker and sends weekly email report every Friday at 7am"
$ScriptPath = Join-Path $PSScriptRoot "run_weekly_doe_report.bat"
$WorkingDirectory = Split-Path $PSScriptRoot -Parent
$TriggerTime = "07:00:00"  # 7am
$TriggerDay = "Friday"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "DOE Weekly Report - Scheduled Task Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if script is running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Verify the batch script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: Batch script not found at: $ScriptPath" -ForegroundColor Red
    exit 1
}

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Task Name: $TaskName"
Write-Host "  Schedule: Every $TriggerDay at $TriggerTime"
Write-Host "  Script: $ScriptPath"
Write-Host "  Working Directory: $WorkingDirectory"
Write-Host ""

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "Task '$TaskName' already exists." -ForegroundColor Yellow
    $response = Read-Host "Do you want to replace it? (Y/N)"
    if ($response -ne "Y" -and $response -ne "y") {
        Write-Host "Setup cancelled." -ForegroundColor Yellow
        exit 0
    }

    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create the scheduled task action
$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$ScriptPath`" >> `"$WorkingDirectory\.tmp\scheduled_doe_report.log`" 2>&1" `
    -WorkingDirectory $WorkingDirectory

# Create the scheduled task trigger (Every Friday at 7am)
$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek $TriggerDay `
    -At $TriggerTime

# Create the scheduled task settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# Get current user
$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Limited

# Register the scheduled task
Write-Host "Creating scheduled task..." -ForegroundColor Green
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $TaskDescription `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Force | Out-Null

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "SUCCESS! Scheduled task created successfully." -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Details:" -ForegroundColor Cyan
    Write-Host "  - Runs every $TriggerDay at $TriggerTime"
    Write-Host "  - Logs saved to: $WorkingDirectory\.tmp\scheduled_doe_report.log"
    Write-Host ""
    Write-Host "To manage the task:" -ForegroundColor Yellow
    Write-Host "  - Open Task Scheduler: taskschd.msc"
    Write-Host "  - Find task: Task Scheduler Library > $TaskName"
    Write-Host ""
    Write-Host "To test the task now:" -ForegroundColor Yellow
    Write-Host "  Run: Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host ""

    # Ask if user wants to test now
    $testNow = Read-Host "Do you want to test the task now? (Y/N)"
    if ($testNow -eq "Y" -or $testNow -eq "y") {
        Write-Host ""
        Write-Host "Running task now..." -ForegroundColor Cyan
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "Task started. Check the log file for results." -ForegroundColor Green
    }

} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to create scheduled task" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

Write-Host ""
Read-Host "Press Enter to exit"

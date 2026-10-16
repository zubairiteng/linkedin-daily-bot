<#
.SYNOPSIS
    Registers a Windows Scheduled Task for LinkedIn Daily Bot.
.DESCRIPTION
    Creates or updates a daily task in Windows Task Scheduler to run
    main.py automatically at 10:00 AM Pakistan Standard Time (or local time).
.PARAMETER Time
    The daily trigger time (default: "10:00 AM").
.PARAMETER DryRun
    If specified, configures the task to run with --dry-run.
.PARAMETER Unregister
    If specified, removes the scheduled task.
#>

param (
    [string]$Time = "10:00 AM",
    [switch]$DryRun,
    [switch]$Unregister
)

$TaskName = "LinkedInDailyBot"
$ProjectDir = (Resolve-Path "$PSScriptRoot\..").Path
$PythonExe = Join-Path $ProjectDir "venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    # Fallback to system python if venv doesn't exist
    $PythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}

if ($Unregister) {
    Write-Host "Unregistering scheduled task '$TaskName'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Task '$TaskName' successfully removed." -ForegroundColor Green
    exit 0
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Configuring Windows Task Scheduler for LinkedIn Daily Bot" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Project Directory : $ProjectDir"
Write-Host "Python Executable : $PythonExe"
Write-Host "Scheduled Time    : $Time Daily"
Write-Host "Dry Run Mode      : $(if ($DryRun) { 'YES' } else { 'NO' })"

$Arguments = "main.py"
if ($DryRun) {
    $Arguments += " --dry-run"
}

# Define scheduled task action
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $Arguments `
    -WorkingDirectory $ProjectDir

# Define scheduled task trigger: Daily at specified time
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time

# Define settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# Register the task
try {
    # Unregister existing if present
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description "Autonomous daily LinkedIn news researcher and publisher." | Out-Null

    Write-Host "`n[SUCCESS] Scheduled task '$TaskName' registered successfully!" -ForegroundColor Green
    Write-Host "It will trigger every day at $Time."
    Write-Host "To test run immediately: Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host "To remove task:           .\scripts\schedule_windows.ps1 -Unregister`n"
} catch {
    Write-Host "`n[ERROR] Failed to register task: $_" -ForegroundColor Red
    Write-Host "Note: You may need to run PowerShell as Administrator."
}

@echo off
chcp 65001 >nul
setlocal

set "PROJECT_DIR=C:\Users\РевмаМед10\PycharmProjects\Medical_center"
set "BACKUP_DIR=C:\MedCenterBackups\Postgres"
set "KEEP_DAYS=60"

set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "SCRIPT_DIR=%~dp0"

"%POWERSHELL%" -ExecutionPolicy Bypass -File "%SCRIPT_DIR%backup_db.ps1" -ProjectDir "%PROJECT_DIR%" -BackupDir "%BACKUP_DIR%" -KeepDays %KEEP_DAYS%

set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo Backup failed with code %EXIT_CODE%
) else (
    echo Backup completed successfully
)

endlocal & exit /b %EXIT_CODE%

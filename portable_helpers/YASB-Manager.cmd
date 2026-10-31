@echo off
setlocal
rem YASB Native Portable manager. No elevation or machine-wide configuration.
set "MANAGER=%~dp0YASB-Manager.ps1"
if not exist "%MANAGER%" (
    echo ERROR: Missing YASB-Manager.ps1 next to this file.
    pause
    exit /b 2
)
powershell.exe -NoLogo -NoProfile -File "%MANAGER%"
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
    echo.
    echo YASB Manager ended with error code %CODE%.
    echo If PowerShell blocked the script, unblock the files from your trusted ZIP.
    pause
)
exit /b %CODE%

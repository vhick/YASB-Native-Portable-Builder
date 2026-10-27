@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0YASB-Manager.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo YASB Manager ended with exit code %EXIT_CODE%.
  pause
)
exit /b %EXIT_CODE%

@echo off
setlocal
rem YASB native portable launcher v1.5.2 with login-startup bridge support.
rem No elevated privileges, machine-wide PATH changes, or hidden persistence.
set "BRIDGE=%~dp0YASB-Komorebi-Bridge.ps1"
if not exist "%BRIDGE%" (
  echo ERROR: Missing YASB-Komorebi-Bridge.ps1 next to this launcher.
  if /I not "%~1"=="--autostart" pause
  exit /b 2
)
if /I "%~1"=="--diagnose" goto diagnose
if /I "%~1"=="--autostart" goto autostart
powershell.exe -NoLogo -NoProfile -File "%BRIDGE%"
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo Portable launcher error code %CODE%.
  echo Check the bridge diagnostic before attempting another start.
  pause
)
exit /b %CODE%
:diagnose
powershell.exe -NoLogo -NoProfile -File "%BRIDGE%" -Diagnose
set "CODE=%ERRORLEVEL%"
echo.
pause
exit /b %CODE%
:autostart
rem Called exclusively by the opt-in, current-user Startup shortcut.
powershell.exe -NoLogo -NoProfile -File "%BRIDGE%" -Autostart
exit /b %ERRORLEVEL%

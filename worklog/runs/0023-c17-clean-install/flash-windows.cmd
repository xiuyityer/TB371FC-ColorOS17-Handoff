@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0flash-windows.ps1" %*
set "flash_exit=%errorlevel%"
if "%~1"=="" pause
exit /b %flash_exit%

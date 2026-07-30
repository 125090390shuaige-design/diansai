@echo off
setlocal
title ESP32S3-Cam Flash Tool Launcher

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare_flash_tool.ps1"
if "%ERRORLEVEL%"=="0" exit /b 0

echo.
echo Failed to prepare the flash tool. See the error above.
pause
exit /b 1


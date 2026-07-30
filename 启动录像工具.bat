@echo off
setlocal
title ESP32S3-Cam Recorder Launcher
set "PYTHON_EXE=C:\Program Files\Python314\python.exe"
set "SCRIPT_FILE=%~dp0电脑录像工具\esp32_cam_recorder.py"

if not exist "%PYTHON_EXE%" goto no_python
if not exist "%SCRIPT_FILE%" goto no_script

cd /d "%~dp0"
echo Starting recorder window...
"%PYTHON_EXE%" "%SCRIPT_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" exit /b 0

echo.
echo Recorder failed with exit code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%

:no_python
echo Python was not found at: %PYTHON_EXE%
pause
exit /b 2

:no_script
echo Recorder script was not found at: %SCRIPT_FILE%
pause
exit /b 3

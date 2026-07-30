@echo off
setlocal
title ESP32S3-Cam Recorder Launcher
set "SCRIPT_FILE=%~dp0recorder\esp32_cam_recorder.py"
set "PYTHON_EXE="
set "PYTHON_ARGS="

if not exist "%SCRIPT_FILE%" goto no_script
cd /d "%~dp0"

if exist "C:\Program Files\Python314\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Python314\python.exe"
    goto python_found
)

where py.exe >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=py.exe"
    set "PYTHON_ARGS=-3.14"
    goto python_found
)

where python.exe >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=python.exe"
    goto python_found
)
goto no_python

:python_found
if /i "%~1"=="--check" goto check_environment
"%PYTHON_EXE%" %PYTHON_ARGS% "%SCRIPT_FILE%"
goto finished

:check_environment
"%PYTHON_EXE%" %PYTHON_ARGS% -c "import tkinter; print('Tkinter: OK')"
if errorlevel 1 exit /b 4
"%PYTHON_EXE%" %PYTHON_ARGS% -m py_compile "%SCRIPT_FILE%"
if errorlevel 1 exit /b 5
echo Recorder environment check: OK
exit /b 0

:finished
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" exit /b 0
echo.
echo Recorder failed with exit code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%

:no_python
echo Python 3.14 was not found.
echo Install 64-bit Python with Tcl/Tk, then run this file again.
pause
exit /b 2

:no_script
echo Recorder script was not found at:
echo %SCRIPT_FILE%
pause
exit /b 3

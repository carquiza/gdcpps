@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "CLI_SCRIPT=%SCRIPT_DIR%scripts\gdcpps.py"

if exist "D:\Source\AIResearch\venv\Scripts\python.exe" (
    set "PYTHON_EXE=D:\Source\AIResearch\venv\Scripts\python.exe"
) else if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
) else if exist "%SCRIPT_DIR%venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" "%CLI_SCRIPT%" %*
exit /b %ERRORLEVEL%

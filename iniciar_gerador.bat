@echo off
cd /d "%~dp0"

if exist "Runtime\python.exe" (
    start "Gerador Escalas" /min "Runtime\python.exe" app.py
    timeout /t 2 >nul
    start "" http://localhost:5100
    exit /b
)

where py >nul 2>nul
if %errorlevel%==0 (
    start "Gerador Escalas" /min py app.py
    timeout /t 2 >nul
    start "" http://localhost:5100
    exit /b
)

where python >nul 2>nul
if %errorlevel%==0 (
    start "Gerador Escalas" /min python app.py
    timeout /t 2 >nul
    start "" http://localhost:5100
    exit /b
)

echo Python nao encontrado.
echo Use a pasta portatil com Runtime incluso.
pause


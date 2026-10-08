@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Jennifer AI - Desktop Assistent Launcher
cd /d "%~dp0"

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"
set "PYTHON=%VENV%\Scripts\python.exe"
set "MAIN=%ROOT%main.py"
set "REQUIREMENTS=%ROOT%requirements.txt"
set "PYCMD="

echo.
echo ======================================================
echo    Jennifer AI ^| Open-Source Windows Desktop AI
echo    Taal: Nederlands (Basis) ^| Lokaal: Ollama
echo ======================================================
echo.

if exist "%PYTHON%" (
  set "PYCMD=%PYTHON%"
)

if not defined PYCMD if exist "%ROOT%python.exe" (
  set "PYCMD=%ROOT%python.exe"
)

if not defined PYCMD if exist "%SystemRoot%\py.exe" (
  set "PYCMD=%SystemRoot%\py.exe"
)

if not defined PYCMD (
  for /f "delims=" %%I in ('where.exe py 2^>nul') do (
    set "CAND=%%~I"
    if exist "!CAND!" (
      set "PYCMD=!CAND!"
      goto :foundPython
    )
  )
)

if not defined PYCMD (
  for /f "delims=" %%I in ('where.exe python 2^>nul') do (
    set "CAND=%%~I"
    echo !CAND! | findstr /i "WindowsApps" >nul
    if errorlevel 1 if exist "!CAND!" (
      set "PYCMD=!CAND!"
      goto :foundPython
    )
  )
)

:foundPython
if not defined PYCMD (
  echo [FOUT] Geen Python installatie gevonden. Installeer Python 3.11 of nieuwer.
  pause
  exit /b 1
)

echo [*] Geselecteerde Python runtime: "!PYCMD!"

REM Start Jennifer AI
echo [*] Jennifer AI wordt gestart...
"!PYCMD!" "%MAIN%"
if errorlevel 1 (
  echo.
  echo [INFO] Applicatie gestopt met foutcode %errorlevel%.
  pause
)

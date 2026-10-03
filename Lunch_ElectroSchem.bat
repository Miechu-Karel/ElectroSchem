@echo off
REM Uruchamia ElectroSchem przy użyciu lokalnego Pythona 3.14.
set "ELECTROSCHEM_PYTHON=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not exist "%ELECTROSCHEM_PYTHON%" (
  echo Nie znaleziono Pythona 3.14: %ELECTROSCHEM_PYTHON%
  pause
  exit /b 1
)
"%ELECTROSCHEM_PYTHON%" "%~dp0main.py"

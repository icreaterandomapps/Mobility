@echo off
rem Builds Mobility.exe with PyInstaller (run this on Windows, needs Python 3 with tkinter).
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py -3
%PY% --version >nul 2>nul || (echo Python 3 was not found. Install it from python.org and tick "Add to PATH". & pause & exit /b 1)

echo Installing / updating PyInstaller...
%PY% -m pip install --upgrade pyinstaller || (echo pip failed. & pause & exit /b 1)

echo Building Mobility.exe ...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name Mobility ^
  --icon "%~dp0Res\mobility.ico" ^
  --add-data "%~dp0Res\mobility.ico;Res" ^
  --add-data "%~dp0Res\mobility_64.png;Res" ^
  --add-data "%~dp0Res\ui;Res\ui" ^
  --distpath "%~dp0." ^
  --workpath "%TEMP%\mobility-build" ^
  --specpath "%TEMP%\mobility-build" ^
  "%~dp0Mobility.pyw"
if errorlevel 1 (echo. & echo Build failed. & pause & exit /b 1)

rmdir /s /q "%TEMP%\mobility-build" 2>nul
echo.
echo Done: "%~dp0Mobility.exe"
echo Keep it next to the "Res", "Custom Tools" and "Administrative Tools" folders.
pause

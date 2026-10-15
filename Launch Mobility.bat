@echo off
rem Starts Mobility: the built .exe if present, otherwise the Python script (no console window).
cd /d "%~dp0"
if exist "%~dp0Mobility.exe" (start "" "%~dp0Mobility.exe" & exit /b)
where pyw >nul 2>nul && (start "" pyw "%~dp0Mobility.pyw" & exit /b)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0Mobility.pyw" & exit /b)
where py >nul 2>nul && (start "" py -3w "%~dp0Mobility.pyw" & exit /b)
powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [void][System.Windows.Forms.MessageBox]::Show('Mobility needs Python 3 (with tkinter) installed, or run build.bat once to make Mobility.exe.', 'Mobility')"

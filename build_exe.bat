@echo off
rem Build dist\SwathCut.exe: one-file windowed app, runs without Python.
rem Needs: pip install pyinstaller netCDF4 cftime numpy matplotlib
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onefile --windowed --name SwathCut --icon assets\swathcut.ico --add-data "assets\swathcut.ico;assets" --paths src --collect-all netCDF4 --hidden-import cftime --hidden-import matplotlib.backends.backend_tkagg src\swathcut.py
if errorlevel 1 exit /b 1
echo Built: %~dp0dist\SwathCut.exe

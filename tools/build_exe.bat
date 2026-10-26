@echo off
REM Génère dist\UniversalLinuxBuilder\UniversalLinuxBuilder.exe (non testé en CI).
REM Prérequis : python -m pip install -r requirements.txt pyinstaller
cd /d "%~dp0\.."
python -m PyInstaller --noconfirm --windowed --name UniversalLinuxBuilder main.py
echo.
echo Résultat : dist\UniversalLinuxBuilder\UniversalLinuxBuilder.exe
pause

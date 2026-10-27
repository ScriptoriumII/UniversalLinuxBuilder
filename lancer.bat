@echo off
REM Universal Linux Builder - lanceur pour un poste Windows neuf.
REM Verifie/installe Python, cree un environnement isole (.venv),
REM installe PySide6, controle WSL2 puis lance l'application.
REM Utilisation : double-clic, ou  lancer.bat --check  (diagnostic seul)
setlocal
cd /d "%~dp0"
chcp 65001 >nul

set "PY="
call :find
if defined PY goto have_python

echo Python 3.10 ou plus recent est introuvable.
where winget >nul 2>nul
if errorlevel 1 (
  echo winget est absent. Installe Python 3.12 depuis https://www.python.org/downloads/
  echo en cochant "Add python.exe to PATH", puis relance ce fichier.
  pause
  exit /b 1
)
echo Installation de Python 3.12 avec winget...
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set PY="%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PY call :find
if not defined PY (
  echo Python est installe mais pas encore visible : ferme cette fenetre puis relance lancer.bat.
  pause
  exit /b 1
)

:have_python
if not exist ".venv\Scripts\python.exe" (
  echo Creation de l'environnement isole .venv ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Impossible de creer .venv
    pause
    exit /b 1
  )
)

".venv\Scripts\python.exe" main.py %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" pause
exit /b %CODE%

:find
REM Le "python" du Microsoft Store n'est qu'un raccourci : on teste vraiment la version.
for %%C in ("py -3" "python") do (
  if not defined PY (
    %%~C -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul && set "PY=%%~C"
  )
)
exit /b 0

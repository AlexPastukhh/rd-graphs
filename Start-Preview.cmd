@echo off
setlocal
set PYTHONUTF8=1
set PYTHONDONTWRITEBYTECODE=1
set "RDG_PREVIEW_HOME=%LOCALAPPDATA%\RDG-ManualPreview"
set "RDG_PREVIEW_PYTHON=%RDG_PREVIEW_HOME%\venv\Scripts\python.exe"
if exist "%RDG_PREVIEW_PYTHON%" goto dependencies
py -3 -m venv "%RDG_PREVIEW_HOME%\venv"
if errorlevel 1 goto failed
:dependencies
"%RDG_PREVIEW_PYTHON%" -c "import fido2,cryptography,tzdata" >nul 2>&1
if not errorlevel 1 goto launch
"%RDG_PREVIEW_PYTHON%" -m pip install --disable-pip-version-check -r "%~dp0tools\requirements-preview.txt"
if errorlevel 1 goto failed
:launch
"%RDG_PREVIEW_PYTHON%" -X utf8 -B "%~dp0tools\rdg-preview.py" --test-preview --data-dir "%RDG_PREVIEW_HOME%\data" --port 8794 --open-browser
if errorlevel 1 goto failed
goto end
:failed
echo RDG preview could not start. Keep this window to inspect the error.
pause
:end
endlocal

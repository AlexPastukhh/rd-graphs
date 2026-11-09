@echo off
setlocal
set PYTHONUTF8=1
set PYTHONDONTWRITEBYTECODE=1
set "RDG_DECISION_PREVIEW_HOME=%LOCALAPPDATA%\RDG-DecisionPreview"
set "RDG_DECISION_PREVIEW_PYTHON=%RDG_DECISION_PREVIEW_HOME%\venv\Scripts\python.exe"
where node >nul 2>&1
if errorlevel 1 goto node_missing
node -e "process.exit(Math.sign(Number(process.versions.node.split('.')[0])-18) === -1 ? 1 : 0)" >nul 2>&1
if errorlevel 1 goto node_missing
if exist "%RDG_DECISION_PREVIEW_PYTHON%" goto dependencies
where py >nul 2>&1
if errorlevel 1 goto python_bootstrap
py -3 -m venv "%RDG_DECISION_PREVIEW_HOME%\venv"
if errorlevel 1 goto failed
goto dependencies
:python_bootstrap
python -m venv "%RDG_DECISION_PREVIEW_HOME%\venv"
if errorlevel 1 goto failed
:dependencies
"%RDG_DECISION_PREVIEW_PYTHON%" -c "from zoneinfo import ZoneInfo; ZoneInfo('Asia/Bangkok')" >nul 2>&1
if not errorlevel 1 goto launch
"%RDG_DECISION_PREVIEW_PYTHON%" -m pip install --disable-pip-version-check -r "%~dp0tools\requirements-decision-preview.txt"
if errorlevel 1 goto failed
:launch
echo RDG Decision preview. Keep this console open while testing.
echo Test data: %RDG_DECISION_PREVIEW_HOME%\data
"%RDG_DECISION_PREVIEW_PYTHON%" -X utf8 -B "%~dp0tools\rdg-preview.py" --test-preview --model-profile rdg-decision-v1 --data-dir "%RDG_DECISION_PREVIEW_HOME%\data" --port 8795 --open-browser
if errorlevel 1 goto failed
goto end
:node_missing
echo Node.js 18 or newer must be available as the node command.
goto failed
:failed
echo RDG Decision preview could not start. Keep this window to inspect the error.
pause
:end
endlocal

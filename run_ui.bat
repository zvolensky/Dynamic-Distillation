@echo off
setlocal

set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%"

set "PYTHONPATH=%REPO_ROOT%src;%PYTHONPATH%"

call "%REPO_ROOT%stop_ui.bat"
timeout /t 1 /nobreak >nul

start "Dynamic Distillation UI" cmd /k python -m streamlit run ui\streamlit_app.py --server.headless true
timeout /t 3 /nobreak >nul
start "" http://localhost:8501

endlocal

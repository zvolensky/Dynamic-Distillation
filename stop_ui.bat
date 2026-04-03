@echo off
setlocal

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8501" ^| findstr "LISTENING"') do (
    echo Stopping process on port 8501: PID %%P
    taskkill /PID %%P /F >nul 2>&1
)

echo Streamlit UI processes on port 8501 have been stopped.
echo Note: active simulation processes are not stopped by stop_ui.bat.

endlocal

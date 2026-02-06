@echo off
setlocal EnableExtensions
pushd "C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\scilab"
echo [BAT] pwd: %CD%
echo [BAT] pythonExe: "C:/Users/Thoma/Documents/Python Scripts/Dynamic_DistillationII/.venv/Scripts/python.exe"
echo [BAT] bridgePy:  "C:/Users/Thoma/Documents/Python Scripts/Dynamic_DistillationII/thermo_bridge.py"
echo [BAT] reqFile:   "C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\scilab\thermo_request.txt"
echo [BAT] respFile:  "C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\scilab\thermo_response.txt"
call "C:/Users/Thoma/Documents/Python Scripts/Dynamic_DistillationII/.venv/Scripts/python.exe" "C:/Users/Thoma/Documents/Python Scripts/Dynamic_DistillationII/thermo_bridge.py" "C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\scilab\thermo_request.txt" "C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\scilab\thermo_response.txt"
set ERR=%ERRORLEVEL%
echo [BAT] python exit code: %ERR%
popd
exit /b %ERR%

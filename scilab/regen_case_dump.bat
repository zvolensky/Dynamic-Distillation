@echo off
setlocal EnableExtensions
pushd "C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\scilab"
echo [BAT] pwd: %CD%
echo [BAT] python: "C:/Users/Thoma/Documents/Python Scripts/Dynamic_DistillationII/.venv/Scripts/python.exe"
echo [BAT] case_dump_py: "C:/Users/Thoma/Documents/Python Scripts/Dynamic_DistillationII/case_dump.py"
echo [BAT] excel_path: "C:/Users/Thoma/Documents/Python Scripts/Dynamic_DistillationII/distillation_column_template.xlsx"
echo [BAT] out_file: "C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\scilab\case_dump_out.txt"
call "C:/Users/Thoma/Documents/Python Scripts/Dynamic_DistillationII/.venv/Scripts/python.exe" "C:/Users/Thoma/Documents/Python Scripts/Dynamic_DistillationII/case_dump.py" "C:/Users/Thoma/Documents/Python Scripts/Dynamic_DistillationII/distillation_column_template.xlsx" "C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\scilab\case_dump_out.txt"
set ERR=%ERRORLEVEL%
echo [BAT] python exit code: %ERR%
popd
exit /b %ERR%

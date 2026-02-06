// ============================================================================
// dd_regen_case_dump.sci
// Regenerate case_dump_out.txt by calling Python case_dump.py (Windows)
//
// Updated: 2026-01-20
//
// Notes:
// - No exists() calls (compatible with older Scilab builds)
// - Uses a temporary BAT file to avoid cmd quoting issues
// - Determines success by output file existence (dos() status can be unreliable)
// ============================================================================

function out_file = dd_regen_case_dump(excel_path, out_file, python_exe, case_dump_py)

    // Defaults
    if argn(2) < 1 | excel_path == [] | excel_path == "" then
        excel_path = fullfile(pwd(), "..", "distillation_column_template.xlsx");
    end
    if argn(2) < 2 | out_file == [] | out_file == "" then
        out_file = fullfile(pwd(), "case_dump_out.txt");
    end
    if argn(2) < 3 | python_exe == [] | python_exe == "" then
        python_exe = "python";
    end
    if argn(2) < 4 | case_dump_py == [] | case_dump_py == "" then
        case_dump_py = fullfile(pwd(), "..", "case_dump.py");
    end

    excel_path   = string(excel_path);
    out_file     = string(out_file);
    python_exe   = string(python_exe);
    case_dump_py = string(case_dump_py);

    if ~is_absolute_path_(excel_path)   then excel_path   = fullfile(pwd(), excel_path);   end
    if ~is_absolute_path_(out_file)     then out_file     = fullfile(pwd(), out_file);     end
    if ~is_absolute_path_(case_dump_py) then case_dump_py = fullfile(pwd(), case_dump_py); end

    stdout_path = fullfile(pwd(), "case_dump_py_stdout.txt");
    stderr_path = fullfile(pwd(), "case_dump_py_stderr.txt");
    bat_path    = fullfile(pwd(), "regen_case_dump.bat");

    q = char(34); // "

    // Write BAT
    bat = [
        "@echo off"
        "setlocal EnableExtensions"
        "pushd " + q + pwd() + q
        "echo [BAT] pwd: %CD%"
        "echo [BAT] python: " + q + python_exe + q
        "echo [BAT] case_dump_py: " + q + case_dump_py + q
        "echo [BAT] excel_path: " + q + excel_path + q
        "echo [BAT] out_file: " + q + out_file + q
        "call " + q + python_exe + q + " " + q + case_dump_py + q + " " + q + excel_path + q + " " + q + out_file + q
        "set ERR=%ERRORLEVEL%"
        "echo [BAT] python exit code: %ERR%"
        "popd"
        "exit /b %ERR%"
    ];
    mputl(bat, bat_path);

    // Delete old logs if present
    if isfile(stdout_path) then deletefile(stdout_path); end
    if isfile(stderr_path) then deletefile(stderr_path); end

    // Run BAT with redirection
    cmd = "cmd /c " + q + bat_path + q + ...
          " 1>" + q + stdout_path + q + ...
          " 2>" + q + stderr_path + q;

    dos(cmd); // ignore status; validate by file existence

    // If output missing, print logs and fail
    if ~isfile(out_file) then
        disp("Regen failed: output file not produced:");
        disp(out_file);
        disp("CMD was:");
        disp(cmd);

        if isfile(stdout_path) then
            disp("case_dump_py_stdout.txt:");
            disp(mgetl(stdout_path));
        end
        if isfile(stderr_path) then
            disp("case_dump_py_stderr.txt:");
            disp(mgetl(stderr_path));
        end

        error("case_dump_out.txt was not produced.");
    end

endfunction


function tf = is_absolute_path_(p)
    p = string(p);
    tf = %f;
    if length(p) >= 2 & part(p,2) == ":" then tf = %t; end
endfunction
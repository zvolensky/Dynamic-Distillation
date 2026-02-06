// ============================================================================
// dd_call_thermo.sci
// Call thermo_bridge.py from Scilab reliably (Windows)
//
// Updated: 2026-01-20
//
// IMPORTANT:
// - Scilab dos()/host() return codes can be unreliable with spaces/redirection.
// - Therefore: SUCCESS = response file exists AND is non-empty.
// - Always writes:
//     thermo_bridge_stdout.txt
//     thermo_bridge_stderr.txt
// ============================================================================

function ok = dd_call_thermo(pythonExe, bridgePy, reqFile, respFile)

    ok = %f;

    // Defaults
    if argn(2) < 1 | pythonExe == [] | pythonExe == "" then
        pythonExe = "python";
    end
    if argn(2) < 2 | bridgePy == [] | bridgePy == "" then
        bridgePy = "thermo_bridge.py";
    end
    if argn(2) < 3 | reqFile == [] | reqFile == "" then
        reqFile = "thermo_request.txt";
    end
    if argn(2) < 4 | respFile == [] | respFile == "" then
        respFile = "thermo_response.txt";
    end

    pythonExe = string(pythonExe);
    bridgePy  = string(bridgePy);
    reqFile   = string(reqFile);
    respFile  = string(respFile);

    // Resolve relative paths relative to current folder (scilab folder)
    if ~is_absolute_path_(bridgePy) then bridgePy = fullfile(pwd(), bridgePy); end
    if ~is_absolute_path_(reqFile)  then reqFile  = fullfile(pwd(), reqFile);  end
    if ~is_absolute_path_(respFile) then respFile = fullfile(pwd(), respFile); end

    // Logs + bat
    stdout_path = fullfile(pwd(), "thermo_bridge_stdout.txt");
    stderr_path = fullfile(pwd(), "thermo_bridge_stderr.txt");
    bat_path    = fullfile(pwd(), "call_thermo_bridge.bat");

    q = char(34); // "

    // Delete old artifacts (avoid false positives)
    if isfile(respFile) then deletefile(respFile); end
    if isfile(stdout_path) then deletefile(stdout_path); end
    if isfile(stderr_path) then deletefile(stderr_path); end

    // Write BAT (keeps quoting sane)
    bat = [
        "@echo off"
        "setlocal EnableExtensions"
        "pushd " + q + pwd() + q
        "echo [BAT] pwd: %CD%"
        "echo [BAT] pythonExe: " + q + pythonExe + q
        "echo [BAT] bridgePy:  " + q + bridgePy + q
        "echo [BAT] reqFile:   " + q + reqFile + q
        "echo [BAT] respFile:  " + q + respFile + q
        "call " + q + pythonExe + q + " " + q + bridgePy + q + " " + q + reqFile + q + " " + q + respFile + q
        "set ERR=%ERRORLEVEL%"
        "echo [BAT] python exit code: %ERR%"
        "popd"
        "exit /b %ERR%"
    ];
    mputl(bat, bat_path);

    // Execute BAT with redirection. Do NOT trust the return code.
    cmd = "cmd /c " + q + bat_path + q + ...
          " 1>" + q + stdout_path + q + ...
          " 2>" + q + stderr_path + q;

    dos(cmd);

    // Validate: response file exists and is non-empty
    if ~isfile(respFile) then
        disp("dd_call_thermo: response file not produced:");
        disp(respFile);
        disp("CMD:");
        disp(cmd);
        if isfile(stdout_path) then
            disp("thermo_bridge_stdout.txt:");
            disp(mgetl(stdout_path));
        end
        if isfile(stderr_path) then
            disp("thermo_bridge_stderr.txt:");
            disp(mgetl(stderr_path));
        end
        error("thermo_bridge.py failed (no response file).");
    end

    L = mgetl(respFile);
    if size(L,"r") == 0 then
        disp("dd_call_thermo: response file is empty:");
        disp(respFile);
        if isfile(stdout_path) then
            disp("thermo_bridge_stdout.txt:");
            disp(mgetl(stdout_path));
        end
        if isfile(stderr_path) then
            disp("thermo_bridge_stderr.txt:");
            disp(mgetl(stderr_path));
        end
        error("thermo_bridge.py failed (empty response).");
    end

    ok = %t;

endfunction


function tf = is_absolute_path_(p)
    p = string(p);
    tf = %f;
    if length(p) >= 2 & part(p,2) == ":" then tf = %t; end
endfunction
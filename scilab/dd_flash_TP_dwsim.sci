// ============================================================================
// dd_flash_TP_dwsim.sci
// TP flash via Python + DWSIM (Scilab Python toolbox)
//
// Provides:
//   [x, y, HL, HV] = dd_flash_TP(T_F, P_psia, z)
//
// Behavior:
//   - Adds Scilab cwd to Python sys.path
//   - Imports dwsim_flash_tp.py
//   - Calls flash_tp(T_F, P_psia, z) -> (x, y, HL, HV)
//
// Timestamp: 2026-01-20
// ============================================================================

function [x, y, HL, HV] = dd_flash_TP(T_F, P_psia, z)

    // ---- Validate inputs
    if typeof(T_F) <> "constant" then error("dd_flash_TP: T_F must be numeric"); end
    if typeof(P_psia) <> "constant" then error("dd_flash_TP: P_psia must be numeric"); end
    if typeof(z) <> "constant" then error("dd_flash_TP: z must be a numeric vector"); end

    z = matrix(z, 1, -1);
    NC = size(z, "*");

    // ---- Check Python toolbox availability (portable)
    if ~isdef("pyImport") then
        error("Python toolbox missing: pyImport is not defined in this Scilab.");
    end
    if ~isdef("pyCall") then
        error("Python toolbox missing: pyCall is not defined in this Scilab.");
    end

    // ---- Add current directory to Python sys.path
    try
        sys = pyImport("sys");
        cwd = pwd();
        // sys.path.insert(0, cwd)
        pyCall(sys, "path.insert", 0, cwd);
    catch
        error("Failed to add current directory to Python sys.path (pyImport/pyCall issue).");
    end

    // ---- Import module
    try
        mod = pyImport("dwsim_flash_tp");
    catch
        error("Failed to import Python module dwsim_flash_tp. Put dwsim_flash_tp.py in the scilab folder or on Python sys.path.");
    end

    // ---- Call flash
    try
        res = pyCall(mod, "flash_tp", T_F, P_psia, z);
    catch
        error("Python call failed: dwsim_flash_tp.flash_tp(T_F, P_psia, z)");
    end

    // ---- Unpack (expect list of length 4)
    if typeof(res) <> "list" then
        error("flash_tp did not return a tuple/list. Expected (x, y, HL, HV).");
    end
    if length(res) <> 4 then
        error("flash_tp returned wrong number of values. Expected 4: (x, y, HL, HV).");
    end

    x_raw  = res(1);
    y_raw  = res(2);
    HL_raw = res(3);
    HV_raw = res(4);

    x = matrix(x_raw, 1, NC);
    y = matrix(y_raw, 1, NC);
    HL = HL_raw;
    HV = HV_raw;

    // ---- Validate
    if abs(sum(x) - 1.0) > 1e-6 then error("dd_flash_TP: x does not sum to 1"); end
    if abs(sum(y) - 1.0) > 1e-6 then error("dd_flash_TP: y does not sum to 1"); end
    if (HL == 0) & (HV == 0) then
        error("dd_flash_TP: HL and HV both zero; backend likely not working.");
    end

endfunction
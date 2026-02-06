// ============================================================================
// run_column_T.sce (UPDATED FOR RIGOROUS RUN)
// ============================================================================
clear;
clc();
funcprot(0);

// ---------------------------------------------------------------------------
// USER SETTINGS & PATHS
// ---------------------------------------------------------------------------
CASE_FILE   = "case_dump_out.txt";
EXCEL_PATH  = "distillation_column_template.xlsx"; // Required for DWSIM bridge

// UPDATE: Pointing to your verified Python 3.13 path
pythonExe   = "C:/Python313/python.exe"; 
bridgePy    = "thermo_bridge.py";

DT_S        = 0.5;          // Reduced DT for stability in rigorous mode
T_END_S     = 60.0;         // Short test run
LOG_EVERY   = 1;            
PRINT_EVERY = 5;           

OUT_DIR     = "run_out";
DIAG_STAGE  = 12;           // Monitoring the feed stage

// ---------------------------------------------------------------------------
// LOAD SUPPORT CODE
// ---------------------------------------------------------------------------
exec("dd_utils.sci", -1);
exec("dd_load_case.sci", -1);
exec("dd_call_thermo.sci", -1);
exec("dd_write_thermo_request.sci", -1);
exec("dd_parse_thermo_response.sci", -1);
exec("dd_hydraulics_francis.sci", -1);

// UPDATE: Loading the FLASH-enabled RHS
exec("dd_column_rhs_T_flash.sci", -1); 

// ---------------------------------------------------------------------------
// INITIALIZATION
// ---------------------------------------------------------------------------
col = dd_load_case(CASE_FILE);
// Inject paths into the col struct so the RHS can find Python
col.pythonExe = pythonExe;
col.bridgePy  = bridgePy;
col.excelPath = EXCEL_PATH;

y = col.y0;
t = 0;
n_steps = floor(T_END_S / DT_S);

mprintf("Starting Rigorous Run with Python 3.13...\n");

// ---------------------------------------------------------------------------
// TIME MARCH (EULER)
// ---------------------------------------------------------------------------
for step = 1:n_steps
    // Calculate derivatives using the Flash-enabled RHS
    // This will now trigger thermo_bridge.py via your C:/Python313/ path
    ydot = column_rhs(t, y, col);
    
    // Euler Step
    y = y + ydot * DT_S;
    t = t + DT_S;
    
    // Access global diagnostics updated by the RHS
    global DD_DIAG;
    
    if modulo(step, PRINT_EVERY) == 0 then
        st = DIAG_STAGE;
        mprintf("step %d/%d | t=%.1fs | V[%d]=%.2f | L[%d]=%.2f | HL=%.1f\n", ..
                step, n_steps, t, st, DD_DIAG.V_LBMOLPH(st), ..
                DD_DIAG.L_LBMOLPH(st), DD_DIAG.HL(st));
    end
end

mprintf("RUN COMPLETE. Check %s for CSV results.\n", OUT_DIR);

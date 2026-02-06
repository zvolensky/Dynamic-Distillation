// ============================================================================
// run_column_T.sce
// Explicit dynamic column runner (FIXED Δt)
// CSV logging + rich console output
// Reads diagnostics via global DD_DIAG (preferred) or RHS list return
// Timestamp: 2026-01-20
// ============================================================================

clear;
clc();
funcprot(0);

// ---------------------------------------------------------------------------
// USER SETTINGS
// ---------------------------------------------------------------------------
CASE_FILE   = "case_dump_out.txt";

DT_S        = 5.0;          // time step (seconds)
T_END_S     = 300.0;        // total simulation time
LOG_EVERY   = 1;            // CSV every step
PRINT_EVERY = 10;           // console every N steps

OUT_DIR     = "run_out";
DIAG_STAGE  = 2;            // avoid condenser/reboiler when possible

// ---------------------------------------------------------------------------
// LOAD SUPPORT CODE
// ---------------------------------------------------------------------------
exec("dd_utils.sci", -1);
exec("dd_load_case.sci", -1);
exec("dd_column_rhs_T.sci", -1);   // this must define column_rhs()

// ---------------------------------------------------------------------------
// LOAD CASE
// ---------------------------------------------------------------------------
col = dd_load_case(CASE_FILE);

if ~isfield(col,"y0") then error("Missing y0 in case struct"); end
if ~isfield(col,"N_STAGES") then error("Missing N_STAGES in case struct"); end
if ~isfield(col,"N_COMPONENTS") then error("Missing N_COMPONENTS in case struct"); end

N  = col.N_STAGES;
NC = col.N_COMPONENTS;

y = col.y0;

// Guard DIAG_STAGE
if N < 3 then
    DIAG_STAGE = 1;
else
    if DIAG_STAGE < 2 then DIAG_STAGE = 2; end
    if DIAG_STAGE > (N-1) then DIAG_STAGE = N-1; end
end

n_steps = floor(T_END_S / DT_S);
t = 0.0;

// ---------------------------------------------------------------------------
// OUTPUT DIRECTORY + FILENAMES
// ---------------------------------------------------------------------------
if ~isdir(OUT_DIR) then mkdir(OUT_DIR); end
stamp = string(getdate("s"));

stage_csv = OUT_DIR + filesep() + "run_column_T_stage_" + stamp + ".csv";
log_csv   = OUT_DIR + filesep() + "run_column_T_log_"   + stamp + ".csv";

// ---------------------------------------------------------------------------
// CONSOLE HEADER
// ---------------------------------------------------------------------------
disp("==================================================");
disp("RUN START: explicit time-march (Euler)");
mprintf("CASE_FILE: %s\n", CASE_FILE);
mprintf("N_STAGES: %d | N_COMPONENTS: %d\n", N, NC);
mprintf("DT_S: %.3f | T_END_S: %.3f | n_steps: %d\n", DT_S, T_END_S, n_steps);
mprintf("LOG_EVERY: %d | PRINT_EVERY: %d\n", LOG_EVERY, PRINT_EVERY);
mprintf("DIAG_STAGE: %d\n", DIAG_STAGE);
disp("CSV outputs:");
disp(stage_csv);
disp(log_csv);
disp("==================================================");

t_run_start = timer();

// ---------------------------------------------------------------------------
// CSV HEADERS (same structure as your historical stage file)
// ---------------------------------------------------------------------------
stage_hdr = "step,t_hr,stage,ML_lbmol,dMLdt_lbmolph,L_lbmolph,V_lbmolph";
for k=1:NC
    stage_hdr = stage_hdr + ",x_" + string(k);
end
for k=1:NC
    stage_hdr = stage_hdr + ",y_" + string(k);
end
stage_hdr = stage_hdr + ",HL,HV";
mputl(stage_hdr, stage_csv);

mputl("step,t_hr", log_csv);

// ---------------------------------------------------------------------------
// DIAGNOSTICS CHANNEL (GLOBAL)
// ---------------------------------------------------------------------------
global DD_DIAG;
DD_DIAG = struct();   // cleared at run start

function diag = get_diag_or_die()
    global DD_DIAG;
    if typeof(DD_DIAG) <> "st" then
        error("DD_DIAG not set by RHS. Your RHS must set global DD_DIAG each call, or return list(dydt,diag).");
    end
    diag = DD_DIAG;

    // Hard requirements for your legacy CSV + flash proof
    if ~isfield(diag,"ML") then error("DD_DIAG missing ML"); end
    if ~isfield(diag,"dMLdt") then error("DD_DIAG missing dMLdt"); end
    if ~isfield(diag,"L_LBMOLPH") then error("DD_DIAG missing L_LBMOLPH"); end
    if ~isfield(diag,"V_LBMOLPH") then error("DD_DIAG missing V_LBMOLPH"); end
    if ~isfield(diag,"X") then error("DD_DIAG missing X"); end
    if ~isfield(diag,"Y") then error("DD_DIAG missing Y"); end
    if ~isfield(diag,"HL") then error("DD_DIAG missing HL"); end
    if ~isfield(diag,"HV") then error("DD_DIAG missing HV"); end
endfunction

// ---------------------------------------------------------------------------
// MAIN LOOP
// ---------------------------------------------------------------------------
for step = 1:n_steps

    // RHS may return either:
    //  - dydt (vector), and set global DD_DIAG
    //  - list(dydt, diag)
    res = column_rhs(t, y, col);

    if typeof(res) == "list" then
        dydt = res(1);
        // If RHS returned diag explicitly, store it to global so everything uses one path
        global DD_DIAG;
        DD_DIAG = res(2);
    else
        dydt = res;
    end

    // Pull diag (must exist now)
    diag = get_diag_or_die();

    // Integrate
    y = y + DT_S * dydt;
    t = t + DT_S;

    // Logging
    if modulo(step, LOG_EVERY) == 0 then
        t_hr = t / 3600.0;

        for i=1:N
            row = string(step) + "," + string(t_hr) + "," + string(i);

            row = row + "," + string(diag.ML(i));
            row = row + "," + string(diag.dMLdt(i));
            row = row + "," + string(diag.L_LBMOLPH(i));
            row = row + "," + string(diag.V_LBMOLPH(i));

            for k=1:NC
                row = row + "," + string(diag.X(i,k));
            end
            for k=1:NC
                row = row + "," + string(diag.Y(i,k));
            end

            row = row + "," + string(diag.HL(i));
            row = row + "," + string(diag.HV(i));

            mputl(row, stage_csv);
        end

        mputl(string(step) + "," + string(t_hr), log_csv);
    end

    // Console progress + flash proof (HL/HV shown)
    if modulo(step, PRINT_EVERY) == 0 then
        st = DIAG_STAGE;
        mprintf("step %d/%d | t=%.1fs | ML[%d]=%.6f | L[%d]=%.6f | V[%d]=%.6f | HL[%d]=%.6f | HV[%d]=%.6f\n", ..
            step, n_steps, t, ..
            st, diag.ML(st), ..
            st, diag.L_LBMOLPH(st), ..
            st, diag.V_LBMOLPH(st), ..
            st, diag.HL(st), ..
            st, diag.HV(st));
    end
end

disp("==================================================");
disp("RUN COMPLETE");
disp("CSV files written:");
disp(stage_csv);
disp(log_csv);
mprintf("Wall time: %.3f s\n", timer() - t_run_start);
disp("==================================================");

funcprot(1);

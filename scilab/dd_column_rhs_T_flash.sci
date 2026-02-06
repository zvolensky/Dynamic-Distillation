// ============================================================================
// dd_column_rhs_T_flash.sci
// Dynamic column RHS with explicit TP flash via DWSIM (Python)
//
// GUARANTEES:
//   - Flash is executed once per stage per RHS call
//   - Diagnostics are published via global DD_DIAG
//   - Flash call counter increments deterministically
//
// DOES NOT YET INCLUDE:
//   - Francis weir hydraulics
//   - Vapor traffic model
//
// Timestamp: 2026-01-20
// ============================================================================

// ---- Global diagnostics channel (Option A)
global DD_DIAG;
DD_DIAG = struct();

function dydt = column_rhs(t, y, col)

    // ------------------------------------------------------------------------
    // Dimensions
    // ------------------------------------------------------------------------
    N  = col.N_STAGES;
    NC = col.N_COMPONENTS;

    // ------------------------------------------------------------------------
    // Unpack state vector
    // ------------------------------------------------------------------------
    idx = 1;
    ML  = y(idx:idx+N-1);                 // liquid holdup [lbmol]
    idx = idx + N;

    X = matrix(y(idx:idx+N*NC-1), N, NC); // liquid composition

    // ------------------------------------------------------------------------
    // Boundary flows (lbmol/s)
    // ------------------------------------------------------------------------
    D = zeros(N,1);
    F = zeros(N,1);
    B = zeros(N,1);

    if size(col.D_LBMOLPH,"*")==N then D = col.D_LBMOLPH(:)/3600; end
    if size(col.F_LBMOLPH,"*")==N then F = col.F_LBMOLPH(:)/3600; end
    if size(col.B_LBMOLPH,"*")==N then B = col.B_LBMOLPH(:)/3600; end

    // ------------------------------------------------------------------------
    // Pressure & temperature profiles
    // ------------------------------------------------------------------------
    P = col.P_psia(:);
    T = col.T_F(:);

    // ------------------------------------------------------------------------
    // Allocate flash results
    // ------------------------------------------------------------------------
    Y  = zeros(N,NC);
    HL = zeros(N,1);
    HV = zeros(N,1);

    // ------------------------------------------------------------------------
    // Liquid & vapor flows (lbmol/s) — hydraulics comes later
    // ------------------------------------------------------------------------
    L = zeros(N,1);
    V = zeros(N,1);

    // ------------------------------------------------------------------------
    // Flash loop (MANDATORY)
    // ------------------------------------------------------------------------
    global DD_DIAG;
    if ~isfield(DD_DIAG,"N_FLASH_CALLS") then
        DD_DIAG.N_FLASH_CALLS = 0;
    end

    for i = 1:N

        // Overall composition approximation
        z = X(i,:);

        // Hard requirement: DWSIM flash must exist
        if ~exists("dd_flash_TP","function") then
            error("dd_flash_TP(T_F,P_psia,z) not found — DWSIM flash REQUIRED");
        end

        // Perform TP flash
        [x_i, y_i, HL_i, HV_i] = dd_flash_TP(T(i), P(i), z);

        X(i,:) = x_i;
        Y(i,:) = y_i;
        HL(i)  = HL_i;
        HV(i)  = HV_i;

        DD_DIAG.N_FLASH_CALLS = DD_DIAG.N_FLASH_CALLS + 1;
    end

    // ------------------------------------------------------------------------
    // Total mass balance
    // ------------------------------------------------------------------------
    dMLdt = zeros(N,1);

    for i = 1:N
        Lin  = (i>1) * L(i-1);
        Vin  = (i>1) * V(i-1);
        Lout = (i<N) * L(i);
        Vout = (i<N) * V(i);

        dMLdt(i) = Lin + Vin + F(i) - Lout - Vout - D(i) - B(i);
    end

    // ------------------------------------------------------------------------
    // Component balances
    // ------------------------------------------------------------------------
    dXdt = zeros(N,NC);

    for i = 1:N
        for k = 1:NC
            Fin_k  = F(i) * col.ZF(k);
            Dout_k = D(i) * X(i,k);
            Bout_k = B(i) * X(i,k);

            dXdt(i,k) = (Fin_k - Dout_k - Bout_k) / max(ML(i),1d-12);
        end
    end

    // ------------------------------------------------------------------------
    // Pack derivatives
    // ------------------------------------------------------------------------
    dydt = zeros(size(y,1),1);

    idx = 1;
    dydt(idx:idx+N-1) = dMLdt;
    idx = idx + N;

    dydt(idx:idx+N*NC-1) = matrix(dXdt, N*NC, 1);

    // ------------------------------------------------------------------------
    // Publish diagnostics (Option A)
    // ------------------------------------------------------------------------
    DD_DIAG = struct( ..
        "ML",        ML, ..
        "dMLdt",     dMLdt*3600, ..        // lbmol/hr
        "L_LBMOLPH", L*3600, ..
        "V_LBMOLPH", V*3600, ..
        "X",         X, ..
        "Y",         Y, ..
        "HL",        HL, ..
        "HV",        HV, ..
        "N_FLASH_CALLS", DD_DIAG.N_FLASH_CALLS ..
    );

endfunction

// ============================================================================
// dd_column_rhs_T.sci
// Dynamic distillation column RHS with strict boundary indexing
//
// Updated: 2026-01-20  (America/New_York)
//
// HARD INVARIANTS:
//   - Distillate (D) applied ONLY at stage 1
//   - Feed (F) applied ONLY at FEED_STAGE
//   - Bottoms (B) applied ONLY at stage N
//
// State layout:
//   y = [ ML(1..N); x(1..N,1..NC) flattened column-major ]
//
// NOTE (IMPORTANT):
//   This RHS currently performs MASS BALANCES ONLY.
//   No VLE / flash / enthalpy calculations are present yet.
//   Diagnostics published here reflect that reality.
// ============================================================================

// ---- Global diagnostics channel (Option A)
global DD_DIAG;
DD_DIAG = struct();

function dydt = column_rhs(t, y, col)

    // ---- Dimensions --------------------------------------------------------
    N  = col.N_STAGES;
    NC = col.N_COMPONENTS;

    // ---- Unpack state ------------------------------------------------------
    idx = 1;
    ML  = y(idx : idx+N-1);        // lbmol
    idx = idx + N;

    x = matrix(y(idx : idx+N*NC-1), N, NC);   // liquid composition

    // ---- Boundary data -----------------------------------------------------
    D = zeros(N,1);
    F = zeros(N,1);
    B = zeros(N,1);

    if size(col.D_LBMOLPH,"*")==N then D = col.D_LBMOLPH(:)/3600.0; end
    if size(col.F_LBMOLPH,"*")==N then F = col.F_LBMOLPH(:)/3600.0; end
    if size(col.B_LBMOLPH,"*")==N then B = col.B_LBMOLPH(:)/3600.0; end

    // ---- Liquid / vapor flows (default zero unless specified) -------------
    L = zeros(N,1);   // lbmol/s
    V = zeros(N,1);   // lbmol/s

    if isfield(col,"L_LBMOLPH") & size(col.L_LBMOLPH,"*")==N then
        L = col.L_LBMOLPH(:)/3600.0;
    end
    if isfield(col,"V_LBMOLPH") & size(col.V_LBMOLPH,"*")==N then
        V = col.V_LBMOLPH(:)/3600.0;
    end

    // ---- Total mass balance -----------------------------------------------
    dMLdt = zeros(N,1);

    for i = 1:N
        Lin  = 0.0;  Lout = 0.0;
        Vin  = 0.0;  Vout = 0.0;

        if i > 1 then
            Lin = L(i-1);
            Vin = V(i-1);
        end
        if i < N then
            Lout = L(i);
            Vout = V(i);
        end

        dMLdt(i) = Lin + Vin + F(i) - Lout - Vout - D(i) - B(i);
    end

    // ---- Component balances -----------------------------------------------
    dxdt = zeros(N,NC);

    for i = 1:N
        for k = 1:NC
            Fin_k  = F(i) * col.ZF(k);
            Dout_k = D(i) * x(i,k);
            Bout_k = B(i) * x(i,k);

            dxdt(i,k) = (Fin_k - Dout_k - Bout_k) / max(ML(i),1d-12);
        end
    end

    // ---- Pack derivative ---------------------------------------------------
    dydt = zeros(size(y,1),1);

    idx = 1;
    dydt(idx:idx+N-1) = dMLdt;
    idx = idx + N;

    dydt(idx:idx+N*NC-1) = matrix(dxdt, N*NC, 1);

    // =======================================================================
    // OPTION A: Publish diagnostics via global DD_DIAG
    // =======================================================================
    global DD_DIAG;

    // Vapor composition NOT computed yet → placeholder zeros
    Y = zeros(N,NC);

    // Enthalpies NOT computed yet → placeholder zeros
    HL = zeros(N,1);
    HV = zeros(N,1);

    DD_DIAG = struct( ..
        "ML",        ML, ..
        "dMLdt",     dMLdt*3600.0, ..     // back to lbmol/hr for logging
        "L_LBMOLPH", L*3600.0, ..
        "V_LBMOLPH", V*3600.0, ..
        "X",         x, ..
        "Y",         Y, ..
        "HL",        HL, ..
        "HV",        HV ..
    );

endfunction
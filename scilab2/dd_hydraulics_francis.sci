// dd_hydraulics_francis.sci
// Francis weir tray hydraulics
//
// Updated: 2026-01-20
//
// Computes:
//   - liquid height on tray
//   - height over weir
//   - liquid flow over weir
//
// Applies ONLY to trays 2..N-1

function hyd = dd_hydraulics_francis(col, ML)

    N = col.N_STAGES;

    // Constants
    Cw = 3.33;   // Francis weir coeff (ft^0.5 / s)

    // Outputs
    h_liq_in = zeros(N,1);
    h_ow_in  = zeros(N,1);
    L_out_lbmolph = zeros(N,1);

    // Liquid density (placeholder)
    // TODO: replace with thermo-based rhoL
    rhoL = 35.0; // lb/ft3 (typical hydrocarbon)

    for s = 2:(N-1)

        // Geometry
        D  = col.TRAY_DIAM_FT(s);
        Lw = col.WEIR_LENGTH_FT(s);
        hw = col.WEIR_HEIGHT_IN(s);
        Af = col.ACTIVE_AREA_FRACTION(s);

        // Active area
        At = %pi * (D/2)^2;
        Aa = Af * At;

        // Liquid volume on tray
        ML_lbmol = ML(s);
        MWmix = col.MW_LIQ(s);   // from case dump (mixture MW)
        VL_ft3 = ML_lbmol * MWmix / rhoL;

        // Liquid height
        h_liq_ft = VL_ft3 / Aa;
        h_liq_in(s) = 12.0 * h_liq_ft;

        // Height over weir
        h_ow_ft = max(0.0, h_liq_ft - hw/12.0);
        h_ow_in(s) = 12.0 * h_ow_ft;

        // Francis weir flow (ft3/s)
        Q_ft3_s = Cw * Lw * h_ow_ft^(3/2);

        // Convert to lbmol/hr
        L_out_lbmolph(s) = Q_ft3_s * rhoL / MWmix * 3600.0;
    end

    hyd = struct();
    hyd.h_liq_in = h_liq_in;
    hyd.h_ow_in  = h_ow_in;
    hyd.L_out_lbmolph = L_out_lbmolph;

endfunction
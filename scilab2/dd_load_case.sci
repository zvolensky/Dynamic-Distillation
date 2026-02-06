// ============================================================================
// dd_load_case.sci
// Load a Dynamic Distillation case from case_dump_out.txt into a Scilab struct
//
// Updated: 2026-01-20  (America/New_York)
//
// Supports REQUIRED keys:
//   N, NC, COMPONENTS_EXCEL
//   P_PSIA (N), T0_F (N), ML0_LBMOL (N)
//   X0ROW (repeat N, each NC)
//   FEED_STAGE, F_LBMOLPH, D_LBMOLPH, B_LBMOLPH, ZF (NC)
//
// Optional keys (geometry / MW):
//   TRAY_DIAM_FT, TRAY_SPACING_FT, GAS_VOID_FRAC, WEIR_HEIGHT_IN,
//   WEIR_LENGTH_FT, ACTIVE_AREA_FRACTION (each N)
//   MW_COMP (NC), MW_LIQ (N)
//
// Output fields include aliases:
//   col.N_STAGES, col.N_COMPONENTS, col.N, col.NC
//   col.P_PSIA, col.T0_F, col.ML0_LBMOL
//   col.P_psia (alias), col.T_F (alias)
//   col.X0 (N x NC), col.Z0 (N x NC), col.ZF (NC)
//   col.FEED_STAGE, col.F_LBMOLPH, col.D_LBMOLPH, col.B_LBMOLPH
//   col.y0 packed state = [ML0; X0(:)] (consistent with column_rhs)
// ============================================================================

function tf = is_absolute_path_(p)
    p = string(p);
    if length(p)==0 then tf=%f; return; end

    // Windows absolute: "C:\..." or "C:/..."
    if length(p) >= 3 then
        c2 = part(p,2);   // ":" check
        c3 = part(p,3);   // "\" or "/"
        if c2==":" & (c3=="\" | c3=="/") then
            tf=%t; return;
        end
    end

    // UNC path: "\\server\share"
    if length(p) >= 2 then
        if part(p,1:2)=="\\" then
            tf=%t; return;
        end
    end

    // Unix absolute: "/..."
    if part(p,1)=="/" then
        tf=%t; return;
    end

    tf=%f;
endfunction

function s = strip_bom_(s)
    s = string(s);
    // Common rendered BOM prefix "ï»¿"
    if length(s) >= 3 then
        if part(s,1:3)=="ï»¿" then
            s = part(s,4:length(s));
        end
    end
endfunction

function v = parse_csv_vector_(csv)
    csv = strip_bom_(string(csv));
    csv = strsubst(csv, " ", "");
    if csv=="" then
        v = [];
        return;
    end
    parts = tokens(csv, ",");
    n = size(parts,"*");
    v = zeros(n,1);
    for i=1:n
        v(i) = evstr(parts(i));
    end
endfunction

function assert_len_(field, vec, expectedN)
    len = size(vec,"*");
    if len <> expectedN then
        error(msprintf("Field %s expected length %d, got %d", field, expectedN, len));
    end
endfunction

function col = dd_load_case(varargin)
    // Usage:
    //   col = dd_load_case()
    //   col = dd_load_case("case_dump_out.txt")

    if argn(2)==0 then
        filename = "case_dump_out.txt";
    elseif argn(2)==1 then
        filename = string(varargin(1));
    else
        error("dd_load_case: expected 0 or 1 input argument(s).");
    end

    if ~is_absolute_path_(filename) then
        filename = fullfile(pwd(), filename);
    end

    if ~isfile(filename) then
        msg = "Case dump file not found: " + filename + ascii(10);
        msg = msg + "pwd() = " + pwd() + ascii(10);
        msg = msg + "Files here:" + ascii(10);
        fl = ls();
        for k=1:size(fl,"r")
            msg = msg + string(fl(k)) + ascii(10);
        end
        error(msg);
    end

    L = mgetl(filename);
    if size(L,"r")==0 then
        error("dd_load_case: case dump file is empty: " + filename);
    end

    // Init
    N=-1; NC=-1; comps_excel="";
    P_PSIA=[]; T0_F=[]; ML0=[];
    X0_rows=[]; Z_rows=[];
    ZF=[];
    FEED_STAGE=[]; F_LBMOLPH=[]; D_LBMOLPH=[]; B_LBMOLPH=[];

    TRAY_DIAM_FT=[]; TRAY_SPACING_FT=[]; GAS_VOID_FRAC=[];
    WEIR_HEIGHT_IN=[]; WEIR_LENGTH_FT=[]; ACTIVE_AREA_FRACTION=[];
    MW_COMP=[]; MW_LIQ=[];

    for i=1:size(L,"r")
        line = strip_bom_(string(L(i)));
        line = stripblanks(line);

        if line=="" then continue; end
        if part(line,1)== "#" then continue; end
        if length(line) >= 2 & part(line,1:2)=="//" then continue; end

        eq = strindex(line, "=");
        if eq==[] then continue; end

        key = stripblanks(part(line,1:eq(1)-1));
        val = stripblanks(part(line,eq(1)+1:length(line)));
        keyU = convstr(key, "u");

        select keyU
        case "N" then
            N = evstr(val);
        case "NC" then
            NC = evstr(val);
        case "COMPONENTS_EXCEL" then
            comps_excel = val;

        case "P_PSIA" then
            P_PSIA = parse_csv_vector_(val);
        case "T0_F" then
            T0_F = parse_csv_vector_(val);
        case "T_F" then
            T0_F = parse_csv_vector_(val); // accept alias
        case "ML0_LBMOL" then
            ML0 = parse_csv_vector_(val);
        case "ML0" then
            ML0 = parse_csv_vector_(val);

        case "X0ROW" then
            rvec = parse_csv_vector_(val);
            X0_rows = [X0_rows; rvec']; // append as row
        case "ZROW" then
            rvec = parse_csv_vector_(val);
            Z_rows = [Z_rows; rvec'];   // append as row

        case "FEED_STAGE" then
            FEED_STAGE = evstr(val);
        case "F_LBMOLPH" then
            F_LBMOLPH = evstr(val);
        case "D_LBMOLPH" then
            D_LBMOLPH = evstr(val);
        case "B_LBMOLPH" then
            B_LBMOLPH = evstr(val);
        case "ZF" then
            ZF = parse_csv_vector_(val);

        // geometry
        case "TRAY_DIAM_FT" then
            TRAY_DIAM_FT = parse_csv_vector_(val);
        case "TRAY_SPACING_FT" then
            TRAY_SPACING_FT = parse_csv_vector_(val);
        case "GAS_VOID_FRAC" then
            GAS_VOID_FRAC = parse_csv_vector_(val);
        case "WEIR_HEIGHT_IN" then
            WEIR_HEIGHT_IN = parse_csv_vector_(val);
        case "WEIR_LENGTH_FT" then
            WEIR_LENGTH_FT = parse_csv_vector_(val);
        case "ACTIVE_AREA_FRACTION" then
            ACTIVE_AREA_FRACTION = parse_csv_vector_(val);

        // MW
        case "MW_COMP" then
            MW_COMP = parse_csv_vector_(val);
        case "MW_LIQ" then
            MW_LIQ = parse_csv_vector_(val);

        else
            // ignore
        end
    end

    // Validate
    if N<=0 then error("dd_load_case: Missing or invalid N in case dump."); end
    if NC<=0 then error("dd_load_case: Missing or invalid NC in case dump."); end
    if comps_excel=="" then error("dd_load_case: Missing COMPONENTS_EXCEL in case dump."); end

    if size(P_PSIA,"*")==0 then error("dd_load_case: Missing P_PSIA vector."); end
    if size(T0_F,"*")==0 then   error("dd_load_case: Missing T0_F vector."); end
    if size(ML0,"*")==0 then    error("dd_load_case: Missing ML0_LBMOL vector."); end

    assert_len_("P_PSIA", P_PSIA, N);
    assert_len_("T0_F",   T0_F,   N);
    assert_len_("ML0_LBMOL", ML0, N);

    if size(X0_rows,"r") <> N then
        error(msprintf("dd_load_case: Expected %d X0ROW rows, got %d", N, size(X0_rows,"r")));
    end
    if size(X0_rows,"c") <> NC then
        error(msprintf("dd_load_case: Expected X0ROW width %d (NC), got %d", NC, size(X0_rows,"c")));
    end

    if size(FEED_STAGE,"*")==0 then error("dd_load_case: Missing FEED_STAGE."); end
    if size(F_LBMOLPH,"*")==0 then  error("dd_load_case: Missing F_LBMOLPH."); end
    if size(D_LBMOLPH,"*")==0 then  error("dd_load_case: Missing D_LBMOLPH."); end
    if size(B_LBMOLPH,"*")==0 then  error("dd_load_case: Missing B_LBMOLPH."); end

    if size(ZF,"*")==0 then
        // fallback: use stage FEED_STAGE composition
        ZF = X0_rows(FEED_STAGE, :)';
    end
    assert_len_("ZF", ZF, NC);

    // Optional geometry checks
    if size(TRAY_DIAM_FT,"*")<>0 then assert_len_("TRAY_DIAM_FT", TRAY_DIAM_FT, N); end
    if size(TRAY_SPACING_FT,"*")<>0 then assert_len_("TRAY_SPACING_FT", TRAY_SPACING_FT, N); end
    if size(GAS_VOID_FRAC,"*")<>0 then assert_len_("GAS_VOID_FRAC", GAS_VOID_FRAC, N); end
    if size(WEIR_HEIGHT_IN,"*")<>0 then assert_len_("WEIR_HEIGHT_IN", WEIR_HEIGHT_IN, N); end
    if size(WEIR_LENGTH_FT,"*")<>0 then assert_len_("WEIR_LENGTH_FT", WEIR_LENGTH_FT, N); end
    if size(ACTIVE_AREA_FRACTION,"*")<>0 then assert_len_("ACTIVE_AREA_FRACTION", ACTIVE_AREA_FRACTION, N); end
    if size(MW_COMP,"*")<>0 then assert_len_("MW_COMP", MW_COMP, NC); end
    if size(MW_LIQ,"*")<>0 then assert_len_("MW_LIQ", MW_LIQ, N); end

    // Build struct
    col = struct();
    col.N_STAGES = N;
    col.N_COMPONENTS = NC;
    col.N = N;
    col.NC = NC;

    col.COMPONENTS_EXCEL = comps_excel;

    col.P_PSIA = P_PSIA;
    col.T0_F   = T0_F;

    // aliases
    col.P_psia = P_PSIA;
    col.T_F    = T0_F;

    col.ML0_LBMOL = ML0;
    col.X0 = X0_rows;

    col.Z0 = X0_rows;
    if size(Z_rows,"r")==N & size(Z_rows,"c")==NC then
        col.Z0 = Z_rows;
    end

    col.FEED_STAGE = FEED_STAGE;
    col.F_LBMOLPH  = F_LBMOLPH;
    col.D_LBMOLPH  = D_LBMOLPH;
    col.B_LBMOLPH  = B_LBMOLPH;
    col.ZF         = ZF;

    // geometry (if present)
    if size(TRAY_DIAM_FT,"*")<>0 then col.TRAY_DIAM_FT = TRAY_DIAM_FT; end
    if size(TRAY_SPACING_FT,"*")<>0 then col.TRAY_SPACING_FT = TRAY_SPACING_FT; end
    if size(GAS_VOID_FRAC,"*")<>0 then col.GAS_VOID_FRAC = GAS_VOID_FRAC; end
    if size(WEIR_HEIGHT_IN,"*")<>0 then col.WEIR_HEIGHT_IN = WEIR_HEIGHT_IN; end
    if size(WEIR_LENGTH_FT,"*")<>0 then col.WEIR_LENGTH_FT = WEIR_LENGTH_FT; end
    if size(ACTIVE_AREA_FRACTION,"*")<>0 then col.ACTIVE_AREA_FRACTION = ACTIVE_AREA_FRACTION; end

    if size(MW_COMP,"*")<>0 then col.MW_COMP = MW_COMP; end
    if size(MW_LIQ,"*")<>0 then col.MW_LIQ  = MW_LIQ; end

    // Pack y0 = [ML; x(:)] consistent with column_rhs()
    ML0_col = ML0(:);
    x0_flat = matrix(X0_rows, N*NC, 1);
    col.y0  = [ML0_col; x0_flat];

endfunction

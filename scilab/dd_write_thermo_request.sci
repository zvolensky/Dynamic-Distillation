// dd_write_thermo_request.sci
// Batched thermo request writer (Option 2)
// Updated: 2026-01-20
//
// thermo_bridge.py expectation (inferred from error):
//   - expects exactly N lines with key "ZROW" (no numbering), stage implied by order
//   - likely same for "X0ROW"
//
// This writer outputs:
//   EXCEL_PATH=...
//   N=...
//   NC=...
//   P_PSIA=... (N values)
//   T_F=...    (N values)
//   ZROW=...   repeated N times (stage 1..N by order)
//   X0ROW=...  repeated N times (stage 1..N by order)

function dd_write_thermo_request(reqFile, col, y, excelPath)

    if argn(2) < 4 then
        error("dd_write_thermo_request: requires (reqFile, col, y, excelPath)");
    end

    reqFile   = string(reqFile);
    excelPath = string(excelPath);

    if excelPath == "" then
        error("dd_write_thermo_request: excelPath is blank (thermo_bridge requires EXCEL_PATH).");
    end

    N  = col.N_STAGES;
    NC = col.N_COMPONENTS;

    // Unpack x from state vector: y = [ML(1..N); x flattened]
    idx = 1 + N;
    x = matrix(y(idx : idx + N*NC - 1), N, NC);

    // T and P vectors
    if isfield(col, "T0_F") then
        T_F = col.T0_F;
    else
        T_F = 100.0 * ones(N,1);
    end

    if isfield(col, "P_PSIA") then
        P_PSIA = col.P_PSIA;
    else
        P_PSIA = 200.0 * ones(N,1);
    end

    // Lines: header(5) + N ZROW + N X0ROW
    lines = emptystr(5 + N + N, 1);
    ii = 1;

    // Header
    lines(ii) = "EXCEL_PATH=" + excelPath; ii = ii + 1;
    lines(ii) = "N="  + string(N);         ii = ii + 1;
    lines(ii) = "NC=" + string(NC);        ii = ii + 1;
    lines(ii) = "P_PSIA=" + dd_csv_line_(P_PSIA); ii = ii + 1;
    lines(ii) = "T_F="    + dd_csv_line_(T_F);    ii = ii + 1;

    // ZROW block: repeated key "ZROW="
    for s = 1:N
        zs = dd_norm_comp_(x(s,:)');
        lines(ii) = "ZROW=" + dd_csv_line_(zs);
        ii = ii + 1;
    end

    // X0ROW block: repeated key "X0ROW="
    for s = 1:N
        xs = dd_norm_comp_(x(s,:)');
        lines(ii) = "X0ROW=" + dd_csv_line_(xs);
        ii = ii + 1;
    end

    mputl(lines, reqFile);

endfunction

function v = dd_norm_comp_(v)
    v = v(:);
    for k=1:size(v,"r")
        if v(k) < 0 then v(k) = 0; end
    end
    ssum = sum(v);
    if ssum <= 0 then
        v = ones(size(v,"r"),1) / size(v,"r");
    else
        v = v / ssum;
    end
endfunction

function out = dd_csv_line_(v)
    v = v(:);
    out = msprintf("%.15g", v(1));
    for k = 2:size(v,"r")
        out = out + "," + msprintf("%.15g", v(k));
    end
endfunction

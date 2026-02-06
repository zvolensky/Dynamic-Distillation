function dd_write_thermo_request(reqFile, col, y, excelPath)
    N = col.N; NC = col.NC;
    // Unpack compositions from state vector y
    idx = N + 1;
    X = matrix(y(idx:idx+N*NC-1), N, NC);
    
    lines = ["EXCEL_PATH=" + excelPath; "N=" + string(N); "NC=" + string(NC)];
    lines = [lines; "P_PSIA=" + strcat(string(col.P_psia), ",")];
    lines = [lines; "T_F=" + strcat(string(col.T_F), ",")];
    
    for i = 1:N
        lines = [lines; "ZROW=" + strcat(string(X(i,:)), ",")];
    end
    mputl(lines, reqFile);
endfunction
function thermo = dd_parse_thermo_response(respFile, N, NC)
    L = mgetl(respFile);
    thermo = struct();
    for i=1:size(L,"r")
        val = part(L(i), strindex(L(i),"=")+1:length(L(i)));
        if strindex(L(i), "HL=") == 1 then thermo.HL = evstr(tokens(val,","))'; end
        if strindex(L(i), "HV=") == 1 then thermo.HV = evstr(tokens(val,","))'; end
    end
endfunction
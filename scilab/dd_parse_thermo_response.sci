// dd_parse_thermo_response.sci
// Parse batched thermo response from thermo_bridge.py
//
// Updated: 2026-01-20
//
// Supported response patterns seen so far:
//   HL=<csv length N>
//   HV=<csv length N>
//   Y_STAGEi=<csv length NC>   (i = 1..N, may appear only for some stages)
//   K_STAGEi=<csv length NC>   (if present later)
//   RHOL=<csv length N> or RHOL_STAGEi=<scalar> (optional)
//   RHOV=<csv length N> or RHOV_STAGEi=<scalar> (optional)
//
// Returns struct thermo with fields if found:
//   thermo.HL : N x 1
//   thermo.HV : N x 1
//   thermo.Y  : N x NC
//   thermo.K  : N x NC
//   thermo.RHOL : N x 1
//   thermo.RHOV : N x 1
// Missing fields are simply absent.

function thermo = dd_parse_thermo_response(respFile, N, NC)

    L = mgetl(respFile);
    thermo = struct();

    HL = [];
    HV = [];
    Y  = [];
    K  = [];
    RHOL = [];
    RHOV = [];

    for i=1:size(L,"r")
        s = stripblanks(L(i));
        if s == "" then continue; end

        eq = strindex(s,"=");
        if eq == [] then continue; end

        key = stripblanks(part(s,1:eq(1)-1));
        val = stripblanks(part(s,eq(1)+1:length(s)));

        // Vector-style keys
        if key == "HL" then
            HL = dd_parse_csv_vec_(val, N);
            continue;
        end
        if key == "HV" then
            HV = dd_parse_csv_vec_(val, N);
            continue;
        end
        if key == "RHOL" then
            RHOL = dd_parse_csv_vec_(val, N);
            continue;
        end
        if key == "RHOV" then
            RHOV = dd_parse_csv_vec_(val, N);
            continue;
        end

        // Per-stage keys like Y_STAGE12 or K_STAGE7
        if strindex(key, "Y_STAGE") <> [] then
            st = evstr(part(key, 8:length(key))); // after 'Y_STAGE'
            if st>=1 & st<=N then
                if Y == [] then Y = %nan * ones(N,NC); end
                vv = dd_parse_csv_vec_(val, NC);
                Y(st,:) = vv';
            end
            continue;
        end

        if strindex(key, "K_STAGE") <> [] then
            st = evstr(part(key, 8:length(key))); // after 'K_STAGE'
            if st>=1 & st<=N then
                if K == [] then K = %nan * ones(N,NC); end
                vv = dd_parse_csv_vec_(val, NC);
                K(st,:) = vv';
            end
            continue;
        end

        // Also allow scalar per-stage forms if they appear later:
        // RHOL_STAGEi=...
        if strindex(key, "RHOL_STAGE") <> [] then
            st = evstr(part(key, 11:length(key)));
            if st>=1 & st<=N then
                if RHOL == [] then RHOL = %nan * ones(N,1); end
                RHOL(st) = evstr(val);
            end
            continue;
        end
        if strindex(key, "RHOV_STAGE") <> [] then
            st = evstr(part(key, 11:length(key)));
            if st>=1 & st<=N then
                if RHOV == [] then RHOV = %nan * ones(N,1); end
                RHOV(st) = evstr(val);
            end
            continue;
        end
    end

    if HL <> [] then thermo.HL = HL; end
    if HV <> [] then thermo.HV = HV; end
    if Y  <> [] then thermo.Y  = Y;  end
    if K  <> [] then thermo.K  = K;  end
    if RHOL <> [] then thermo.RHOL = RHOL; end
    if RHOV <> [] then thermo.RHOV = RHOV; end

endfunction

function v = dd_parse_csv_vec_(s, n_expected)
    t = tokens(s,",");
    n = size(t,"*");
    if n_expected > 0 & n <> n_expected then
        // still parse what we can; pad/truncate
        v = %nan * ones(n_expected,1);
        m = min(n, n_expected);
        for i=1:m
            v(i) = evstr(stripblanks(t(i)));
        end
    else
        v = zeros(n,1);
        for i=1:n
            v(i) = evstr(stripblanks(t(i)));
        end
    end
endfunction
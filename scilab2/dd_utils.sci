// dd_utils.sci
// Shared parsing/utilities for Dynamic_DistillationII Scilab modules
// Generated: 2026-01-19

function vec = dd_parse_csv_floats(s)
    parts = tokens(s, ",");
    n = size(parts, "*");
    vec = zeros(n, 1);
    for i=1:n
        vec(i) = evstr(parts(i));
    end
endfunction

function row = dd_parse_csv_floats_row(s)
    parts = tokens(s, ",");
    n = size(parts, "*");
    row = zeros(1, n);
    for i=1:n
        row(i) = evstr(parts(i));
    end
endfunction

function x = dd_norm_row(x)
    s = sum(x);
    if s <= 0 then
        x = ones(x) / length(x);
    else
        x = x / s;
    end
endfunction
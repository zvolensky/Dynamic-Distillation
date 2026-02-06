// test_s2_rhs.sce
// Minimal RHS validation test (stage-2 / general RHS smoke test)
// Updated: 2026-01-20

exec("dd_regen_case_dump.sci", -1);
exec("dd_load_case.sci", -1);
exec("dd_column_rhs_T.sci", -1);

// Paths
projRoot  = "C:/Users/Thoma/Documents/Python Scripts/Dynamic_DistillationII";
excelPath = projRoot + "/distillation_column_template.xlsx";
pythonExe = projRoot + "/.venv/Scripts/python.exe";
caseDumpPy = projRoot + "/case_dump.py";

// Ensure case dump exists
dd_regen_case_dump(excelPath, "case_dump_out.txt", pythonExe, caseDumpPy);

// Load case
c = dd_load_case("case_dump_out.txt");

// Dimensions
N  = c.N_STAGES;
NC = c.N_COMPONENTS;

// State
y0 = c.y0;

// RHS call
dy0 = column_rhs(0.0, y0, c);

// Basic checks
if size(dy0, "*") <> size(y0, "*") then
    error("RHS size mismatch: size(dy0) != size(y0)");
end

// Boundary sanity check
D_stage = zeros(N,1); F_stage = zeros(N,1); B_stage = zeros(N,1);
D_stage(1)            = c.D_LBMOLPH/3600.0;
F_stage(c.FEED_STAGE) = c.F_LBMOLPH/3600.0;
B_stage(N)            = c.B_LBMOLPH/3600.0;

disp("Boundary indices (D, F, B):");
disp(find(D_stage<>0));
disp(find(F_stage<>0));
disp(find(B_stage<>0));

disp("test_s2_rhs: PASS (RHS executed, sizes OK).");
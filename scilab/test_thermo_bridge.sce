// test_thermo_bridge.sce
// Batched thermo bridge test (Option 2)
//
// Updated: 2026-01-20

exec("dd_call_thermo.sci", -1);
exec("dd_regen_case_dump.sci", -1);
exec("dd_load_case.sci", -1);
exec("dd_write_thermo_request.sci", -1);
exec("dd_parse_thermo_response.sci", -1);

// Paths
projRoot  = "C:/Users/Thoma/Documents/Python Scripts/Dynamic_DistillationII";
excelPath = projRoot + "/distillation_column_template.xlsx";
pythonExe = projRoot + "/.venv/Scripts/python.exe";
caseDumpPy = projRoot + "/case_dump.py";
bridgePy  = projRoot + "/thermo_bridge.py";

// Files in scilab folder
caseDumpFile = "case_dump_out.txt";
reqFile  = "thermo_request.txt";
respFile = "thermo_response.txt";

// Ensure case dump exists + load
dd_regen_case_dump(excelPath, caseDumpFile, pythonExe, caseDumpPy);
col = dd_load_case(caseDumpFile);

// Write batched request from current state (NOTE 4th arg excelPath)
dd_write_thermo_request(reqFile, col, col.y0, excelPath);

// Call thermo once (Option 2)
ok = dd_call_thermo(pythonExe, bridgePy, reqFile, respFile);
disp("dd_call_thermo returned:");
disp(ok);

// Parse response
thermo = dd_parse_thermo_response(respFile, col.N_STAGES, col.N_COMPONENTS);

// Basic validation: must have at least Y or HL
if ~isfield(thermo,"Y") & ~isfield(thermo,"HL") then
    disp("thermo_response.txt (first 60 lines):");
    L = mgetl(respFile);
    disp(L(1:min(60,size(L,"r"))));
    error("Batched thermo response did not contain Y_STAGEi or HL_STAGEi fields.");
end

disp("test_thermo_bridge (batched): PASS");
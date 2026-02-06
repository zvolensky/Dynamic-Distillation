// ============================================================================
// test_load_case_geometry.sce
//
// Unit test for dd_load_case geometry + MW parsing
//
// Updated: 2026-01-20
// ============================================================================

exec("dd_load_case.sci", -1);

disp("Running test_load_case_geometry...");

col = dd_load_case();

N  = col.N_STAGES;
NC = col.N_COMPONENTS;

// Geometry checks
assert_checkequal(size(col.TRAY_DIAM_FT,"*"), N);
assert_checkequal(size(col.WEIR_HEIGHT_IN,"*"), N);
assert_checkequal(size(col.WEIR_LENGTH_FT,"*"), N);
assert_checkequal(size(col.ACTIVE_AREA_FRACTION,"*"), N);

// MW checks
assert_checkequal(size(col.MW_LIQ,"*"), N);

// Stage 1 geometry should be zero (per template)
assert_checkequal(col.TRAY_DIAM_FT(1), 0.0);
assert_checkequal(col.WEIR_LENGTH_FT(1), 0.0);

// Mixture MW sanity
assert_checktrue(col.MW_LIQ(5) > 40);
assert_checktrue(col.MW_LIQ(5) < 60);

disp("test_load_case_geometry: PASS");
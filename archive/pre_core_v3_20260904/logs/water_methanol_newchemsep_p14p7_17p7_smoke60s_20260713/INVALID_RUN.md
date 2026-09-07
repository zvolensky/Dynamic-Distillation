# Invalid Run

This run did not execute with live DWSIM thermodynamics. The process inherited
no `DWSIM_DTL_PATH`, and the backend's former default pointed to a stale
installation path. All startup tray flashes failed and retained cached state;
the resulting top-temperature collapse and steady-state score are invalid.

The valid replacement is:

`logs/water_methanol_newchemsep_p14p7_17p7_dwsim60s_20260713`

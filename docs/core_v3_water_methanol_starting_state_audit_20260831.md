# Core V3 water-methanol starting-state audit

- Result: `usable_starting_state_not_steady`
- Next gate: `ready_for_stationary_jacobian_audit`
- Workbook: `water_methanol_template_10stage_chemsep_excess_enthalpy_p14p7_to_p17p7_geometry_20260713.xlsx`
- Model size: `100 equations and variables`
- DWSIM property package: `unifac`
- Largest scaled mismatch: `1.650701e+00`
- Largest fugacity mismatch: `1.650701e+00`
- Largest pressure mismatch: `9.047876e-01 psia`
- Largest liquid-flow mismatch: `5.923708e+03 lbmol/h`
- Largest energy mismatch: `2.017448e+07 BTU/h`
- Dominant equation: `phase_fugacity[combined_reboiler_sump,Methanol]`
- Nonlinear solve, Jacobian, or timestep: `False`

## Meaning

The workbook is a valid, physically usable starting point for Core V3. All ten vapor spaces remain positive, the stationary equation set has full structural rank, and every live UNIFAC property call completed without a fallback.

It is not yet a steady Core V3 solution. The largest mismatch is the methanol phase-equilibrium equation in the combined reboiler/sump. The prescribed pressure profile and several tray liquid flows also need to move when the stationary equations are solved.

The workbook was left unchanged. This audit stopped before computing a Jacobian, running a nonlinear solve, or advancing time.

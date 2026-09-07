# DD-081 Core V2 Gate C Five-Volume Numerical Audit

- Classification: `dd081_five_volume_numerical_gate_passed`
- Decision: `authorize_one_bounded_dd082_five_volume_steady_solve`
- Runtime: `13.686 s`
- Direct unknowns/residuals: `38 / 38`
- DD-077 ledger unknowns/residuals: `53 / 53`
- Five-volume nonlinear solve attempted: `False`
- Gate C solve authorized: `True`

## Representation Reconciliation

DD-077 retained NL and two independent x coordinates per volume, with three component-reconstruction rows per volume. DD-080 established exact direct reconstruction NL=sum(N) and x=N/NL. DD-081 eliminates those 15 coordinates and their 15 identity rows before numerical differentiation. This is an algebraic substitution of the DD-077 ledger, not a change to the physical equations.

The reflux drum is liquid-only. The other four volumes own equilibrium vapor outlets, so the direct system has eight independent vapor composition coordinates, not ten.

## Source Mapping

| Role | Source stage | T (F) | P (psia) | NL (lbmol) |
|---|---:|---:|---:|---:|
| reflux_drum | 1 | 117.932000 | 218.440000 | 1388.900000 |
| rectifying_tray | 3 | 156.578000 | 222.377000 | 32.514779 |
| feed_tray | 5 | 179.654000 | 226.896000 | 51.062141 |
| stripping_tray | 6 | 196.124000 | 229.478000 | 62.535311 |
| combined_reboiler_sump | 8 | 220.712000 | 232.060000 | 794.000000 |

## Numerical States

| State | Residual inf | Component telescope | Energy telescope | Rank h / h/2 | Worst condition | Pass |
|---|---:|---:|---:|---:|---:|---|
| canonical_mini8_derived | 5.111e-01 | 3.438e-16 | 0.000e+00 | 38 / 38 | 1.181e+06 | True |
| bounded_inventory_perturbation | 5.111e-01 | 3.939e-16 | 0.000e+00 | 38 / 38 | 1.182e+06 | True |
| bounded_energy_perturbation | 5.111e-01 | 3.438e-16 | 0.000e+00 | 38 / 38 | 1.181e+06 | True |
| feed_role_composition_transfer | 5.111e-01 | 3.438e-16 | 0.000e+00 | 38 / 38 | 1.183e+06 | True |
| combined_bounded_perturbation | 5.133e-01 | 3.438e-16 | 0.000e+00 | 38 / 38 | 1.189e+06 | True |

## Francis Diagnostic

| Role | Source profile L | Derived Francis L | Residence time (s) |
|---|---:|---:|---:|
| rectifying_tray | 5258.480000 | 5477.054711 | 21.371560 |
| feed_tray | 12372.200000 | 16109.483026 | 11.410901 |
| stripping_tray | 12584.800000 | 17591.820321 | 12.797261 |

## Hard Stops

- local_closure_pass: `True`
- direct_registry_square: `True`
- direct_structural_rank_full: `True`
- all_numerical_states_pass: `True`
- component_telescoping_all_states: `True`
- energy_telescoping_all_states: `True`
- terminal_draws_use_live_composition: `True`
- francis_is_sole_internal_liquid_flow_owner: `True`
- total_condenser_has_no_inventory: `True`
- fixed_volume_equation_absent: `True`
- serialized_enthalpy_absent: `True`
- pressure_and_vapor_rates_remain_parameters: `True`
- no_clipping_projection_or_property_fallback: `True`
- geometry_unchanged_during_gate: `True`

## Decision

DD-081 passes. DD-082 may make one bounded five-volume steady solve using the frozen equations, scales, tolerances, and three predeclared starts. Pressure dynamics, vapor holdup, energy-owned vapor traffic, controllers, and production tray count remain unauthorized.

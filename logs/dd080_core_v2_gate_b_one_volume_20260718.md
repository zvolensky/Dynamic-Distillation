# DD-080 Gate B One-Volume Property and Energy Closure

- Classification: `dd080_gate_b_passed`
- Decision: `authorize_gate_c_five_volume_prescribed_pressure_model`
- Source role: `feed_tray`
- Source stage: `5`
- Prescribed pressure: `226.896 psia`
- Static gate: `True`
- Dynamic gate: `True`
- Wall time: `289.569 s`

## Static Cases

| Case | T (F) | max residual | Jacobian condition | Height (ft) | Francis L (lbmol/h) | Pass |
|---|---:|---:|---:|---:|---:|---:|
| nominal_canonical | 179.654000 | 1.128e-16 | 2.964e+00 | 0.589899 | 16109.483 | True |
| inventory_plus_1_percent | 179.654000 | 1.128e-16 | 2.937e+00 | 0.595798 | 16425.959 | True |
| internal_energy_plus_0p5_percent | 180.254506 | 5.433e-13 | 2.974e+00 | 0.591128 | 16141.623 | True |
| propane_to_butane_transfer | 179.750060 | 2.331e-14 | 2.962e+00 | 0.589987 | 16111.808 | True |
| combined_bounded | 179.942382 | 1.725e-13 | 2.948e+00 | 0.593383 | 16281.490 | True |

## Dynamic Cases

| Case | Algebraic residual | Component closure | Energy closure | BDF/Radau | Pass |
|---|---:|---:|---:|---:|---:|
| nominal_no_disturbance | 1.128e-16 | 0.000e+00 | 0.000e+00 | 0.000e+00 | True |
| inlet_composition_step | 1.623e-12 | 4.229e-16 | 1.101e-16 | 5.338e-11 | True |
| inlet_enthalpy_step | 8.508e-13 | 1.690e-24 | 6.011e-17 | 3.748e-09 | True |
| bounded_combined | 1.982e-13 | 4.595e-16 | 2.013e-16 | 7.859e-10 | True |

## Interpretation

The conserved state is exactly `N_k, U`. Liquid amount and composition are reconstructed directly. Temperature and the two independent vapor-composition coordinates are solved from one live DWSIM liquid-energy equation and two independent relative-fugacity equations.

The mini8 workbook supplies only the role-selected source state, geometry, components, and pressure. Canonical energy is rebuilt from live DWSIM PR enthalpy and density. Serialized enthalpy, fixed vessel-volume closure, vapor holdup, clipping, projection, phase relaxation, and legacy governing equations are not used.

The reported common fugacity ratio is a saturation-proximity diagnostic. The algebraic equilibrium equations are the two independent relative-fugacity relations for a three-component normalized vapor composition.

## Authorization

Gate B is complete. Gate C may begin as one five-volume prescribed-pressure Francis column. Gates D through G remain unauthorized.

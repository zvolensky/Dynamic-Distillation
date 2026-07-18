# DD-073 Direct Steady-State Continuation

- Classification: `dd073_continuation_stopped`
- Accepted direct root: `False`
- Final completed stage: `0/5`
- Live thermo: `DWSIM PR`
- Wall time: `619.53 s`
- Final scaled infinity norm: `0.700125`

## Stage Results

| Stage | System | Size | Accepted | Final lambda | Accepted points | Last condition |
|---:|---|---:|---:|---:|---:|---:|
| 1 | local_closure | 160 | False | 0.617358 | 22 | 9556.12 |

## Final Physical Residuals

- `liquid_hydraulics`: `0.700125`
- `local_component_closure`: `0.0551381`
- `local_energy_closure`: `0.00712727`
- `local_equilibrium`: `0.282168`
- `local_volume_closure`: `0.0040145`
- `operating_specification`: `0.237736`
- `steady_component_balance`: `0.0412621`
- `steady_energy_balance`: `0.00997541`
- `vapor_pressure_drop`: `0.121801`

Final gate failures:
- local_component_closure=5.514e-02>1.000e-08
- local_energy_closure=7.127e-03>1.000e-07
- local_volume_closure=4.015e-03>1.000e-07
- local_equilibrium=2.822e-01>1.000e-06
- steady_component_balance=4.126e-02>1.000e-08
- steady_energy_balance=9.975e-03>1.000e-07
- liquid_hydraulics=7.001e-01>1.000e-06
- vapor_pressure_drop=1.218e-01>1.000e-06
- operating_specification=2.377e-01>1.000e-06
- pressure profile is not strictly increasing top-to-bottom
- global scaled infinity norm 7.001e-01 exceeds 1.000e-06

## Dominant Residuals

- `liquid_hydraulics[tray_18]`: scaled `0.700125`, raw `5000.97 lbmol_per_h`
- `liquid_hydraulics[tray_19]`: scaled `0.682992`, raw `4878.59 lbmol_per_h`
- `liquid_hydraulics[tray_14]`: scaled `0.496723`, raw `3548.08 lbmol_per_h`
- `liquid_hydraulics[tray_13]`: scaled `0.486554`, raw `3475.44 lbmol_per_h`
- `liquid_hydraulics[tray_12]`: scaled `0.47611`, raw `3400.84 lbmol_per_h`
- `liquid_hydraulics[tray_2]`: scaled `0.453347`, raw `3238.25 lbmol_per_h`
- `liquid_hydraulics[tray_15]`: scaled `0.408757`, raw `2919.74 lbmol_per_h`
- `liquid_hydraulics[tray_9]`: scaled `0.399688`, raw `2854.96 lbmol_per_h`
- `liquid_hydraulics[tray_8]`: scaled `0.399274`, raw `2852 lbmol_per_h`
- `liquid_hydraulics[tray_10]`: scaled `0.396882`, raw `2834.92 lbmol_per_h`
- `liquid_hydraulics[tray_7]`: scaled `0.395871`, raw `2827.69 lbmol_per_h`
- `liquid_hydraulics[tray_3]`: scaled `0.395549`, raw `2825.39 lbmol_per_h`

## Decision

stage 1 local_closure stopped at lambda=0.6173584: solver_success=True; homotopy_inf=6.909e-04; rank=160/160; condition=9.556e+03; condition_growth_pass=False; conservation_pass=True; saturation=0

A failed stage localizes the unresolved equation family. A Stage 5 root is still only a direct steady-state feasibility result; serialization and dynamic testing require later gates.

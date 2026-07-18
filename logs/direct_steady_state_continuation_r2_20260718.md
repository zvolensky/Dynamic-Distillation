# DD-073 Direct Steady-State Continuation

- Classification: `dd073_continuation_stopped`
- Accepted direct root: `False`
- Final completed stage: `0/5`
- Live thermo: `DWSIM PR`
- Wall time: `285.60 s`
- Final scaled infinity norm: `0.706225`

## Stage Results

| Stage | System | Size | Accepted | Final lambda | Accepted points | Last condition |
|---:|---|---:|---:|---:|---:|---:|
| 1 | local_closure | 160 | False | 0.377734 | 7 | 29703.2 |

## Final Physical Residuals

- `liquid_hydraulics`: `0.706225`
- `local_component_closure`: `0.0191176`
- `local_energy_closure`: `0.00202663`
- `local_equilibrium`: `0.306742`
- `local_volume_closure`: `0.000825989`
- `operating_specification`: `0.195872`
- `steady_component_balance`: `0.0164449`
- `steady_energy_balance`: `0.00601262`
- `vapor_pressure_drop`: `0.068089`

Final gate failures:
- local_component_closure=1.912e-02>1.000e-08
- local_energy_closure=2.027e-03>1.000e-07
- local_volume_closure=8.260e-04>1.000e-07
- local_equilibrium=3.067e-01>1.000e-06
- steady_component_balance=1.644e-02>1.000e-08
- steady_energy_balance=6.013e-03>1.000e-07
- liquid_hydraulics=7.062e-01>1.000e-06
- vapor_pressure_drop=6.809e-02>1.000e-06
- operating_specification=1.959e-01>1.000e-06
- pressure profile is not strictly increasing top-to-bottom
- global scaled infinity norm 7.062e-01 exceeds 1.000e-06

## Dominant Residuals

- `liquid_hydraulics[tray_18]`: scaled `0.706225`, raw `5044.55 lbmol_per_h`
- `liquid_hydraulics[tray_19]`: scaled `0.686926`, raw `4906.69 lbmol_per_h`
- `liquid_hydraulics[tray_14]`: scaled `0.497091`, raw `3550.71 lbmol_per_h`
- `liquid_hydraulics[tray_13]`: scaled `0.487269`, raw `3480.55 lbmol_per_h`
- `liquid_hydraulics[tray_12]`: scaled `0.477129`, raw `3408.12 lbmol_per_h`
- `liquid_hydraulics[tray_2]`: scaled `0.45772`, raw `3269.48 lbmol_per_h`
- `liquid_hydraulics[tray_15]`: scaled `0.408791`, raw `2919.99 lbmol_per_h`
- `liquid_hydraulics[tray_9]`: scaled `0.400168`, raw `2858.39 lbmol_per_h`
- `liquid_hydraulics[tray_8]`: scaled `0.399912`, raw `2856.56 lbmol_per_h`
- `liquid_hydraulics[tray_3]`: scaled `0.399513`, raw `2853.71 lbmol_per_h`
- `liquid_hydraulics[tray_10]`: scaled `0.397206`, raw `2837.23 lbmol_per_h`
- `liquid_hydraulics[tray_7]`: scaled `0.396722`, raw `2833.77 lbmol_per_h`

## Decision

stage 1 local_closure stopped at lambda=0.37773438: solver_success=True; homotopy_inf=1.085e-05; rank=160/160; condition=2.970e+04; condition_growth_pass=False; conservation_pass=True; saturation=0

A failed stage localizes the unresolved equation family. A Stage 5 root is still only a direct steady-state feasibility result; serialization and dynamic testing require later gates.

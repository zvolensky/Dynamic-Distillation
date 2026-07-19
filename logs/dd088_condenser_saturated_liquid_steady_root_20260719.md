# DD-088 Saturated-Liquid Steady-Root Result

- Classification: `dd088_saturated_liquid_steady_root_failed`
- Decision: `retire_solved_duty_saturated_liquid_five_volume_architecture`
- Contract commit: `99c9973857fa0df37d8df3452f810feb17209b34`
- Total wall time: `166.000 s`

## Starts

| Start | Initial inf | Final inf | nfev / njev | Worst condition | Min bound distance | Qc MMBTU/h | Pass |
|---|---:|---:|---:|---:|---:|---:|---|
| canonical_saturated_liquid_seed | 3.978625e-01 | 3.885781e-15 | 31 / 30 | 1.162467e+03 | 1.823216e-01 | -52.515728 | False |
| deterministic_dd087_perturbation | 3.891215e-01 | 3.330669e-15 | 41 / 38 | 1.162467e+03 | 1.823216e-01 | -52.515728 | False |
| independent_smooth_phase_stable_seed | 5.538542e-01 | 2.317633e-14 | 48 / 43 | 1.162467e+03 | 1.823216e-01 | -52.515728 | False |

## Root Agreement

- `canonical_saturated_liquid_seed__vs__deterministic_dd087_perturbation`: `7.529936e-11`
- `canonical_saturated_liquid_seed__vs__independent_smooth_phase_stable_seed`: `7.530823e-11`
- `deterministic_dd087_perturbation__vs__independent_smooth_phase_stable_seed`: `8.865770e-15`

## Decision

DD-088 met its frozen hard stop. Retire this solved-duty saturated-liquid five-volume steady architecture; do not tune, widen bounds, sweep duty, add a partial condenser, or integrate.

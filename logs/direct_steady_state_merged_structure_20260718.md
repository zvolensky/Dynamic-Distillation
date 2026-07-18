# DD-074 Merged Continuation Structural Audit

- Classification: `dd074_structural_gate_failed_manual_continuation_retired`
- Structural gate passed: `False`
- Live solve attempted: `False`
- Live solve authorized: `False`

## Stage Structure

| Stage | Name | Size | Physical rank | Nullity | Empty rows | Unused columns | Identity anchors | Pass |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | merged_local_conserved | 240 | 239 | 1 | 0 | 0 | True | False |
| 2 | liquid_hydraulics | 258 | 258 | 0 | 0 | 0 | True | True |
| 3 | vapor_pressure_drop | 277 | 277 | 0 | 0 | 0 | True | True |
| 4 | operating_specifications | 281 | 281 | 0 | 0 | 0 | True | True |

## Merged Block Accounting

- `local_component_closure`: `60`
- `local_energy_closure`: `20`
- `local_equilibrium`: `60`
- `local_volume_closure`: `20`
- `steady_component_balance`: `60`
- `steady_energy_balance`: `20`

The DD-071 registry supplies `60` local equilibrium rows. The merged block is `160` local rows plus `80` steady-balance rows; no equations are added to reach `240`.

## Endpoint And Conservation Checks

- Lambda-zero identity error: `0`
- Merged lambda-one DD-072 identity error: `0`
- Final lambda-one DD-072 identity error: `0`
- Component telescoping: `True`
- Energy telescoping: `True`

## Structural Stop

- Unmatched unknown: `NV[partial_reboiler]`
- Unmatched residual: `component_balance[partial_reboiler,n-Pentane]`

DD-074 fails before a live solve. The merged 240 x 240 physical block has structural rank 239 and nullity 1. Under the predefined hard stop, retire manual staged continuation and pivot architectures.

Per the predefined DD-074 hard stop, no live DWSIM solve was run and manual release-order continuation is retired.

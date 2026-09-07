# DD-085 Energy-Owned Steady-Root Result

- Classification: `dd085_energy_owned_steady_root_failed`
- Decision: `retire_five_volume_energy_owned_steady_architecture`
- Contract commit: `eaa7cc390a384b651afebdbc9cec5462db7d4846`
- Contract SHA-256: `c549bdb9a0f35546c0fee932b865c4b8610b0c6cc1f1d10aa51f7f2714d7b9c7`
- Total wall time: `101.486 s`
- Campaign executions: `1`
- Dynamic integrations: `0`

## Starts

| Start | Initial inf | Final inf | nfev / njev | Worst condition | Min bound distance | Pass |
|---|---:|---:|---:|---:|---:|---|
| canonical role-mapped | `3.978625e-1` | `5.268884e-15` | `27 / 24` | `7.515345e2` | `1.823216e-1` | False |
| deterministic perturbation | `3.891215e-1` | `2.545938e-13` | `31 / 29` | `7.515345e2` | `1.823216e-1` | False |
| independent smooth | `4.857025e-1` | `2.886580e-15` | `40 / 38` | `7.515345e2` | `1.823216e-1` | False |

All starts pass residual, Jacobian, conservation, common-root, property, and
bound gates. All fail only the physical temperature-ordering gate.

## Root Agreement

- canonical / perturbation: `1.371244e-12`
- canonical / smooth: `1.808854e-13`
- perturbation / smooth: `1.552129e-12`

## Physical Stop

```text
T[reflux_drum]     = 166.130673 F
T[rectifying_tray] = 162.897548 F
inversion          =   3.233125 F
```

The liquid drum is hotter than the equilibrium stage supplying vapor to the
inventory-free total condenser while condenser duty removes heat. The common
algebraic root is therefore not accepted as physical.

## Common Root

```text
D = 2818.2023 lbmol/h
B = 4324.7717 lbmol/h
L = [4810.1937, 12025.6087, 12076.0110] lbmol/h
V = [7751.2392, 7700.8369, 7628.3959, 8770.6823] lbmol/h
T = [166.1307, 162.8975, 179.8992, 191.6582, 206.2302] F
NL = [1388.9000, 30.3775, 44.0920, 52.3600, 794.0000] lbmol
```

- Rank: `37/37` at both endpoint steps
- Condition: approximately `751.534`
- Component telescoping: `2.29e-16`
- Energy telescoping: `3.40e-17`
- Active bounds: none
- Property fallback or clipping: none

The adjacent JSON contains the complete per-start block norms, singular
values, compositions, heights, residence times, movements, and property-call
counters.

## Decision

DD-085 met its frozen hard stop. Retire this five-volume energy-owned steady
architecture; do not tune or continue it. Dynamic DAE drafting and
integration remain unauthorized.

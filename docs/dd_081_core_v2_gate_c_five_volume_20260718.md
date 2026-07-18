# DD-081 Core V2 Gate C Five-Volume Numerical Audit

## Purpose

DD-081 assembles the complete five-volume equilibrium-DAE v2 steady residual
with live DWSIM PR properties. It audits equations, conservation, Francis
hydraulics, sparsity, numerical rank, and conditioning before any five-volume
nonlinear solve.

The inventory-bearing volumes are selected by physical role:

1. reflux drum;
2. rectifying tray;
3. feed tray;
4. stripping tray;
5. combined partial reboiler and sump.

The total condenser remains algebraic and inventory-free. Pressure and the two
section vapor rates remain prescribed parameters. Controllers, pressure
dynamics, vapor holdup, energy-determined vapor flow, and production tray count
remain excluded.

## Representation Correction

The external DD-080 review requested direct reconstruction of liquid amount
and composition while also referring to the DD-077 `53 x 53` registry. Those
statements describe two representations of the same equations but cannot both
be the numerical coordinate count.

DD-077 retained, for each volume:

```text
NL
x[1]
x[2]
```

and three component-reconstruction equations. DD-080 established:

```text
NL = sum(N_k)
x_k = N_k / NL
```

DD-081 therefore eliminates 15 algebraic identity coordinates and their 15
reconstruction rows. The live numerical system is `38 x 38`. The reflux drum
is liquid-only, so only the other four volumes have equilibrium-vapor
coordinates: eight independent vapor coordinates, not ten.

This is exact algebraic substitution of the DD-077 ownership ledger. It does
not remove a physical equation or change a control volume.

## Live Equations

The direct residual contains:

| Block | Rows |
|---|---:|
| live liquid-energy reconstruction | 5 |
| live relative-fugacity equilibrium | 8 |
| component balances | 15 |
| energy balances | 5 |
| Francis liquid-flow equations | 3 |
| terminal liquid-amount specifications | 2 |
| **Total** | **38** |

All liquid and vapor enthalpies, liquid internal energies, densities, and
phase fugacity coefficients are evaluated live through the same DWSIM PR
provider. Product component draws use current terminal liquid compositions.

## Numerical Result

The canonical mini8-derived state and four predefined bounded perturbations
all pass:

| State | Scaled residual infinity norm | Rank at `h` / `h/2` | Worst condition |
|---|---:|---:|---:|
| canonical | `0.5111` | `38 / 38` | `1.181e6` |
| inventory | `0.5111` | `38 / 38` | `1.182e6` |
| energy | `0.5111` | `38 / 38` | `1.181e6` |
| composition transfer | `0.5111` | `38 / 38` | `1.183e6` |
| combined | `0.5133` | `38 / 38` | `1.189e6` |

Every state has:

- structural rank `38/38`;
- numerical rank `38/38` at both finite-difference steps;
- no zero row or column;
- no numerical coupling outside the declared dependency graph;
- exact colored/uncolored Jacobian agreement at the reported precision;
- component telescoping below `4.0e-16` relative;
- energy telescoping at reported zero;
- positive inventories, compositions, and flows;
- no clipping, projection, property fallback, or geometry adjustment.

Conditioning is slightly worse than the preferred `1e6` target but remains
well below the fixed `1e8` hard stop.

The canonical seed is not a steady solution. Its largest scaled residual is
the combined-bottom energy balance, `-0.5111`, followed by the feed energy
balance and terminal component balances. DD-081 tests readiness to solve, not
existence of a root.

## Francis Diagnostic

| Role | Source liquid flow (lbmol/h) | Live Francis flow (lbmol/h) | Residence time (s) |
|---|---:|---:|---:|
| rectifying tray | `5258.48` | `5477.05` | `21.37` |
| feed tray | `12372.20` | `16109.48` | `11.41` |
| stripping tray | `12584.80` | `17591.82` | `12.80` |

The source profile does not force the residual. These differences remain
visible diagnostics. No geometry or hydraulic coefficient was changed in
DD-081.

## Evidence

- `src/dynamic_distillation/core_v2/five_volume_residual_gate_v1.py`
- `tools/audit_core_v2_gate_c_five_volume.py`
- `tests/test_core_v2_five_volume_residual_gate_v1.py`
- `logs/dd081_core_v2_gate_c_five_volume_20260718.json`
- `logs/dd081_core_v2_gate_c_five_volume_20260718.md`

## Decision

DD-081 passes the pre-solve Gate C audit.

DD-082 is authorized for one bounded five-volume steady solve using frozen
equations, scales, tolerances, and predefined starts. No solver or physics
tuning is authorized after seeing the result. Failure to obtain the declared
common physical root stops Gate C.


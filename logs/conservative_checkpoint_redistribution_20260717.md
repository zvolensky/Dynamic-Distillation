# Conservative Checkpoint Redistribution Probe

- Classification: `energy_only_pressure_ordering_feasible`
- Limited feasibility pass: `True`
- Checkpoint: `20260717_111627` at `2400 s`
- Thermo: `dwsim`

## Scope

This first feasibility layer keeps every node component inventory and fixed volume unchanged. It imposes ordered pressure and redistributes only internal energy under exact whole-column energy conservation. Hydraulic equations are not included, so a pass is not production-model acceptance.

## Conservation And Movement

| Metric | Value |
|---|---:|
| Component conservation max error, lbmol | 0 |
| Total energy error, BTU | -0.0295369 |
| Total energy relative error | 1.84159e-09 |
| Energy moved, BTU | 747127 |
| Energy L1 change, BTU | 1.49425e+06 |
| Energy L1 fraction of inventory | 0.0931647 |
| Maximum node energy change, BTU | 536480 |
| Maximum node specific-energy change, BTU/lbmol | 1854.49 |
| Maximum pressure change, psi | 93.6566 |
| Pressure RMS change, psi | 49.2983 |
| Maximum temperature change, F | 32.5132 |
| Temperature RMS change, F | 18.2833 |

## Pressure Result

- Uniform pressure shift: `-2.91416 psi`
- Required minimum increment: `0.01 psi/node`
- Ordered profile pass: `True`
- Energy root converged: `True`
- Profile evaluations: `14`

| Node | P initial, psia | P final, psia | T final, F | Vapor fraction | Delta U, BTU | Volume rel. residual | Beta residual |
|---|---:|---:|---:|---:|---:|---:|---:|
| top_terminal | 213.564 | 210.65 | 113.731 | 0.0627312 | -58754.5 | 8.84917e-12 | 5.21268e-11 |
| tray_2 | 321.89 | 228.234 | 130.224 | 0.467022 | -159248 | 9.8364e-14 | 4.44811e-13 |
| tray_3 | 320.55 | 228.244 | 140.424 | 0.202656 | -79970.8 | 1.31799e-13 | 3.76565e-12 |
| tray_4 | 309.723 | 228.254 | 150.068 | 0.196791 | -73927.5 | 2.44555e-13 | 8.62588e-12 |
| tray_5 | 299.929 | 228.264 | 158.209 | 0.193511 | -67241.6 | 1.09331e-15 | 6.20892e-14 |
| tray_6 | 291.521 | 228.274 | 164.209 | 0.192909 | -60581.2 | 3.33545e-08 | 3.57168e-10 |
| tray_7 | 285.472 | 228.284 | 168.421 | 0.192523 | -55535.4 | 8.25251e-13 | 7.05533e-12 |
| tray_8 | 281.263 | 228.294 | 171.481 | 0.191962 | -51967.4 | 2.08613e-13 | 9.92872e-13 |
| tray_9 | 277.739 | 228.304 | 174.057 | 0.191236 | -48940.8 | 1.83176e-12 | 3.35632e-12 |
| tray_10 | 274.236 | 228.314 | 176.717 | 0.189863 | -45939.4 | 1.04318e-12 | 4.29803e-12 |
| tray_11 | 270.119 | 228.324 | 179.809 | 0.187335 | -42386.5 | 2.27848e-13 | 1.37967e-12 |
| tray_12 | 230.295 | 228.334 | 182.166 | 0.149441 | -2634.31 | 5.22781e-13 | 7.59434e-12 |
| tray_13 | 223.381 | 228.344 | 185.395 | 0.151524 | 6711.17 | 2.30336e-12 | 1.43088e-12 |
| tray_14 | 217.871 | 228.354 | 189.152 | 0.152804 | 14302.6 | 3.23415e-13 | 3.91631e-14 |
| tray_15 | 212.128 | 228.364 | 193.273 | 0.156884 | 22425.6 | 5.71108e-09 | 3.34945e-10 |
| tray_16 | 210.402 | 228.374 | 197.706 | 0.155028 | 29368.3 | 2.65471e-13 | 1.70552e-12 |
| tray_17 | 202.467 | 228.384 | 202.687 | 0.161709 | 42587.6 | 7.75765e-13 | 1.20293e-12 |
| tray_18 | 208.628 | 228.394 | 207.072 | 0.122059 | 44556.9 | 7.59834e-13 | 1.25944e-12 |
| tray_19 | 205.161 | 228.404 | 210.574 | 0.116176 | 50695.1 | 8.58635e-14 | 1.82139e-12 |
| bottom_terminal | 199.616 | 228.414 | 218.084 | 0.10807 | 536480 | 3.04071e-13 | 7.30528e-12 |

## Decision

Energy redistribution alone can recover an ordered local UV pressure profile while preserving all component totals and whole-column energy. Assess the movement magnitude, then extend the sandbox to simultaneous component redistribution and an uncapped hydraulic residual.

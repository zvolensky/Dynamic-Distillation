# DD-069 Terminal Energy, Volume, and Basis Audit

- Classification: `dd069_terminal_basis_or_volume_defect_found`
- Checkpoint: `20260717_111627` at `2400 s`
- Thermo: `dwsim`
- Decision: Checkpoint repair remains paused. Correct the concrete terminal energy/volume mapping defects and the DD-068 scaling bias, then repeat DD-067/DD-068 before any hydraulic work. Failed checks: one or more terminal energy/volume basis checks fail; one or more representative interior controls fail; DD-068 local energy scaling is not neutral.

## Falsification Tests

| Test | Pass | Evidence |
|---|---:|---|
| A: H/U/PV round trip | True | max relative error `0` |
| B: fixed-volume reconstruction | False | max relative error `0.51472` |
| C: phase aggregation and mapped-U basis | False | max phase error `1.43284e-16`; max mapped-U error `0` |
| D: empty condenser placeholder invariance | True | raw H `0 BTU`; mapped V `0 ft3` |
| E: normalized-energy scaling neutrality | False | max/min cost ratio `4134.77` |

## Energy And Volume Reconstruction

| Region | Category | Stored H, BTU | Reconstructed H, BTU | Fixed PV, BTU | Mapped U, BTU | Reconstructed phase U, BTU | Fixed V, ft3 | Phase V, ft3 | V rel error | H rel error |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reflux_drum | terminal_equipment | N/A | -8.41303e+06 | 178778 | -8.5915e+06 | -8.5915e+06 | 4330.14 | 4322.76 | 0.00170395 | N/A |
| reboiler_stage | terminal_equipment | 33304.7 | 33084.5 | 12541.7 | 20763.1 | 20712.5 | 291.9 | 287.95 | 0.013532 | 0.00661414 |
| bottoms_sump | terminal_equipment | N/A | -3.185e+06 | 133778 | -3.24992e+06 | -3.24992e+06 | 3113.6 | 1510.97 | 0.51472 | N/A |
| tray_2 | interior_control | -95756 | -319109 | 37855.4 | -133611 | -350512 | 908.74 | 753.86 | 0.170434 | 2.33252 |
| tray_12 | interior_control | -274110 | -321862 | 15001.1 | -289112 | -331134 | 354.155 | 218.9 | 0.381911 | 0.174207 |
| tray_19 | interior_control | -354577 | -329397 | 16759.3 | -371337 | -341370 | 390.064 | 278.658 | 0.285608 | 0.0710138 |

## Energy Scaling

A `1000 BTU` move is priced with the DD-068 normalized L2 scale.

| Node | Category | Inventory, lbmol | Energy scale, BTU | Normalized cost | Cost / median interior |
|---|---|---:|---:|---:|---:|
| top_terminal | terminal | 1516.27 | 8.5915e+06 | 1.35476e-08 | 0.000417517 |
| tray_2 | interior | 85.8713 | 133611 | 5.60161e-05 | 1.72634 |
| tray_12 | interior | 70.1399 | 289112 | 1.19638e-05 | 0.368707 |
| tray_19 | interior | 91.0843 | 371337 | 7.25212e-06 | 0.2235 |
| bottom_terminal | terminal | 804.613 | 3.22916e+06 | 9.59004e-08 | 0.00295551 |

## Basis Contract

- PV conversion: `0.185049714738 BTU/(psia ft3)`.
- Pressure is absolute psia; volume is ft3; enthalpy and internal energy are BTU.
- All property reconstructions use the same runtime provider and component ordering.
- Interior and terminal-stage stored H comes from checkpoint EL+EV.
- Drum and sump boundary H/U is property-reconstructed because the checkpoint layout has no boundary energy state.

## Decision

Checkpoint repair remains paused. Correct the concrete terminal energy/volume mapping defects and the DD-068 scaling bias, then repeat DD-067/DD-068 before any hydraulic work. Failed checks: one or more terminal energy/volume basis checks fail; one or more representative interior controls fail; DD-068 local energy scaling is not neutral.

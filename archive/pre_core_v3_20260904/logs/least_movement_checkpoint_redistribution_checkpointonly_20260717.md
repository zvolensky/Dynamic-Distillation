# DD-068 Least-Movement N+U Redistribution

- Classification: `dd068_stop_before_hydraulics`
- Hydraulics decision: `stop_before_hydraulics`
- Thermo: `dwsim`
- Checkpoint: `20260717_111627` at `2400 s`
- Primary objective: `normalized_L2_component_plus_energy`

## Multi-Start Evidence

| Start | Converged | Objective | Energy moved, BTU | Material moved, lbmol | Max dP, psi | Terminal energy fraction |
|---|---:|---:|---:|---:|---:|---:|
| checkpoint | True | 0.496284 | 1.01286e+06 | 68.8647 | 79.1585 | 0.803167 |

- Successful starts: `1` / `1`
- Objective relative spread: `0.0`
- Required spread: `<0.0001`
- Reproducible minimum pass: `False`
- Best start: `checkpoint`

## Best Result

| Metric | Value |
|---|---:|
| Normalized L2 objective | 0.496284 |
| Component objective | 0.262992 |
| Energy objective | 0.233292 |
| Material moved, half L1, lbmol | 68.8647 |
| Energy moved, half L1, BTU | 1.01286e+06 |
| DD-067 energy-movement ratio | 1.35567 |
| Maximum pressure change, psi | 79.1585 |
| DD-067 max-pressure-change ratio | 0.845199 |
| Terminal component correction fraction | 0.314581 |
| Terminal energy correction fraction | 0.803167 |
| First-order optimality norm | 1.49683e-12 |
| Constraint violation norm | 1.82962e-07 |
| UV solves | 1220 |
| Active bounds | 0 |

## Best Node Profile

| Node | T, F | P, psia | Vapor fraction | Delta U, BTU |
|---|---:|---:|---:|---:|
| top_terminal | 102.124 | 182.566 | 0.0523331 | -858628 |
| tray_2 | 141.963 | 242.732 | 0.670004 | -10585.4 |
| tray_3 | 148.94 | 242.742 | 0.263361 | -21055.4 |
| tray_4 | 158.019 | 242.752 | 0.250181 | -20691.7 |
| tray_5 | 165.368 | 242.762 | 0.241856 | -19184 |
| tray_6 | 170.768 | 242.772 | 0.237365 | -17143 |
| tray_7 | 174.64 | 242.782 | 0.234016 | -15431 |
| tray_8 | 177.534 | 242.792 | 0.231192 | -14168.7 |
| tray_9 | 180.04 | 242.802 | 0.228324 | -13101 |
| tray_10 | 182.69 | 242.812 | 0.224526 | -12053.7 |
| tray_11 | 185.816 | 242.822 | 0.218807 | -10815.5 |
| tray_12 | 187.733 | 242.832 | 0.155825 | 10593.9 |
| tray_13 | 191.057 | 242.842 | 0.155065 | 16305.7 |
| tray_14 | 194.803 | 242.852 | 0.153944 | 20782.4 |
| tray_15 | 199.026 | 242.862 | 0.154975 | 25591.6 |
| tray_16 | 203.544 | 242.872 | 0.150991 | 31711 |
| tray_17 | 208.92 | 242.882 | 0.170269 | 46149.9 |
| tray_18 | 213.009 | 242.892 | 0.117177 | 44764.3 |
| tray_19 | 216.435 | 242.902 | 0.109705 | 48598.9 |
| bottom_terminal | 223.842 | 242.912 | 0.115768 | 768360 |

## Decision

Do not add hydraulics yet. The least-movement result is unresolved, not reproducible across starts, insufficiently improved from DD-067, or terminal-dominated. Audit the reported movement structure, energy allocation, volumes, and terminal mapping first.

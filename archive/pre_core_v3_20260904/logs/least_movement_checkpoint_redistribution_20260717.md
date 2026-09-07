# DD-068 Least-Movement N+U Redistribution

- Classification: `dd068_stop_before_hydraulics`
- Hydraulics decision: `stop_before_hydraulics`
- Thermo: `dwsim`
- Checkpoint: `20260717_111627` at `2400 s`
- Primary objective: `normalized_L2_component_plus_energy`

## Multi-Start Evidence

| Start | Converged | Objective | Energy moved, BTU | Material moved, lbmol | Max dP, psi | Terminal energy fraction |
|---|---:|---:|---:|---:|---:|---:|
| checkpoint | True | 0.496284 | 1.01285e+06 | 68.8648 | 79.1587 | 0.803167 |
| dd067 | False | 2.58149 | 747127 | 0 | 93.6566 | 0.398349 |
| linear | False | 1.22902 | 914010 | 33.3733 | 91.6086 | 0.624877 |
| random-small | False | 0.723719 | 690225 | 97.3084 | 108.181 | 0.772049 |
| random-moderate | True | 0.496284 | 1.01286e+06 | 68.8648 | 79.1584 | 0.803168 |

- Successful starts: `2` / `5`
- Objective relative spread: `2.569008727970612e-09`
- Required spread: `<0.0001`
- Reproducible minimum pass: `True`
- Best start: `checkpoint`

## Best Result

| Metric | Value |
|---|---:|
| Normalized L2 objective | 0.496284 |
| Component objective | 0.262994 |
| Energy objective | 0.23329 |
| Material moved, half L1, lbmol | 68.8648 |
| Energy moved, half L1, BTU | 1.01285e+06 |
| DD-067 energy-movement ratio | 1.35566 |
| Maximum pressure change, psi | 79.1587 |
| DD-067 max-pressure-change ratio | 0.845202 |
| Terminal component correction fraction | 0.31458 |
| Terminal energy correction fraction | 0.803167 |
| First-order optimality norm | 1.42245e-12 |
| Constraint violation norm | 9.09648e-07 |
| UV solves | 1620 |
| Active bounds | 0 |

## Best Node Profile

| Node | T, F | P, psia | Vapor fraction | Delta U, BTU |
|---|---:|---:|---:|---:|
| top_terminal | 102.124 | 182.566 | 0.0523332 | -858620 |
| tray_2 | 141.962 | 242.732 | 0.670004 | -10585.4 |
| tray_3 | 148.94 | 242.742 | 0.26336 | -21055.4 |
| tray_4 | 158.018 | 242.752 | 0.250181 | -20691.7 |
| tray_5 | 165.368 | 242.762 | 0.241856 | -19184.1 |
| tray_6 | 170.768 | 242.772 | 0.237365 | -17143 |
| tray_7 | 174.64 | 242.782 | 0.234015 | -15431.1 |
| tray_8 | 177.533 | 242.792 | 0.231192 | -14168.7 |
| tray_9 | 180.04 | 242.802 | 0.228324 | -13101.1 |
| tray_10 | 182.69 | 242.812 | 0.224526 | -12053.8 |
| tray_11 | 185.816 | 242.822 | 0.218807 | -10815.6 |
| tray_12 | 187.733 | 242.832 | 0.155825 | 10593.7 |
| tray_13 | 191.057 | 242.842 | 0.155065 | 16305.4 |
| tray_14 | 194.803 | 242.852 | 0.153944 | 20782.1 |
| tray_15 | 199.026 | 242.862 | 0.154975 | 25591.4 |
| tray_16 | 203.544 | 242.872 | 0.15099 | 31710.5 |
| tray_17 | 208.92 | 242.882 | 0.170269 | 46149.5 |
| tray_18 | 213.009 | 242.892 | 0.117177 | 44763.9 |
| tray_19 | 216.435 | 242.902 | 0.109706 | 48599 |
| bottom_terminal | 223.841 | 242.912 | 0.115768 | 768354 |

## Decision

Do not add hydraulics. Failed gates: only 2 of 5 starts converged; energy movement is 1.356 times DD-067; maximum pressure correction is 0.845 times DD-067; terminal assemblies absorb 80.3% of absolute energy movement. Audit checkpoint energy allocation, stage and terminal volumes, vapor-space treatment, and terminal mapping before increasing model complexity.

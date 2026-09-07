# DD-070 Canonical Checkpoint Repair

- Classification: `dd070_checkpoint_repair_retired`
- Decision: `retire_checkpoint_repair`
- Thermo: `dwsim`
- Sump topology: `liquid_only_sump_occupied_volume`
- Scale mode: `column-common`

## Canonical Mapping

- Stored whole-column U: `-16038840.9 BTU`
- Canonical whole-column U: `-17246038.2 BTU`
- Mapping replacement: `-1207197.26 BTU`
- Enthalpy offset classification: `state_dependent_checkpoint_enthalpy_mismatch`

| Node | Topology | Stored U, BTU | Canonical U, BTU | Mapping delta U, BTU | Prior V mismatch | Canonical target V mismatch |
|---|---|---:|---:|---:|---:|---:|
| top_terminal | explicit_reflux_drum_vapor_owner | -8.5915e+06 | -8.5915e+06 | 0 | 0.00170395 | 0.00170395 |
| tray_2 | fixed_stage_shell_volume | -133611 | -350512 | -216901 | 0.170434 | 0.170434 |
| tray_3 | fixed_stage_shell_volume | -175381 | -303958 | -128578 | 0.47329 | 0.47329 |
| tray_4 | fixed_stage_shell_volume | -175724 | -294717 | -118993 | 0.461589 | 0.461589 |
| tray_5 | fixed_stage_shell_volume | -174650 | -283345 | -108695 | 0.44844 | 0.44844 |
| tray_6 | fixed_stage_shell_volume | -173158 | -272828 | -99669.1 | 0.443429 | 0.443429 |
| tray_7 | fixed_stage_shell_volume | -172212 | -265554 | -93342.3 | 0.441381 | 0.441381 |
| tray_8 | fixed_stage_shell_volume | -171663 | -260911 | -89248.3 | 0.439599 | 0.439599 |
| tray_9 | fixed_stage_shell_volume | -171461 | -258097 | -86636.6 | 0.439755 | 0.439755 |
| tray_10 | fixed_stage_shell_volume | -171732 | -256731 | -84998.9 | 0.441391 | 0.441391 |
| tray_11 | fixed_stage_shell_volume | -172962 | -256452 | -83490.1 | 0.446973 | 0.446973 |
| tray_12 | fixed_stage_shell_volume | -289112 | -331134 | -42022.9 | 0.381911 | 0.381911 |
| tray_13 | fixed_stage_shell_volume | -288251 | -323340 | -35089.4 | 0.406107 | 0.406107 |
| tray_14 | fixed_stage_shell_volume | -285786 | -313607 | -27821.1 | 0.40881 | 0.40881 |
| tray_15 | fixed_stage_shell_volume | -281894 | -301168 | -19273.3 | 0.405735 | 0.405735 |
| tray_16 | fixed_stage_shell_volume | -324183 | -337382 | -13198.8 | 0.355899 | 0.355899 |
| tray_17 | fixed_stage_shell_volume | -317139 | -318118 | -978.852 | 0.362612 | 0.362612 |
| tray_18 | fixed_stage_shell_volume | -367923 | -356100 | 11822.9 | 0.318127 | 0.318127 |
| tray_19 | fixed_stage_shell_volume | -371337 | -341370 | 29966.5 | 0.285608 | 0.285608 |
| bottom_terminal | explicit_reboiler_plus_liquid_only_sump | -3.22916e+06 | -3.22921e+06 | -50.5681 | 0.51472 | 0.00219095 |

## Multi-Start Result

| Start | Converged | Objective | Energy moved, BTU | Material moved, lbmol | Max dP, psi | Terminal energy fraction |
|---|---:|---:|---:|---:|---:|---:|
| checkpoint | False | 5.27355e-05 | 134207 | 16.1191 | 25.3368 | 0.410324 |
| dd067 | False | 5.27543e-05 | 134176 | 16.1229 | 25.3342 | 0.410456 |
| linear | True | 6.38279e-05 | 159739 | 13.6396 | 23.3349 | 0.434815 |
| random-small | False | 5.27636e-05 | 133994 | 16.1979 | 25.3339 | 0.410695 |
| random-moderate | False | 5.27652e-05 | 134102 | 16.1424 | 25.3385 | 0.410541 |

- Successful starts: `1` / `5`
- Objective relative spread: `0.0`
- Maximum normalized pattern difference: `None`
- Reproducible basin pass: `False`

## Best Candidate

- Energy moved: `159738.658 BTU`
- Material moved: `13.6396092 lbmol`
- Maximum pressure correction: `23.3349305 psi`
- Terminal energy movement fraction: `0.434815`
- Terminal energy-capacity fraction: `0.685416`
- Terminal concentration ratio: `0.634381`

| Node | T, F | P, psia | Vapor fraction | Delta U, BTU |
|---|---:|---:|---:|---:|
| top_terminal | 111.778 | 205.851 | 0.0621107 | -103489 |
| tray_2 | 121.68 | 205.988 | 0.408908 | 10527.2 |
| tray_3 | 131.793 | 206.141 | 0.173843 | 17647 |
| tray_4 | 140.929 | 206.29 | 0.170279 | 14937 |
| tray_5 | 148.768 | 206.438 | 0.168696 | 12262.1 |
| tray_6 | 154.615 | 206.587 | 0.168967 | 10551.2 |
| tray_7 | 158.754 | 206.736 | 0.169116 | 9632.13 |
| tray_8 | 161.772 | 206.885 | 0.16892 | 9244.05 |
| tray_9 | 164.286 | 207.035 | 0.168354 | 9455.22 |
| tray_10 | 167.085 | 207.302 | 0.167657 | 11290.4 |
| tray_11 | 169.81 | 207.312 | 0.164661 | 11476.2 |
| tray_12 | 172.559 | 207.48 | 0.133723 | 6624.43 |
| tray_13 | 175.653 | 207.632 | 0.135235 | 8120.33 |
| tray_14 | 179.36 | 207.783 | 0.13642 | 8278.15 |
| tray_15 | 183.468 | 207.934 | 0.14023 | 7930.9 |
| tray_16 | 188.243 | 208.082 | 0.139744 | 5523.17 |
| tray_17 | 193.141 | 208.238 | 0.145922 | 6239.2 |
| tray_18 | 198.706 | 208.384 | 0.100224 | -7090.24 |
| tray_19 | 203.049 | 208.849 | 0.0975963 | -13734.8 |
| bottom_terminal | 213.152 | 218.271 | 0.0150966 | -35425 |

## Acceptance Gate

| Criterion | Pass |
|---|---:|
| at_least_4_of_5_starts_converged | False |
| objective_basin_reproduced | False |
| movement_pattern_reproduced | False |
| component_energy_local_uv_and_bounds | True |
| candidate_volume_mismatch_below_1pct | True |
| canonical_live_dwsim_energy_basis | True |
| enthalpy_reconciliation_not_state_dependent | False |
| energy_movement_below_dd067 | True |
| maximum_pressure_correction_below_50psi | True |
| terminal_scaling_neutral | True |
| terminal_movement_to_capacity_ratio_below_2 | True |

## Final Decision

Retire checkpoint repair. The one permitted corrected attempt failed: at_least_4_of_5_starts_converged; objective_basin_reproduced; movement_pattern_reproduced; enthalpy_reconciliation_not_state_dependent. Formulate the direct conserved steady-state solve from operating specifications. Do not retune this optimizer or add hydraulics to the rejected state.

# DD-146 Longer Post-Cache-Fix Captured-Trajectory Result

- Classification: `longer_post_cachefix_captured_trajectory_passed`
- Decision: `authorize_separately_frozen_trajectory_efficiency_design`
- Completed coarse/refined steps: `60` / `120`
- Worst residual: `1.087532713e-10`
- Endpoint refinement: `{'inventory': 2.2577532171038805e-07, 'energy': 2.2360300516947203e-07, 'memory': 3.5917736764326524e-06, 'coordinates': 2.6489588645511875e-06, 'product': 2.6382323540217593e-06, 'level': 1.1785185094481676e-07}`
- Capture gates: `{'capture_count_matches_completed_steps': True, 'all_capture_arrays_read_only': True, 'residual_identity': True, 'one_frozen_jacobian_per_step': True}`
- DWSIM calls: `221845`
- Wall clock: `116.259 s`

The sole scientific change from DD-145 is the 60-second duration. Complete captured evidence is retained for every attempted step.

## Outcome

The coarse path completes `60/60` roots and the refined path completes `120/120`. No line-search or bound step is rejected. The worst coarse/refined Jacobian conditions are `2.084543e5` and `7.287030e5`, both below the frozen `1e8` limit.

At `t=60 s`, coarse and refined endpoints agree within:

- inventory: `2.2578e-7` relative;
- energy: `2.2360e-7` relative;
- controller memory: `3.5918e-6` absolute;
- coordinates: `2.6490e-6` relative;
- product rates: `2.6382e-6` relative;
- levels: `1.1785e-7` absolute.

The coarse endpoint is level `[0.4692922216, 0.5251799416]` with distillate/bottoms rates `2254.9523891 / 4867.4495454 lbmol/h`. The refined endpoint is level `[0.4692922176, 0.5251800594]` with rates `2254.9523745 / 4867.4366517 lbmol/h`. Both level errors shrink from the moved-setpoint initial errors, controller memories and products move in the commanded direction, pressure remains ordered, and every physical, conservation, provider, call, wall, and capture gate passes.

## Decision

Core V3's repaired controlled DAE is numerically coherent through 60 seconds on both grids. The fully captured brute-force extension path is now complete: this proof required `221,845` DWSIM calls and produced a `62.6 MiB` artifact. Before multi-minute operation, the next authorized work is a separately frozen trajectory-efficiency design that reduces repeated finite-difference Jacobian cost without changing the accepted equations or silently weakening scientific gates.

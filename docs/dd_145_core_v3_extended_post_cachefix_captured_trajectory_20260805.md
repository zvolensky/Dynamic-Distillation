# DD-145 Extended Post-Cache-Fix Captured-Trajectory Result

- Classification: `extended_post_cachefix_captured_trajectory_passed`
- Decision: `authorize_separately_frozen_longer_captured_trajectory_contract`
- Completed coarse/refined steps: `20` / `40`
- Worst residual: `1.087532713e-10`
- Endpoint refinement: `{'inventory': 7.21467615592131e-08, 'energy': 1.251490057039405e-08, 'memory': 1.2555682594728168e-06, 'coordinates': 1.2439084048077031e-06, 'product': 1.238636625234203e-06, 'level': 1.5070000247696669e-09}`
- Capture gates: `{'capture_count_matches_completed_steps': True, 'all_capture_arrays_read_only': True, 'residual_identity': True, 'one_frozen_jacobian_per_step': True}`
- DWSIM calls: `74005`
- Wall clock: `42.222 s`

The sole scientific change from DD-144 is the 20-second duration. Complete captured evidence is retained for every attempted step.

## Outcome

The coarse path completes `20/20` roots and the refined path completes `40/40`. No line-search fraction is rejected. The worst coarse/refined Jacobian conditions are `2.084358e5` and `7.286608e5`, both below the frozen `1e8` limit.

At `t=20 s`, coarse and refined endpoints agree within:

- inventory: `7.2147e-8` relative;
- energy: `1.2515e-8` relative;
- controller memory: `1.2556e-6` absolute;
- coordinates: `1.2439e-6` relative;
- product rates: `1.2386e-6` relative;
- levels: `1.5070e-9` absolute.

The coarse endpoint is level `[0.4692895711, 0.5250317185]` with distillate/bottoms rates `2255.1248513 / 4866.5236786 lbmol/h`. The refined endpoint is level `[0.4692895696, 0.5250317200]` with rates `2255.1248467 / 4866.5176251 lbmol/h`. Both level errors shrink from the moved-setpoint initial errors, controller memories and products move in the commanded direction, pressure remains ordered, and every physical, conservation, provider, call, wall, and capture gate passes.

## Decision

The repaired Core V3 controlled DAE remains numerically coherent through 20 seconds on both grids. A separately frozen longer captured trajectory is authorized. Complete capture consumed `74,005` of the `<80,000` call allowance, so a longer successor must declare a revised evidence/call-budget strategy before execution rather than silently reusing this ceiling.

# DD-144 Post-Cache-Fix Captured Short-Trajectory Result

- Classification: `post_cachefix_captured_short_trajectory_passed`
- Decision: `authorize_separately_frozen_controlled_trajectory_extension_contract`
- Completed coarse/refined steps: `10` / `20`
- Worst residual: `1.087532713e-10`
- Capture gates: `{'capture_count_matches_completed_steps': True, 'all_capture_arrays_read_only': True, 'residual_identity': True, 'one_frozen_jacobian_per_step': True}`
- DWSIM calls: `37045`
- Wall clock: `48.472 s`

The DD-134 scientific contract is unchanged. Complete captured evidence is retained for every attempted step.

## Outcome

The coarse path completes `10/10` roots and the refined path `20/20`. No line-search fraction is rejected. The worst coarse/refined Jacobian conditions are `2.084321e5` and `7.286588e5`; both remain below the frozen limit.

At `t=10 s`, coarse and refined endpoints agree within:

- inventory: `6.3526e-8` relative;
- energy: `1.0470e-8` relative;
- coordinates: `6.6774e-7` relative;
- product rates: `6.6492e-7` relative;
- levels: `5.1569e-9` absolute.

The first step reproduces DD-132 to at worst `3.7939e-11` in level and `1.9167e-11` in product rate. Products and controller memories move in the commanded direction, both level errors shrink, pressure remains ordered, and all physical, conservation, provider, call, and wall gates pass.

## Decision

DD-134's failures were consequences of the rounded property-cache defect, not evidence that the controlled DAE trajectory was infeasible. A separately frozen modest trajectory extension is authorized. The extension should preserve captured evidence and should not yet add another controller move, solver variation, or longer operating campaign.

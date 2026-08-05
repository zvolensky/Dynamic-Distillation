# DD-136 DD-134 Residual-Replay Audit Result

- Classification: `deterministic_replay_dd134_artifact_incomplete`
- Decision: `authorize_separately_frozen_in_process_failure_capture_contract`
- Same-process repeatable: `True`
- Cross-process/order repeatable: `True`
- DD-135 norms reproduced: `True`
- DD-134 saved-norm gap persists: `True`
- coarse cross-process vector spread: `0.000000000e+00` (component_balance[reflux_drum,n-Propane])
- coarse replayed norm range: `8.499349302e-09` to `8.499349302e-09`
- coarse DD-134 minimum norm gap: `4.241887117e-08`
- refined cross-process vector spread: `0.000000000e+00` (component_balance[reflux_drum,n-Propane])
- refined replayed norm range: `4.731911069e-08` to `4.731911069e-08`
- refined DD-134 minimum norm gap: `3.151938474e-08`
- Aggregate DWSIM calls: `507`
- Wall clock: `27.172 s`

No Jacobian, nonlinear solve, state advance, timestep, or trajectory was attempted.

## Interpretation

All nine complete 50-row vectors for each saved point are bit-for-bit identical across three distinct Python/DWSIM processes and grouped-forward, grouped-reverse, and interleaved orders. The coarse norm is always `8.499349302e-9`; the refined norm is always `4.731911069e-8`. Both reproduce DD-135 exactly.

The persistent differences from DD-134 are therefore not DWSIM process noise, same-process drift, or call-order dependence. DD-134 retained a scalar solver residual and final physical coordinates/state, but not the exact in-process residual vector, frozen Jacobian, correction, trial vectors, or enough solver-state identity evidence to replay that failure numerically.

DD-134 and DD-135 remain unchanged. No adaptive-refresh conclusion is authorized. One separately frozen in-process failure-capture contract may add immutable residual/Jacobian/line-search evidence to a future diagnostic execution before any solver architecture is selected.

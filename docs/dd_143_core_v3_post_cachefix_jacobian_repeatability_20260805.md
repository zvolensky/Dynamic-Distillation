# DD-143 Post-Cache-Fix Jacobian Repeatability Result

- Classification: `exact_state_cache_fix_jacobian_proof_passed`
- Decision: `authorize_separately_frozen_captured_trajectory_successor_contract`
- Cross-process/order repeatable: `True`
- Finite-difference step stable: `True`
- Worst cross-process relative Frobenius difference: `0.000000000e+00`
- Historical improvement factor: `1.880522575e+305`
- Worst `h` versus `h/2` relative difference: `2.330688118e-10`
- Worst spectrum change: `2.419767549e-08`
- Condition range: `2.084298241e+05` to `7.286434967e+05`
- Aggregate DWSIM calls: `14115`
- Wall clock: `78.767 s`

No nonlinear solve, correction, state advance, timestep, or trajectory was attempted.

## Interpretation

All four point/step matrices are bit-for-bit identical across grouped-forward, grouped-reverse, and interleaved fresh processes. Halving the difference step changes the matrices by at most `2.330688118e-10` relative and the singular spectra by at most `2.419767549e-8`.

DD-140's process/order dependence is eliminated. The rounded property cache was the causal defect. A separately frozen captured-trajectory successor may now test whether correcting that defect also removes the DD-134/DD-138 globalization failures; this audit itself did not run a solver or accept a state.

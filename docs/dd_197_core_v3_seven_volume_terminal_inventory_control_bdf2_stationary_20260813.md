# DD-197 Controlled BDF2 Stationary Parity Result

- Classification: `bdf2_stationary_parity_passed`
- Decision: `authorize_one_frozen_bdf2_moving_step_contract`
- BDF2 residual infinity norm: `4.979842e-13`
- BDF2 / BE residual difference: `0.000000e+00`
- BDF2 ranks: `58 / 58`
- BE rank: `58`
- Worst condition: `3.172742e+07`
- BDF2 spectrum step sensitivity: `1.078595e-07`
- BDF2 / BE matrix difference (diagnostic): `3.330511e-01`
- Provider calls: `11934`
- Wall clock: `5.230 s`
- Nonlinear solve, accepted timestep, tuning, or trajectory: `False`

## Assessment

Every frozen gate passes. Identical BDF2 histories preserve the accepted
stationary state exactly: inventory, component rates, internal-energy rates,
and PI-memory rates all have zero motion. The complete scaled residual is
`4.979842e-13` and is bit-for-bit identical to the backward-Euler stationary
residual.

Both BDF2 finite-difference Jacobians and the backward-Euler reference retain
rank `58`. The BDF2 singular spectrum changes by only `1.078595e-7` between
the two finite-difference steps. The `0.3330511` BDF2/backward-Euler matrix
difference is diagnostic and expected because BDF2 applies a different time
derivative weight; it does not indicate a changed stationary root, lost
equation, or unexpected coupling.

All physicality, equilibrium, component/energy conservation, provider
ownership, call-count, and wall-clock gates pass. The live audit used `11,934`
logical property calls in `5.230 s`.

## Decision Boundary

One separately frozen BDF2 moving-step contract is authorized. It may compare
one BDF2 step against the accepted backward-Euler refinement from the same
history and disturbance. It must include an accepted backward-Euler startup
history, fixed timestep, full closure/rank/physicality gates, and a direct
accuracy comparison. No trajectory, controller tuning, retry, or timestep
campaign is authorized.

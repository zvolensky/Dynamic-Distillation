# DD-134 Modified-Newton Short Controlled-Trajectory Result

- Classification: `dd134_failed`
- Decision: `stop_modified_newton_controlled_trajectory_path`
- Completed steps: `7 / 6`
- Worst residual: `5.091822e-08`
- DWSIM calls: `16801`
- Wall clock: `9.919 s`

No rebuild, fallback, retry, or grid change was attempted.

## Decision Detail

The coarse path closes six steps and stops on step 7 at `t=7 s`; its frozen-
Jacobian line search rejects all four fractions at iteration 2 with residual
`5.091822e-8`. The refined path closes five steps and stops on step 6 at
`t=3 s`; its line search fails at iteration 5 with residual `1.579973e-8`.
Both exceed the frozen `<1e-8` closure gate.

This is a solver-globalization failure, not evidence of physical divergence.
Every completed endpoint remains physical and conservative with ordered
pressure, correct controller direction, full-rank Jacobians, and condition
below `7.31e5`. The first coarse step reproduces DD-132 exactly. A static
same-time comparison at `t=3 s` gives inventory difference `3.374022e-8`,
coordinate difference `2.041384e-7`, product difference `2.041384e-7`, and
level difference `2.824641e-9`, all within the frozen endpoint-refinement
limits. The reported final refinement gate is non-diagnostic because the two
paths stopped at different simulated times.

The run used `16,801` DWSIM calls in `9.919 s`, comfortably within its limits.
Per the contract, the one-frozen-Jacobian controlled-trajectory path is stopped
without retry or solver adjustment.

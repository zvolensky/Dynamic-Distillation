# DD-193 Controlled Finer-Grid Parallel Trajectory Contract

- Payload SHA-256: `0d9f1c06a792f5d7394c6ccf1853fc58d7517fe636e24e32d94bcc64e0aaf874`
- Preparation base commit: `bb79f57f2d619701153445b274830223248dc693`
- Duration: `10.0 s`
- Coarse: `80 x 0.125 s`
- Refined: `160 x 0.0625 s`
- Solver: one persistent four-worker DWSIM Jacobian pool
- Physics, disturbance, controllers, setpoints, and acceptance limits: unchanged
- Projected serial baseline: `277.433 s`
- Parallel trajectory wall gate: `<208.074 s` excluding startup
- Tuning, retry, alternate grid, fallback, clipping, and longer horizon: prohibited

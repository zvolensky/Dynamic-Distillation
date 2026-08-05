# DD-150 Frozen Parallel Captured 60-Second Trajectory Contract

- Payload SHA-256: `f20b3e01fe52ae76ccdcd0a62f766ef61c40695107b16ea282bd3e2e38f9d25f`
- Scientific reference: exact accepted DD-146 trajectory and captures
- Duration/grids: `60 s`, `60 x 1.0 s`, and `120 x 0.5 s`
- Solver: immutable captured modified Newton
- Parallel work: one persistent four-process pool for all 180 Jacobians
- Dynamic worker context: actual previous inventory, energy, controller memory, and timestep
- Serial equivalence: every capture, accepted step, and endpoint `<=1e-10` versus DD-146
- Exact work: 7,560 tasks and 211,680 worker-provider calls
- Meaningful wall gate: `<60%` of DD-146 and `<75 s` including startup/shutdown
- Rebuild, retry, fallback, clipping, projection, controller change, or grid change: prohibited

Passing may authorize a separately frozen multi-minute parallel trajectory. Failure retains the validated serial path.

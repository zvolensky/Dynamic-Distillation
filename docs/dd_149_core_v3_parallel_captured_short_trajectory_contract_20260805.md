# DD-149 Frozen Parallel Captured Short-Trajectory Contract

- Payload SHA-256: `e2f63dd0b46498a6a7da10d01f7a16dd577a84dbf63c053c6631aedfbd6acbe0`
- Scientific experiment: exact DD-144 `10 s` coarse/refined trajectory
- Solver: immutable captured modified Newton
- Parallel work: one persistent four-process pool for all 30 Jacobians
- Dynamic worker context: actual previous inventory, energy, controller memory, and timestep for every root
- Capture: complete residual, matrix, correction, and line-search evidence for every root
- Serial equivalence: every step and both endpoints `<=1e-10` versus DD-144
- Exact work: 1,260 tasks and 35,280 worker-provider calls
- Meaningful wall gate: `<60%` of DD-144 and `<75 s` including startup/shutdown
- Rebuild, retry, fallback, clipping, projection, or grid change: prohibited

Passing authorizes only a separately frozen modest parallel trajectory extension. Failure retains the serial path.

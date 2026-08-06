# DD-151 Frozen Parallel Captured Five-Minute Trajectory Contract

- Payload SHA-256: `beeed82b9a9d34d49c1f9751ece943915574b3e877695ce4c23b92e31e985994`
- Sole scientific change from DD-146: duration `60 s -> 300 s`
- Grids: `300 x 1.0 s` and `600 x 0.5 s`
- Solver/parallel path: exact DD-150 captured modified Newton and one persistent four-process pool
- Frozen oracle: first `60/120` roots exactly reproduce DD-146 within `1e-10`
- Remaining acceptance: inherited endpoint refinement, physicality, pressure, conservation, direction, and kinematics
- Exact work: 37,800 tasks and 1,058,400 worker-provider calls
- Successful evidence: deterministic per-root capture and call-audit SHA-256 summaries
- Failure evidence: complete replay captures retained
- Governed wall: `<5x` DD-150 and `<330 s` including pool lifetime
- Rebuild, retry, fallback, clipping, projection, controller change, or grid change: prohibited

Passing establishes a five-minute parallel controlled trajectory. Failure stops with full replay evidence.

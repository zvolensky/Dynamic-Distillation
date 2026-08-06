# DD-166 Frozen Hybrid-Jacobian Short-Trajectory Successor

- Payload SHA-256: `9f85bb121b8208b532d3b0e76c1e1463f8bedfb345f7ba297f6aa43b8cedd576`
- Scientific contract: exactly DD-165
- Sole correction: disabled-by-default exact-key Clapeyron fugacity memoization and statistics
- Solver, grids, controls, worker count, gates, and limits: unchanged
- DD-165 will not be rerun

Passing authorizes a separately frozen longer derivative-accelerated trajectory. Failure retires the path.

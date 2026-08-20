# DD-245 Stationary Vapor-Holdup Root Contract

- Starts: `1`
- Solver: `scipy.optimize.least_squares(method='trf')`
- Jacobian: `28-color central difference, h=1e-5`
- Dimension: `260 x 260`
- Maximum function evaluations: `120`
- Fixed coordinate-scale range: `0.285257` to `8.18164`
- Source scaled conditions: `2.044142e+04` / `2.044142e+04`
- Root residual limit: `1e-8`
- Endpoint rank/condition: `260 / <1e8`
- Call/wall limits: `1,000,000 / 600 s`

The campaign has no retry or tuning path. Failure stops nonlinear work; success still requires a separate dynamic handoff and hold audit.

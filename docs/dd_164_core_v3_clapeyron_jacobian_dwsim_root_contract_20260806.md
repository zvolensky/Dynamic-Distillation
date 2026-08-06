# DD-164 Frozen Clapeyron-Jacobian/DWSIM-Root Contract

- Payload SHA-256: `b39f3f26fe6833550c7633a0eaf7c9fcc2929c4d2ba7d0d5839ceeb0a4264a17`
- Root: exact accepted DD-148/DD-146 first coarse moving root
- Governing residual, line search, convergence, and endpoint: DWSIM only
- Approximate frozen Jacobian: Clapeyron fugacity with DWSIM bulk properties
- Solver settings and four line-search fractions: unchanged
- Required root residual: `<1e-8`
- Accepted-root coordinate reproduction: `<=1e-6`
- Minimum warm matrix speedup: `1.10x`
- Retry, state acceptance, timestep, and trajectory: prohibited

Passing may authorize only a separately frozen short derivative-acceleration trajectory.

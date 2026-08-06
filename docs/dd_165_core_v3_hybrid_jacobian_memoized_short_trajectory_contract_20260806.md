# DD-165 Frozen Hybrid-Jacobian Memoized Short-Trajectory Contract

- Payload SHA-256: `6586f7e22f4f217e69eb0f74ed380d8f99ec4e6f03f7c7cd8ee69ef58b402d0a`
- Scientific case: exact DD-158 10-second coarse/refined controlled trajectory
- Main-process residual, solver, line search, and endpoint: DWSIM only
- Four worker Jacobians: Clapeyron fugacity with DWSIM bulk properties
- Exact memoization: one epoch per root; hit fraction `>=0.60`
- Capture and state equivalence: `<=1e-10`
- Trajectory wall: `<=0.95x` DD-158
- Startup-adjusted five-minute projection: below accepted DD-160
- Retry, fallback, clipping, projection, or grid change: prohibited

Passing authorizes a separately frozen longer derivative-accelerated trajectory. Failure retires this acceleration path.

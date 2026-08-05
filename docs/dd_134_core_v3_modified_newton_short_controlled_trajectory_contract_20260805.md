# DD-134 Frozen Modified-Newton Short Controlled-Trajectory Contract

- Payload SHA-256: `3a8760929d2025559d78a9cabecbe3ac9e8825334e286692d1b22521ff12d269`
- Initial state and disturbance: exact DD-132
- Duration: `10 s`
- Grids: `10 x 1.0 s` and `20 x 0.5 s`
- Solver: one frozen 21-color Jacobian and one LU factorization per root
- Provider-call limit: `<80000`
- Wall-clock limit: `<180 s`
- Rebuild, fallback, retry, clipping, projection, or changed grid: `False`

This commit freezes the contract only. Trajectory execution requires explicit authorization after the contract commit is reviewed.

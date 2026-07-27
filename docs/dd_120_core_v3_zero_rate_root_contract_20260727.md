# DD-120 Frozen Core V3 Zero-Rate Root Contract

- Payload SHA-256: `7d804f246f3d2b93b88941fd9738b51e21534c327b916ef539e1aaf28aaa8bfb`
- System: overdetermined `48 x 46` zero-rate residual
- Starts: DD-112 canonical and DD-115 refined one-second state
- Solver: one bounded `least_squares(method='trf')` configuration
- Jacobian: unchanged 20-color central difference
- Acceptance: every row below `1e-8`, common root below `1e-6`
- Retry, continuation, timestep, controller, or dynamics: `False`

Execution is permitted once only after this exact contract is committed. Failure retires the terminal-scaled zero-rate root path without tuning.

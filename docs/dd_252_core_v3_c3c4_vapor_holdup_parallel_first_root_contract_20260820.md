# DD-252 Vapor-Holdup Parallel First-Root Contract

- Payload SHA-256: `b093f0462388f86e4e9bddea0ca54c9ac7de6632b9dfc990621d92d0fd58356f`
- Root: first DD-249 `0.25 s`, `+0.1%` feed endpoint.
- Solves: one serial and one persistent eight-worker parallel root.
- Main process retains SciPy residual, trust-region, convergence, and acceptance decisions.
- Delegated work: only 28-color central-difference residual tasks.
- Endpoint agreement: `1e-12`; Jacobian agreement: `1e-10`.
- Performance: parallel solve wall at most 75% of serial wall, excluding startup.
- State advance, retry, controller, or trajectory: `False`.

# DD-251 Vapor-Holdup Parallel Jacobian Contract

- Payload SHA-256: `e5d441e8fb0a0d9de25ad006ef61cc44b2aaf5455c8184d075a03db26e70f915`
- Matrix: `258 x 258` with `28` colors and `56` tasks.
- Comparison: one serial matrix and one eight-worker process-isolated matrix.
- State: accepted DD-249 full-step endpoint.
- Matrix, rank, spectrum, condition, provider, call, and wall gates are fixed.
- Performance gate: parallel matrix wall at most 75% of serial wall.
- Nonlinear solve, state advance, controller, or trajectory: `False`.

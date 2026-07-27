# DD-115 Frozen Core V3 Initializer First-Step Refinement Contract

- Payload SHA-256: `388fcde1f35de0824145104472e2b8609fcd0acadb5bf03fc2a255ccf9fae9cf`
- Canonical endpoint: `dd094_storage_and_pressure_profile`
- Coarse/refined grids to `t=1 s`: `1 x 1.0 s / 2 x 0.5 s`
- System: exact conserved-N/U `46 x 46` backward Euler
- Colored Jacobian groups: `21`
- Solver: one frozen trust-region configuration, no retry
- Controllers or longer trajectory: `False`

Execution is permitted once only after this exact contract is committed. Passing authorizes only a separately frozen short open-loop trajectory contract.

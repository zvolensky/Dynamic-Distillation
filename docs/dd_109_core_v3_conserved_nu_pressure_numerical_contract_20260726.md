# DD-109 Frozen Conserved N/U Pressure Numerical Contract

- Payload SHA-256: `c3ffe33e917eeea8a7d70490a8808aacdc93355c84878e154150c6be2aa6c31c`
- Live system: `46 x 46` leading residual
- Colored Jacobian groups: `15`
- States: DD-094 algebraic profile and DD-103 pressure endpoint guess
- Jacobian steps: `1e-5`, `5e-6`
- Canonical cross-check: one full central-difference Jacobian
- Live property evaluation during preparation: `False`
- Nonlinear solve during preparation: `False`
- Initializer or integration during preparation: `False`

Execution is permitted once only after this contract is committed. No root solve, timestep, or initializer is part of DD-109.
